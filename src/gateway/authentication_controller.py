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
authentication manager manages logged in users in the system.
"""

from __future__ import absolute_import

from enum import Enum
import logging
import json
import time
import uuid

import constants
from ioc import Injectable, Inject, Singleton, INJECTED
from gateway.dto import UserDTO
from gateway.enums import UserEnums
from gateway.exceptions import ItemDoesNotExistException, GatewayException, UnAuthorizedException
from gateway.mappers.user import UserMapper
from gateway.models import User

logger = logging.getLogger(__name__)


if False:  # MYPY
    from typing import Tuple, List, Optional, Dict, Union
    from gateway.user_controller import UserController


class LoginMethod(Enum):
    PIN_CODE = 'pin_code'
    PASSWORD = 'password'

@Injectable.named('authentication_controller')
@Singleton
class AuthenticationController(object):
    TERMS_VERSION = 1

    @Inject
    def __init__(self, token_timeout=INJECTED, token_store=INJECTED):
        # type: (int, TokenStore) -> None
        self._token_timeout = token_timeout
        self.token_store = token_store  # type: TokenStore
        self.api_secret = AuthenticationController._retrieve_api_secret()
        self.user_controller = None  # type: Optional[UserController]

    def set_user_controller(self, user_controller):
        # type: (UserController) -> None
        self.user_controller = user_controller

    @staticmethod
    def _retrieve_api_secret():
        conf_file = constants.get_renson_main_config_file()
        try:
            with open(conf_file, 'rb') as conf_file_stream:
                conf_json = json.load(conf_file_stream)
                secret = conf_json['secret']
            return secret
        except Exception:
            return None

    def login(self,
              user_dto,                             # type: UserDTO
              accept_terms=False,                   # type: bool
              timeout=None,                         # type: Optional[float]
              impersonate=None,                     # type: Optional[str]
              login_method=LoginMethod.PASSWORD     # type: LoginMethod
              ):
        # type: (...)  -> Tuple[bool, Union[str, AuthenticationToken]]
        """  Login a user given a UserDTO """

        # Set the proper timeout value
        if timeout is not None:
            try:
                timeout = int(timeout)
                timeout = min(60 * 60 * 24 * 30, max(60 * 60, timeout))
            except ValueError:
                timeout = None
        if timeout is None:
            timeout = self._token_timeout

        # Load the user that tries to login
        user_orm = User.select().where(
            (User.username == user_dto.username.lower()) &
            (User.password == user_dto.hashed_password)
        ).first()

        # If the user does not exists
        if user_orm is None:
            return False, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS

        # convert the user to a dto object
        user_dto = UserMapper.orm_to_dto(user_orm)

        # check if the users wants to impersonate some other user
        impersonator = None  # type: Optional[UserDTO]
        if impersonate is not None:
            if user_dto.role != User.UserRoles.SUPER:
                return False, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS
            if self.user_controller is not None:
                user_impersonate = self.user_controller.load_user_by_username(impersonate)
            else:
                raise GatewayException('UserController is not present in the authentication controller')
            if user_impersonate is None:
                return False, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS
            user_to_login = user_impersonate
            impersonator = user_dto
        else:
            user_to_login = user_dto
            impersonator = None

        # Check if accepted terms
        if user_orm.accepted_terms == AuthenticationController.TERMS_VERSION:
            token = self.token_store.create_token(user_to_login, timeout=timeout, impersonator=impersonator, login_method=login_method)
            return True, token
        if accept_terms is True:
            user_orm.accepted_terms = AuthenticationController.TERMS_VERSION
            user_orm.save()
            token = self.token_store.create_token(user_to_login, timeout=timeout, impersonator=impersonator, login_method=login_method)
            return True, token
        return False, UserEnums.AuthenticationErrors.TERMS_NOT_ACCEPTED

    def login_with_user_code(self, pin_code, accept_terms=False, timeout=None):
        # type: (str, bool, Optional[float]) -> Tuple[bool, Union[str, AuthenticationToken]]
        """  Login a user given a pin_code """
        user_orm = User.select().where(
            (User.pin_code == pin_code)
        ).first()

        if user_orm is None:
            return False, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS

        user_dto = UserMapper.orm_to_dto(user_orm)
        return self.login(user_dto, accept_terms=accept_terms, timeout=timeout, login_method=LoginMethod.PIN_CODE)

    def logout(self, token):
        self.token_store.remove_token(token)

    def check_token(self, token):
        # type: (Union[str, AuthenticationToken]) -> Optional[AuthenticationToken]
        return self.token_store.check_token(token)

    def remove_tokens_for_user(self, user_dto):
        self.token_store.remove_tokens_for_user(user_dto)

    def check_api_secret(self, api_secret):
        return self.api_secret == api_secret


@Injectable.named('token_store')
class TokenStore(object):

    @Inject
    def __init__(self, token_timeout=INJECTED):
        # type: (int) -> None
        self.token_timeout = token_timeout
        self.tokens = {}  # type: Dict[str, AuthenticationToken]

    def remove_token(self, token):
        if isinstance(token, AuthenticationToken):
            self._remove_token_str(token.token)
        else:
            self._remove_token_str(token)

    def _remove_token_str(self, token):
        # type: (str) -> None
        if token in self.tokens:
            del self.tokens[token]
        else:
            raise ItemDoesNotExistException('Token does not exist in the token store')

    def remove_tokens_for_user(self, user_dto):
        full_user = self._get_full_user_dto(user_dto)
        for token in list(self.tokens.values()):
            if token.user.id == full_user.id:
                del self.tokens[token.token]

    def create_token(self, user_dto, login_method, timeout=None, impersonator=None):
        # type: (UserDTO, LoginMethod, int, Optional[UserDTO]) -> AuthenticationToken
        """ Creates an authentication token, and needs the user code to do so """
        # Set the default timeout value
        if timeout is None:
            timeout = self.token_timeout

        full_user = self._get_full_user_dto(user_dto)

        generated_token = AuthenticationToken.generate(user_dto=full_user, token_timeout=timeout, impersonator=impersonator, login_method=login_method)
        token_id = generated_token.token
        self.tokens[token_id] = generated_token
        return self.tokens[token_id]

    def check_token(self, token):
        # type: (Union[str, AuthenticationToken]) -> Optional[AuthenticationToken]
        if isinstance(token, AuthenticationToken):
            return self._check_token_str(token.token)
        return self._check_token_str(token)

    def _check_token_str(self, token_str):
        # type: (str) -> Optional[AuthenticationToken]
        # clear all the expired tokens before checking the actual token
        for token in list(self.tokens.values()):
            if token.is_expired():
                del self.tokens[token.token]
        found_token = self.tokens.get(token_str, None)
        return found_token

    def _get_full_user_dto(self, user_dto):
        _ = self
        user_orm = User.select().where(
            (User.username == user_dto.username.lower())
        ).first()
        full_user_dto = UserMapper.orm_to_dto(user_orm)
        return full_user_dto


class AuthenticationToken(object):

    def __init__(self, user, token, expire_timestamp, login_method, impersonator=None):
        # type: (UserDTO, str, int, LoginMethod, Optional[UserDTO]) -> None
        self.user = user
        self.token = token
        self.expire_timestamp = expire_timestamp
        self.login_method = login_method
        self.impersonator = impersonator

    @staticmethod
    def generate(user_dto, login_method, token_timeout, impersonator=None):
        # type: (UserDTO, LoginMethod, int, Optional[UserDTO]) -> AuthenticationToken
        """ Creates an authentication token """
        if impersonator is not None and impersonator.role != User.UserRoles.SUPER:
            raise UnAuthorizedException("Cannot create an impersonated token for a non SUPER user")
        token = uuid.uuid4().hex
        auth_token = AuthenticationToken(user_dto, token, int(time.time()) + token_timeout, impersonator=impersonator, login_method=login_method)
        return auth_token

    def is_expired(self):
        now = time.time()
        return now > self.expire_timestamp

    def _get_user_id(self):
        # type: () -> int
        try:
            id_str = self.token.split('-')[0]
            id_int = int(id_str)
            return id_int
        except Exception as ex:
            raise RuntimeError('Could not get user id from token: {}'.format(ex))

    def to_dict(self):
        d = {
            'user_id': self.user.id,
            'user_role': self.user.role,
            'token': self.token,
            'login_method': self.login_method.value
        }
        if self.impersonator is not None:
            d['impersonator_id'] = self.impersonator.id
        return d

    def __repr__(self):
        return '<Auth Token: {}, username: {}, Expire_timestamp: {}>'.format(self.token, self.user.username, self.expire_timestamp)
