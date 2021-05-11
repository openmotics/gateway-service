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
import random
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
        self.load_users()

    def start(self):
        # type: () -> None
        # Create the user for the cloud
        logger.info('Adding the cloud user')
        username = self._config['username'].lower()

        cloud_user_dto = UserDTO(
            username=username,
            pin_code=None,
            role=User.UserRoles.ADMIN,
            accepted_terms=AuthenticationController.TERMS_VERSION
        )
        cloud_user_dto.set_password(self._config['password'])
        # Save the user to the DB
        self.save_user(user_dto=cloud_user_dto)

    def stop(self):
        # type: () -> None
        pass

    def user_id_exists(self, user_id):
        # type: (int) -> bool
        user_orm = User.get_by_id(user_id)
        return user_orm is not None

    def save_user(self, user_dto):
        # type: (UserDTO) -> UserDTO
        """ Saves one instance of a user with the defined fields in param fields """
        _ = self
        if 'language' in user_dto.loaded_fields:
            if user_dto.language not in User.UserLanguages.ALL:
                raise RuntimeError('Could not save the user with an unknown language: {}'.format(user_dto.language))

        user_orm = UserMapper.dto_to_orm(user_dto)
        UserController._validate(user_orm)
        user_orm.save()
        if user_orm.apartment is not None:
            user_orm.apartment.save()
        user_dto_saved = UserMapper.orm_to_dto(user_orm)
        return user_dto_saved


    def save_users(self, users):
        # type: (List[UserDTO]) -> None
        """ Create or update a new user using a user DTO object """
        for user_dto in users:
            self.save_user(user_dto)

    def load_user(self, user_id):
        # type: (int) -> Optional[UserDTO]
        """  Returns a UserDTO of the requested user """
        _ = self
        user_orm = User.select().where(User.id == user_id).first()
        if user_orm is None:
            return None
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
        # self.user_cache = users
        return users

    def activate_user(self, user_id):
        _ = self
        try:
            user_orm = User.select().where(User.id == user_id).first()
            user_orm.is_active = True
            user_orm.save()
        except Exception as e:
            raise RuntimeError('Could not save the is_active flag to the database: {}'.format(e))

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
        username = user_dto.username.lower()

        # check if the removed user is not the last admin user of the system
        if UserController.get_number_of_users() <= 1:
            raise Exception(UserEnums.DeleteErrors.LAST_ACCOUNT)

        User.delete().where(User.username == username).execute()

    def login(self, user_dto, accept_terms=False, timeout=None):
        # type: (UserDTO, bool, Optional[float]) -> Tuple[bool, Union[str, AuthenticationToken]]
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

    def generate_new_pin_code(self):
        # type: () -> int
        _ = self
        current_pin_codes = User.select(User.pin_code).execute()
        while True:
            new_pin = random.randint(0, 9999)
            if new_pin not in current_pin_codes:
                break
        return new_pin

    def check_if_pin_exists(self, pin):
        _ = self
        current_pin_codes = User.select(User.pin_code).execute()
        return pin in current_pin_codes

    @staticmethod
    def _validate(user):
        # type: (User) -> None
        """  Checks if the user object is a valid object to store  """
        if user.username is None or not isinstance(user.username, six.string_types) or user.username.strip() == '':
            raise RuntimeError('A user must have a username, value of type {} is provided'.format(type(user.username)))
        if (not (user.password is not None and isinstance(user.password, six.string_types)) and
                not (user.pin_code is not None and isinstance(user.pin_code, six.string_types))):
            raise RuntimeError('A user must have a password or pin_code, value of types {} {} is provided'.format(type(user.password), type(user.pin_code)))
        if user.accepted_terms is None or \
            not isinstance(user.accepted_terms, six.integer_types) or \
                0 < user.accepted_terms < AuthenticationController.TERMS_VERSION:
            raise RuntimeError('A user must have a valid "accepted_terms" fields')
