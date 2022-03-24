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
User Mapper
"""
from __future__ import absolute_import
import json
from gateway.dto import UserDTO
from gateway.models import User


class UserMapper(object):
    def __init__(self, db):
        self._db = db

    def orm_to_dto(self, orm_object):
        # type: (User) -> UserDTO
        _ = self
        user_dto = UserDTO(id=orm_object.id,
                           username=orm_object.username,
                           first_name=orm_object.first_name,
                           last_name=orm_object.last_name,
                           role=orm_object.role,
                           pin_code=orm_object.pin_code,
                           language=orm_object.language,
                           is_active=orm_object.is_active,
                           accepted_terms=orm_object.accepted_terms,
                           email=orm_object.email)
        # Copy over the hashed password from the database into the DTO
        user_dto.hashed_password = orm_object.password
        return user_dto

    def dto_to_orm(self, dto_object):
        # type: (UserDTO) -> User
        user_orm = self._db.query(User).where(User.username == dto_object.username).one_or_none()
        if user_orm is None:
            mandatory_fields = {'username'}
            if not mandatory_fields.issubset(set(dto_object.loaded_fields)):
                raise ValueError('Cannot create user without mandatory fields `{0}`\nGot fields: {1}\nDifference: {2}'
                                 .format('`, `'.join(mandatory_fields),
                                         dto_object.loaded_fields,
                                         mandatory_fields - set(dto_object.loaded_fields)))
            user_orm = User(username=dto_object.username.lower(),
                            accepted_terms=0)
            self._db.add(user_orm)

        # Set the default role to a normal user
        if dto_object.role is None:
            dto_object.role = User.UserRoles.USER  # set default role to USER when one is created

        # add the default value for the language to en
        if 'language' not in dto_object.loaded_fields and user_orm.language is None:
            user_orm.language = 'en'

        for field in dto_object.loaded_fields:
            if getattr(dto_object, field, None) is None:
                continue
            elif field == 'hashed_password':
                user_orm.password = dto_object.hashed_password
            elif field not in ['username', 'hashed_password']:
                setattr(user_orm, field, getattr(dto_object, field))
        return user_orm
