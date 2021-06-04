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

import json
import time
import uuid

import constants
from ioc import Injectable, Inject, Singleton, INJECTED
from gateway.dto import UserDTO, RfidDTO
from gateway.enums import UserEnums
from gateway.exceptions import ItemDoesNotExistException
from gateway.mappers.user import UserMapper
from gateway.models import User, RFID
from gateway.rfid_controller import RfidController


if False:  # MYPY
    from typing import Tuple, List, Optional, Dict, Union
    from gateway.user_controller import UserController


@Injectable.named('authentication_controller')
class AuthenticationController(object):
    TERMS_VERSION = 1

    @Inject
    def __init__(self, token_timeout=INJECTED, token_store=INJECTED, rfid_controller=INJECTED):
        # type: (int, TokenStore, RfidController) -> None
        self._rfid_controller = rfid_controller
        self._token_timeout = token_timeout
        self.token_store = token_store  # type: TokenStore
        self.api_secret = AuthenticationController._retrieve_api_secret()

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

    def login(self, user_dto, accept_terms=False, timeout=None):
        # type: (UserDTO, bool, Optional[float]) -> Tuple[bool, Union[str, AuthenticationToken]]
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
            (User.username == user_dto.username.lower()) &
            (User.password == user_dto.hashed_password)
        ).first()

        if user_orm is None:
            return False, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS

        if user_orm.accepted_terms == AuthenticationController.TERMS_VERSION:
            token = self.token_store.create_token(UserMapper.orm_to_dto(user_orm), timeout=timeout)
            return True, token
        if accept_terms is True:
            user_orm.accepted_terms = AuthenticationController.TERMS_VERSION
            user_orm.save()
            token = self.token_store.create_token(UserMapper.orm_to_dto(user_orm), timeout=timeout)
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
        return self.login(user_dto, accept_terms=accept_terms, timeout=timeout)

    def login_with_rfid_tag(self, rfid_tag_string, accept_terms=False, timeout=None):
        # type: (str, bool, Optional[float]) -> Tuple[bool, Union[str, AuthenticationToken]]
        """  Login a user given a UserDTO """
        # rfid_orm = RFID.select().where(RFID.tag_string == rfid_tag_string).first()  # type: RFID
        # if rfid_orm is None:
        #     return False, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS
        # user_orm = rfid_orm.user
        # user_dto = UserMapper.orm_to_dto(user_orm)
        rfid_dto = self._rfid_controller.check_rfid_tag_for_login(rfid_tag_string)
        if rfid_dto is None:
            return False, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS
        return self.login(rfid_dto.user, accept_terms=accept_terms, timeout=timeout)

    def logout(self, token):
        self.token_store.remove_token(token)

    def check_token(self, token):
        return self.token_store.check_token(token)

    def remove_token_for_user(self, user_dto):
        self.token_store.remove_token_for_user(user_dto)

    def check_api_secret(self, api_secret):
        return self.api_secret == api_secret


@Injectable.named('token_store')
class TokenStore(object):

    @Inject
    def __init__(self, token_timeout=INJECTED):
        # type: (int) -> None
        self.token_timeout = token_timeout
        self.tokens = {}  # type: Dict[int, AuthenticationToken]  # user_id, authToken

    def has_user_token(self, user_id):
        return user_id in self.tokens

    def remove_token(self, token):
        if isinstance(token, AuthenticationToken):
            self._remove_token(token)
        else:
            self._remove_token_str(token)

    def _remove_token(self, token):
        # type: (AuthenticationToken) -> None
        user_id = token.user.id
        if user_id in self.tokens:
            del self.tokens[user_id]
        else:
            raise ItemDoesNotExistException('Token does not exist in the token store')

    def _remove_token_str(self, token):
        # type: (str) -> None
        found = False
        for user_id, auth_token in dict(self.tokens).items():
            if auth_token.token == token:
                del self.tokens[user_id]
                found = True
        if not found:
            raise ItemDoesNotExistException('Token does not exist in the token store')

    def remove_token_for_user(self, user_dto):
        full_user = self._get_full_user_dto(user_dto)
        user_id = full_user.id
        if user_id in self.tokens:
            del self.tokens[user_id]

    def create_token(self, user_dto, timeout=None):
        # type: (UserDTO, int) -> AuthenticationToken
        """ Creates an authentication token, and needs the user code to do so """
        full_user = self._get_full_user_dto(user_dto)
        user_id = full_user.id
        # if there is already a token, just return the existing token
        if user_id in self.tokens:
            return self.tokens[user_id]
        if timeout is not None:
            self.tokens[user_id] = AuthenticationToken.generate(full_user, token_timeout=timeout)
        else:
            self.tokens[user_id] = AuthenticationToken.generate(full_user)
        return self.tokens[user_id]

    def check_token(self, token):
        if isinstance(token, AuthenticationToken):
            return self._check_token_str(token.token)
        return self._check_token_str(token)

    def _check_token_str(self, token_str):
        # type: (str) -> Optional[AuthenticationToken]
        for user_id, token in dict(self.tokens).items():
            if token.token == token_str:
                if not token.is_expired():
                    return token
                else:
                    self.remove_token(token)
        return None

    def _get_full_user_dto(self, user_dto):
        _ = self
        user_orm = User.select().where(
            (User.username == user_dto.username.lower())
        ).first()
        full_user_dto = UserMapper.orm_to_dto(user_orm)
        return full_user_dto


class AuthenticationToken(object):
    def __init__(self, user, token, expire_timestamp):
        # type: (UserDTO, str, int) -> None
        self.user = user
        self.token = token
        self.expire_timestamp = expire_timestamp

    @staticmethod
    def generate(user_dto, token_timeout=INJECTED):
        # type: (UserDTO, int) -> AuthenticationToken
        """ Creates an authentication token """
        # TBD: Use the old style of tokens, or the shorter style that include the user_id
        # user_id = user_dto.id
        # token_postfix = uuid.uuid4().hex[:14]
        # token = "{}-{}".format(user_id, token_postfix)
        token = uuid.uuid4().hex
        auth_token = AuthenticationToken(user_dto, token, int(time.time()) + token_timeout)
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
        return {
            'user_id': self.user.id,
            'user_role': self.user.role,
            'token': self.token
        }

    def __repr__(self):
        return '<Auth Token: {}, username: {}, Expire_timestamp: {}>'.format(self.token, self.user.username, self.expire_timestamp)

