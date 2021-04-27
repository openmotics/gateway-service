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


class UserMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):
        # type: (User) -> UserDTO
        user_dto = UserDTO(id=orm_object.id,
                           first_name=orm_object.first_name,
                           last_name=orm_object.last_name,
                           role=orm_object.role,
                           pin_code=orm_object.pin_code,
                           apartment=None,
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
    def dto_to_orm(dto_object):
        # type: (UserDTO) -> User
        user = User.get_or_none(first_name=dto_object.first_name,
                                last_name=dto_object.last_name)
        if user is None:
            mandatory_fields = {'role', 'pin_code', 'first_name', 'last_name', 'password'}
            if not mandatory_fields.issubset(set(dto_object.loaded_fields)):
                raise ValueError('Cannot create user without mandatory fields `{0}`\nGot fields: {1}\nDifference: {2}'
                                 .format('`, `'.join(mandatory_fields),
                                         dto_object.loaded_fields,
                                         mandatory_fields - set(dto_object.loaded_fields)))

        user_orm = User(password=dto_object.hashed_password)
        if dto_object.role is None:
            dto_object.role = User.UserRoles.ADMIN  # set default role to admin when one is created
        for field in dto_object.loaded_fields:
            if getattr(dto_object, field, None) is None:
                continue
            if field == 'apartment_id' and dto_object.apartment is not None:
                apartment_orm = ApartmentMapper.dto_to_orm(dto_object.apartment)
                user_orm.apartment_id = apartment_orm
                continue
            if field not in ['password']:
                setattr(user_orm, field, getattr(dto_object, field))
        return user_orm
