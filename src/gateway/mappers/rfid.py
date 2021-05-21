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
RFID object Mapper
"""
from __future__ import absolute_import

import logging

from gateway.dto.rfid import RfidDTO
from gateway.mappers.user import UserMapper
from gateway.models import RFID

logger = logging.getLogger(__name__)


class RfidMapper(object):
    @staticmethod
    def orm_to_dto(orm_object):
        # type: (RFID) -> RfidDTO
        rfid_dto = RfidDTO(orm_object.id,
                           orm_object.tag_string,
                           orm_object.uid_manufacturer,
                           orm_object.uid_extension,
                           orm_object.enter_count,
                           orm_object.blacklisted,
                           orm_object.label,
                           orm_object.timestamp_created,
                           orm_object.timestamp_last_used,
                           None)
        user_orm = orm_object.user_id
        if user_orm is not None:
            user_dto = UserMapper.orm_to_dto(user_orm)
            rfid_dto.user = user_dto
        return rfid_dto

    @staticmethod
    def dto_to_orm(dto_object):
        # type: (RfidDTO) -> RFID
        rfid = RFID.get_or_none(tag_string=dto_object.tag_string)
        if rfid is None:
            mandatory_fields = {'tag_string', 'uid_manufacturer', 'enter_count', 'label', 'user_id'}
            if not mandatory_fields.issubset(set(dto_object.loaded_fields)):
                raise ValueError('Cannot create rfid without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))

        rfid_orm = RFID()
        for field in dto_object.loaded_fields:
            if getattr(rfid_orm, field, None) is None or getattr(rfid_orm, field, None) is None:
                continue
            if field == 'user_id':
                user_orm = UserMapper.dto_to_orm(dto_object.user)
                rfid_orm.user_id = user_orm
                continue
            setattr(rfid_orm, field, getattr(dto_object, field))
        return rfid_orm
