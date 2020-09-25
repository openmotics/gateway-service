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
import uuid
import time
import six
from ioc import Injectable, Inject, Singleton, INJECTED
from gateway.models import User
from gateway.mappers.user import UserMapper
from gateway.dto.user import UserDTO
from gateway.enums import UserEnums

if False:  # MYPY
    from typing import Tuple, List, Optional, Dict


@Injectable.named('user_controller')
@Singleton
class UserController(object):
    """ The UserController provides methods for the creation and authentication of users. """

    TERMS_VERSION = 1

    @Inject
    def __init__(self, config=INJECTED, token_timeout=INJECTED):
        # type: (Dict[str, str], int) -> None
        """ Constructor a new UserController. """
        self._config = config
        self._token_timeout = token_timeout
        self._tokens = {}  # type: Dict[str, Tuple[str, float]]

        # Create the user for the cloud
        cloud_user_dto = UserDTO(
            username=self._config['username'].lower(),
            accepted_terms=UserController.TERMS_VERSION
        )
        cloud_user_dto.set_password(self._config['password'])
        self.save_users(users=[(cloud_user_dto, ['username', 'password', 'accepted_terms'])])

    def save_user(self, user_dto, fields):
        # type: (UserDTO, List[str]) -> None
        """ Saves one instance of a user with the defined fields in param fields """
        _ = self
        user_orm = UserMapper.dto_to_orm(user_dto, fields)
        UserController._validate(user_orm)
        user_orm.save()

    def save_users(self, users):
        # type: (List[Tuple[UserDTO, List[str]]]) -> None
        """ Create or update a new user using a user DTO object """
        for user_dto, fields in users:
            self.save_user(user_dto, fields)

    def load_users(self):
        # type: () -> List[UserDTO]
        """  Returns a list of UserDTOs with all the usernames """
        _ = self
        users = []
        for user_orm in User.select():
            user_dto = UserMapper.orm_to_dto(user_orm)
            user_dto.clear_password()
            users.append(user_dto)
        return users

    @staticmethod
    def get_number_of_users():
        # type: () -> int
        """ Return the number of registred users """
        return User.select().count()

    def remove_user(self, user_dto):
        # type: (UserDTO) -> None
        """  Remove a user. """
        # set username to lowercase to compare on username
        username = user_dto.username.lower()

        # check if the removed user is not the last admin user of the system
        if UserController.get_number_of_users() <= 1:
            raise Exception(UserEnums.DeleteErrors.LAST_ACCOUNT)
        User.delete().where(User.username == username).execute()

        to_remove = []
        for token in self._tokens:
            if self._tokens[token][0] == username:
                to_remove.append(token)

        for token in to_remove:
            del self._tokens[token]

    def login(self, user_dto, accept_terms=False, timeout=None):
        # type: (UserDTO, Optional[bool], Optional[float]) -> Tuple[bool, str]
        """  Login a user given a UserDTO """

        if timeout is not None:
            try:
                timeout = int(timeout)
                timeout = min(60 * 60 * 24 * 30, max(60 * 60, timeout))
            except ValueError:
                timeout = None
        if timeout is None:
            timeout = self._token_timeout

        user_orm = User.select().where(
            User.username == user_dto.username.lower(),
            User.password == user_dto.hashed_password
        ).first()

        if user_orm is None:
            return False, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS

        if user_orm.accepted_terms == UserController.TERMS_VERSION:
            return True, self._gen_token(user_orm.username, time.time() + timeout)
        if accept_terms is True:
            user_orm.accepted_terms = UserController.TERMS_VERSION
            user_orm.save()
            return True, self._gen_token(user_orm.username, time.time() + timeout)
        return False, UserEnums.AuthenticationErrors.TERMS_NOT_ACCEPTED

    def logout(self, token):
        # type: (str) -> None
        """  Removes the token from the controller.  """
        self._tokens.pop(token, None)

    def _gen_token(self, username, valid_until):
        # type: (str, float) -> str
        """  Generate a token and insert it into the tokens dict.  """
        ret = uuid.uuid4().hex
        self._tokens[ret] = (username, valid_until)

        # Delete the expired tokens
        for token in list(self._tokens.keys()):
            if self._tokens[token][1] < time.time():
                self._tokens.pop(token, None)

        return ret

    def check_token(self, token):
        # type: (str) -> bool
        """  Returns True if the token is valid, False if the token is invalid.  """
        if token is None or token not in self._tokens:
            return False
        else:
            timed_out = self._tokens[token][1] >= time.time()
            return timed_out

    @staticmethod
    def _validate(user):
        # type: (User) -> None
        """  Checks if the user object is a valid object to store  """
        if user.username is None or not isinstance(user.username, six.string_types) or user.username.strip() == '':
            raise RuntimeError('A user must have a username')
        if user.password is None or not isinstance(user.password, six.string_types):
            raise RuntimeError('A user must have a password')
        if user.accepted_terms is None or \
            not isinstance(user.accepted_terms, six.integer_types) or \
                0 < user.accepted_terms < UserController.TERMS_VERSION:
            raise RuntimeError('A user must have a valid "accepted_terms" fields')
