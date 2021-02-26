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
from ioc import Injectable, Inject, Singleton, INJECTED

from gateway.models import EsafeUser
from gateway.mappers.esafe import EsafeUserMapper

if False:  # MYPY
    from typing import Tuple, List, Optional, Dict
    from gateway.dto.esafe import EsafeUserDTO


@Injectable.named('esafe_user_controller')
@Singleton
class EsafeUserController(object):
    """ The EsafeUserController provides methods for the creation and authentication of eSafe users. """

    @Inject
    def __init__(self):
        pass

    def load_user(self, user_id):
        _ = self
        user_orm = EsafeUser.select().where(EsafeUser.id == user_id).first()
        if user_orm is None:
            return None
        user_dto = EsafeUserMapper.orm_to_dto(user_orm)
        return user_dto

    def load_users(self):
        # type: () -> List[EsafeUserDTO]
        _ = self
        users = []
        for user in EsafeUser.select():
            user_dto = EsafeUserMapper.orm_to_dto(user)
            users.append(user_dto)
        return users

    def save_user(self, user_dto):
        pass
