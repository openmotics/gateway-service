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
from gateway.mappers.apartment import ApartmentMapper

if False:  # MYPY
    from typing import List, Optional, Any

class UserMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):
        # type: (User) -> UserDTO
        user_dto = UserDTO(id=orm_object.id,
                           first_name=orm_object.first_name,
                           last_name=orm_object.last_name,
                           role=orm_object.role,
                           pin_code=orm_object.pin_code,
                           apartment_dto=None,
                           accepted_terms=orm_object.accepted_terms)
        try:
            apartment_orm = orm_object.apartment_id
            if apartment_orm is not None:
                apartment_dto = ApartmentMapper.orm_to_dto(apartment_orm)
                user_dto.apartment = apartment_dto
        except:
            pass
        # Copy over the hashed password from the database into the DTO
        user_dto.hashed_password = orm_object.password
        return user_dto

    @staticmethod
    def dto_to_orm(dto_object, fields):
        # type: (UserDTO, List[str]) -> User
        user = User.get_or_none(first_name=dto_object.first_name,
                                last_name=dto_object.last_name)
        if user is None:
            mandatory_fields = {'role', 'pin_code', 'first_name', 'last_name', 'password'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create user without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))

        user_orm = User()
        user_orm.password = dto_object.hashed_password
        user_orm.username_old = dto_object.username
        for field in fields:
            if getattr(dto_object, field, None) is None:
                continue
            if field == 'apartment_id' and dto_object.apartment is not None:
                apartment_orm, _ = ApartmentMapper.dto_to_orm(dto_object.apartment, ['id', 'name', 'mailbox_rebus_id', 'doorbell_rebus_id'])
                user_orm.apartment_id = apartment_orm
                continue
            setattr(user_orm, field, getattr(dto_object, field))
        return user_orm
