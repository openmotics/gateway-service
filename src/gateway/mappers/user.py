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
Schedule Mapper
"""
from __future__ import absolute_import
import json
from gateway.dto import UserDTO
from gateway.models import User

if False:  # MYPY
    from typing import List, Optional, Any


class UserMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):  # type: (User) -> UserDTO
        return UserDTO(
            username=orm_object.username,
            password=orm_object.password,
            role=orm_object.role,
            enabled=orm_object.enabled,
            accepted_terms=orm_object.accepted_terms
        )

    @staticmethod
    def dto_to_orm(user_dto, fields):  # type: (UserDTO, List[str]) -> User
        # Look if there is a user in the DB to take over the unchanged fields
        user = User.get_or_none(username=user_dto.username)
        # if the user is non existing, create a new user with the mandatory fields that can be further filled with the user_dto fields
        if user is None:
            mandatory_fields = {'username', 'password', 'role', 'enabled'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create user without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))
            user = User(
                **{field: getattr(user_dto, field) for field in mandatory_fields}
            )
        for field in ['accepted_terms']:
            if field in fields:
                setattr(user, field, getattr(user_dto, field))
        
        # override or set the unset fields in the user object according to the fields from the user_dto field
        for field in vars(user):
            if field in fields:
                setattr(user, field, getattr(user_dto, field))

        return user
