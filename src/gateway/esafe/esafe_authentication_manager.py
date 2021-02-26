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
eSafe authentication manager manages logged in users in the system. This is separate from the
default gateway authentciation system
"""

from __future__ import absolute_import

import time
import uuid


from ioc import Injectable, Inject, Singleton, INJECTED

from gateway.esafe.esafe_user_controller import EsafeUserController
from gateway.esafe.esafe_exception import EsafeItemDoesNotExistError, EsafeWrongInputParametersError, EsafeError

if False:  # MYPY
    from typing import Tuple, List, Optional, Dict
    from gateway.dto.esafe import EsafeUserDTO

class EsafeUserAuth:
    USER = 'USER'
    ADMIN = 'ADMIN'
    TECHNICIAN = 'TECHNICIAN'
    COURIER = 'COURIER'

@Injectable.named('esafe_token_store')
class EsafeTokenStore(object):

    @Inject
    def __init__(self, esafe_user_controller=INJECTED, esafe_token_timeout=INJECTED):
        # type: (EsafeUserController, int) -> None
        self.user_controller = esafe_user_controller
        self.token_timeout = esafe_token_timeout
        self.tokens = {}  # type: Dict[int, EsafeAuthenticationToken]

    def add_token(self, token):
        # type: (EsafeAuthenticationToken) -> None
        user_id = token.user.id
        if user_id not in self.tokens:
            self.tokens[user_id] = token

    def has_user_token(self, user_id):
        return (user_id in self.tokens)

    def remove_token(self, token):
        # type: (EsafeAuthenticationToken) -> None
        user_id = token.user.id
        if user_id in self.tokens:
            del self.tokens[user_id]
        else:
            raise EsafeItemDoesNotExistError('Token does not exist in the token store')

    def generate_token(self, user_dto):
        # type: (EsafeUserDTO) -> EsafeAuthenticationToken
        """ Creates a eSafe authentication token, and needs the user code to do so"""
        user_db_dto = self.user_controller.load_user(code=user_dto.code)
        user_id = user_db_dto.id
        # if there is already a token, just return the existing token
        if user_id in self.tokens:
            return self.tokens[user_id]
        token_postfix = uuid.uuid4().hex[:14]
        token = "{}-{}".format(user_id, token_postfix)
        self.tokens[user_id] = EsafeAuthenticationToken(user_dto, token, int(time.time()) + self.token_timeout)
        return self.tokens[user_id]

    def check_token(self, token_str):
        # type: (str) -> Optional[EsafeAuthenticationToken]
        for user_id, esafe_token in self.tokens.items():
            if esafe_token.token == token_str:
                if not esafe_token.is_expired():
                    return esafe_token
                else:
                    self.remove_token(esafe_token)
        return None


class EsafeAuthenticationToken(object):
    def __init__(self, user, token, expire_timestanp):
        # type: (EsafeUserDTO, str, int) -> None
        self.user = user
        self.token = token
        self.expire_timestamp = expire_timestanp

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
            raise EsafeError('Could not get user id from token: {}'.format(ex))


@Injectable.named('esafe_user_controller')
@Singleton
class EsafeAuthenticationController(object):
    """ The EsafeUserController provides methods for the creation and authentication of eSafe users. """

    @Inject
    def __init__(self, esafe_user_controller=INJECTED, esafe_token_store=INJECTED):
        # type: (EsafeUserController, EsafeTokenStore) -> None
        self.user_controller = esafe_user_controller
        # Token == Tuple of token itself + valid until timestamp (unix style)
        self.token_store = esafe_token_store

    def login(self, user_dto):
        # type: (EsafeUserDTO) -> Optional[EsafeAuthenticationToken]
        user_in_db = self.user_controller.load_user(code=user_dto.code)
        if user_in_db is None:
            return None
        if not self.token_store.has_user_token(user_dto.id):
            token = self.token_store.generate_token(user_dto)
            return token
        return None

    def check_token(self, token_str):
        return self.token_store.check_token(token_str)






