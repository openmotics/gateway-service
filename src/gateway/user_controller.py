# Copyright (C) 2020 OpenMotics BV
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
The users module contains the UserController class, which provides methods for creating
and authenticating users.
"""

from __future__ import absolute_import
import sqlite3
import hashlib
import uuid
import time
import logging
import six
from random import randint
from ioc import Injectable, Inject, Singleton, INJECTED
from gateway.models import User
from gateway.mappers.user import UserMapper
from gateway.dto.user import UserDTO

if False: # MYPY
    from typing import Tuple, List

logger = logging.getLogger('openmotics')


@Injectable.named('user_controller')
@Singleton
class UserController(object):
    """ The UserController provides methods for the creation and authentication of users. """

    TERMS_VERSION = 1

    @Inject
    def __init__(self, config=INJECTED, token_timeout=INJECTED):
        """ Constructor a new UserController.

        :param user_db: filename of the sqlite database used to store the users and tokens.
        :param lock: shared lock for the given DB
        :type lock: threading.Lock
        :param config: Contains the OpenMotics cloud username and password.
        :type config: A dict with keys 'username' and 'password'.
        :param token_timeout: the number of seconds a token is valid.
        """
        logger.info("Initializing the user controller")
        self._config = config
        self._token_timeout = token_timeout
        self._tokens = {} #type: Dict[str, Tuple(str, float)]
        # WITH CACHE USE
        # self._cached_users = {} #type: Dict[str, User]

        # Create the user for the cloud
        cloud_user_dto = UserDTO(
            username=self._config['username'].lower(), 
            password=self._config['password'],
            role="admin",
            enabled=True,
            accepted_terms=UserController.TERMS_VERSION
        )
        logger.info("Adding the cloud user")
        self.save_users(users=[(cloud_user_dto, ['username', 'password', 'role', 'enabled', 'accepted_terms'])])

    @staticmethod
    def _hash(password):
        """ Hash the password using sha1. """
        sha = hashlib.sha1()
        sha.update("OpenMotics")
        sha.update(password)
        return sha.hexdigest()

    # WITH CACHE USE
    # def reload_users(self):
    #     for user in User.select():
    #         self._cached_users[user.username] = user


    def save_users(self, users):
        # type: (List[Tuple[UserDTO, List[str]]]) -> None
        """
        Create a new user using a user DTO object
        """
        for user_dto, fields in users:
            logger.debug("Saving new user with username: [{}]".format(user_dto.username))
            user_dto_to_save = UserDTO(
                username=user_dto.username.lower(),
                password=self._hash(user_dto.password),
                role=user_dto.role,
                enabled=user_dto.enabled,
                accepted_terms=user_dto.accepted_terms
            )
            user = UserMapper.dto_to_orm(user_dto_to_save, fields)
            self._validate(user)
            user.save()
            

    def get_usernames(self):
        """ Get all usernames.

        :returns: a list of strings.
        """
        return [user.username for user in User.select()]


    def remove_user(self, username):
        """ Remove a user.

        :param username: the name of the user to remove.
        """
        username = username.lower()

        # check if the removed user is not the last admin user of the system
        if self.get_role(username) == "admin" and self._get_num_admins() == 1:
            raise Exception("Cannot delete last admin account")
        else:
            User.delete().where(User.username == username).execute()

            to_remove = []
            for token in self._tokens:
                if self._tokens[token][0] == username:
                    to_remove.append(token)

            for token in to_remove:
                del self._tokens[token]

    def _get_num_admins(self):
        """ Get the number of admin users in the system. """

        # TO WORK WITH CACHE
        # count = 0
        # for user in self._cached_users:
        #     if self._cached_users[user].role == "admin":
        #         count += 1
        # return count

        count = User.select().where(User.role == "admin").count()
        return count

    def login(self, users):
        # type: (List[Tuple[UserDTO, bool, float]]) -> Tuple[bool, str]
        """ Login with a username and password, returns a token for this user.

        :param user: Tuple of the UserDTO object, accepted_terms and timeout value
        :returns: a token that identifies this user, None for invalid credentials.
        """

        if isinstance(users, tuple):
            return False, 'User_is_not_a_tuple'

        for user, accept_terms, timeout in users:
            user.username = user.username.lower()
            logger.debug("Logging in user with username [{}]".format(user.username))
            if timeout is not None:
                try:
                    timeout = int(timeout)
                    timeout = min(60 * 60 * 24 * 30, max(60 * 60, timeout))
                except ValueError:
                    timeout = None
            if timeout is None:
                timeout = self._token_timeout

            for user_orm in User.select().where(
                User.username == user.username,
                User.password == UserController._hash(user.password),
                User.enabled == 1
            ):
                # check if returned object is valid
                if user_orm is None or not hasattr(user_orm, 'username'):
                    logger.debug("User login: Could not find any user with name [{}]".format(user.username))
                    return False, 'invalid_credentials'

                if user_orm.accepted_terms == UserController.TERMS_VERSION:
                    return True, self._gen_token(user_orm.username, time.time() + timeout)
                if accept_terms is True:
                    user_orm.accepted_terms=UserController.TERMS_VERSION
                    user_orm.save()
                    return True, self._gen_token(user_orm.username, time.time() + timeout)
                logger.debug("User login: User [{}] has not accepted the latest terms".format(user.username))
                return False, 'terms_not_accepted'
        logger.debug("User login: Could not find user with credentials")
        return False, 'invalid_credentials'


    def logout(self, token):
        """ Removes the token from the controller. """
        self._tokens.pop(token, None)

    def get_role(self, username):
        """ Get the role for a certain user. Returns None is user was not found. """
        username = username.lower()

        for user_orm in User.select().where(User.username == username):
            user_dto = UserMapper.orm_to_dto(user_orm)
            if user_orm is not None:
                return user_dto.role
        return None

    def _gen_token(self, username, valid_until):
        """ Generate a token and insert it into the tokens dict. """
        ret = uuid.uuid4().hex
        self._tokens[ret] = (username, valid_until)

        # Delete the expired tokens
        for token in self._tokens.keys():
            if self._tokens[token][1] < time.time():
                logger.debug("Removing expired token for user: [{}]".format(self._tokens[token][0]))
                self._tokens.pop(token, None)

        return ret

    def check_token(self, token):
        """ Returns True if the token is valid, False if the token is invalid. """
        if token is None or token not in self._tokens:
            return False
        else:
            timed_out = self._tokens[token][1] >= time.time()
            return timed_out

    def _validate(self, user):
        # type: (User) -> None
        if user.username is None or not isinstance(user.username, six.string_types) or user.username.strip() == '':
            raise RuntimeError("A user must have a username")
        if user.password is None or not isinstance(user.password, six.string_types) or user.password.strip() == '':
            raise RuntimeError("A user must have a password")
        if user.accepted_terms is None or \
            not isinstance(user.accepted_terms, six.integer_types) or \
            0 < user.accepted_terms < UserController.TERMS_VERSION:
            raise RuntimeError("A user must have a valid 'accepted_terms' fields")
