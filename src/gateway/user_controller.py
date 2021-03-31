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
import logging
import uuid
import time
import six
from ioc import Injectable, Inject, Singleton, INJECTED
from gateway.authentication_controller import AuthenticationController, AuthenticationToken
from gateway.exceptions import ItemDoesNotExistException
from gateway.models import User
from gateway.mappers.user import UserMapper
from gateway.dto.user import UserDTO
from gateway.enums import UserEnums

if False:  # MYPY
    from typing import Tuple, List, Optional, Dict, Union

logger = logging.getLogger('openmotics')

@Injectable.named('user_controller')
@Singleton
class UserController(object):
    """ The UserController provides methods for the creation and authentication of users. """

    @Inject
    def __init__(self, config=INJECTED, authentication_controller=INJECTED):
        # type: (Dict[str, str], AuthenticationController) -> None
        """ Constructor a new UserController. """
        self._config = config
        self.authentication_controller = authentication_controller

    def start(self):
        # type: () -> None
        # Create the user for the cloud
        logger.info('Adding the cloud user')
        first_name = self._config['username'].lower()
        password = self._config['password']
        hashed_password = UserDTO._hash_password(password)

        if User.select().where((User.first_name == first_name) & (User.password == hashed_password)).first():
            # If the cloud user is already in the DB, do not add it anymore
            logger.debug('Cloud user already added, not adding it anymore')
            return

        cloud_user_dto = UserDTO(
            username=self._config['username'].lower(),
            pin_code=self._config['username'].lower(),
            role=User.UserRoles.ADMIN,
            accepted_terms=AuthenticationController.TERMS_VERSION
        )
        cloud_user_dto.set_password(self._config['password'])
        # Save the user to the DB
        self.save_user(user_dto=cloud_user_dto,
                       fields=['first_name', 'last_name', 'password', 'accepted_terms', 'pin_code', 'role'])

    def stop(self):
        # type: () -> None
        pass

    def save_user(self, user_dto, fields):
        # type: (UserDTO, List[str]) -> None
        """ Saves one instance of a user with the defined fields in param fields """
        _ = self
        logger.info('Saving user: {}'.format(user_dto))
        user_orm = UserMapper.dto_to_orm(user_dto, fields)
        logger.info('Saving user: {}'.format(user_orm))
        UserController._validate(user_orm)
        user_orm.save()

    def save_users(self, users):
        # type: (List[Tuple[UserDTO, List[str]]]) -> None
        """ Create or update a new user using a user DTO object """
        for user_dto, fields in users:
            self.save_user(user_dto, fields)

    def load_user(self, user_id):
        # type: (int) -> UserDTO
        """  Returns a UserDTO of the requested user """
        _ = self
        user_orm = User.select().where(User.id == user_id).first()
        user_dto = UserMapper.orm_to_dto(user_orm)
        user_dto.clear_password()
        return user_dto

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
        """ Return the number of registered users """
        return User.select().count()

    def remove_user(self, user_dto):
        # type: (UserDTO) -> None
        """  Remove a user. """
        # remove the token if one is there
        try:
            self.authentication_controller.remove_token_for_user(user_dto)
        except:
            pass

        # set username to lowercase to compare on username
        first_name = user_dto.first_name.lower()
        last_name = user_dto.last_name.lower()

        # check if the removed user is not the last admin user of the system
        if UserController.get_number_of_users() <= 1:
            raise Exception(UserEnums.DeleteErrors.LAST_ACCOUNT)
        User.delete().where((User.first_name == first_name) & (User.last_name == last_name)).execute()

    def login(self, user_dto, accept_terms=False, timeout=None):
        # type: (UserDTO, Optional[bool], Optional[float]) -> Tuple[bool, Union[str, AuthenticationToken]]
        """  Login a user given a UserDTO """
        success, token = self.authentication_controller.login(user_dto, accept_terms, timeout)
        return success, token

    def logout(self, token):
        # type: (str) -> None
        """  Removes the token from the controller.  """
        self.authentication_controller.logout(token)

    def check_token(self, token):
        result = self.authentication_controller.check_token(token)
        return result is not None

    @staticmethod
    def _validate(user):
        # type: (User) -> None
        """  Checks if the user object is a valid object to store  """
        if user.username is None or not isinstance(user.username, six.string_types) or user.username.strip() == '':
            raise RuntimeError('A user must have a username, value of type {} is provided'.format(type(user.username)))
        if user.password is None or not isinstance(user.password, six.string_types):
            raise RuntimeError('A user must have a password, value of type {} is provided'.format(type(user.password)))
        if user.accepted_terms is None or \
            not isinstance(user.accepted_terms, six.integer_types) or \
                0 < user.accepted_terms < AuthenticationController.TERMS_VERSION:
            raise RuntimeError('A user must have a valid "accepted_terms" fields')