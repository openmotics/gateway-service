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
Apartment Mapper
"""
from __future__ import absolute_import

import logging

from gateway.dto.apartment import ApartmentDTO
from gateway.models import Apartment, User

logger = logging.getLogger('openmotics')


class ApartmentMapper(object):
    @staticmethod
    def orm_to_dto(orm_object):
        # type: (Apartment) -> ApartmentDTO
        apartment_dto = ApartmentDTO(orm_object.id,
                                     orm_object.name,
                                     orm_object.mailbox_rebus_id,
                                     orm_object.doorbell_rebus_id)
        return apartment_dto

    @staticmethod
    def dto_to_orm(dto_object):
        # type: (ApartmentDTO) -> Apartment
        apartment = Apartment.get_or_none(name=dto_object.name,
                                     mailbox_rebus_id=dto_object.mailbox_rebus_id,
                                     doorbell_rebus_id=dto_object.doorbell_rebus_id)
        if apartment is None:
            mandatory_fields = {'name', 'mailbox_rebus_id', 'doorbell_rebus_id'}
            if not mandatory_fields.issubset(set(dto_object.loaded_fields)):
                raise ValueError('Cannot create apartment without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))
        apartment_orm = Apartment()
        for field in dto_object.loaded_fields:
            if getattr(dto_object, field, None) is None:
                continue
            setattr(apartment_orm, field, getattr(dto_object, field))
        return apartment_orm
