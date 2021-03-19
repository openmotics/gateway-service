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
eSafe object Mapper
"""
from __future__ import absolute_import

import logging

from gateway.dto.esafe import DeliveryDTO, RfidDTO, ApartmentDTO
from gateway.mappers.user import UserMapper
from gateway.models import Apartment, User, RFID, Delivery

if False:  # MYPY
    from typing import Any, Dict, List

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
    def dto_to_orm(dto_object, fields):
        # type: (ApartmentDTO, List[str]) -> Apartment
        apartment = User.get_or_none(name=dto_object.name,
                                          mailbox_rebus_id=dto_object.mailbox_rebus_id,
                                          doorbell_rebus_id=dto_object.doorbell_rebus_id)
        if apartment is None:
            mandatory_fields = {'name', 'mailbox_rebus_id', 'doorbell_rebus_id'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create apartment without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))
        apartment_orm = Apartment()
        for field in fields:
            if getattr(apartment_orm, field, None) is None or getattr(apartment_orm, field, None) is None:
                continue
            setattr(apartment_orm, field, getattr(dto_object, field))
        return apartment_orm


class DeliveryMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):
        # type: (Delivery) -> DeliveryDTO
        delivery_dto = DeliveryDTO(orm_object.id,
                                        orm_object.type,
                                        orm_object.timestamp_delivery,
                                        orm_object.timestamp_pickup,
                                        orm_object.courier_firm,
                                        orm_object.signature_delivery,
                                        orm_object.signature_pickup,
                                        orm_object.parcelbox_rebus_id,
                                        orm_object.user_id_delivery,
                                        orm_object.user_id_pickup)
        return delivery_dto

    @staticmethod
    def dto_to_orm(dto_object, fields):
        # type: (DeliveryDTO, List[str]) -> Delivery
        delivery = Delivery.get_or_none(type=dto_object.type,
                                        user_id_delivery=dto_object.user_delivery.id,
                                        timestamp_delivery=dto_object.timestamp_delivery,
                                        parcelbox_rebus_id=dto_object.parcelbox_rebus_id)
        if delivery is None:
            mandatory_fields = {'type', 'timestamp_delivery', 'user_id_delivery', 'parcelbox_rebus_id'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create delivery without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))

        delivery_orm = Delivery()
        for field in fields:
            if getattr(delivery_orm, field, None) is None or getattr(delivery_orm, field, None) is None:
                continue
            if field == 'user_id_delivery':
                user_orm = UserMapper.dto_to_orm(dto_object.user_delivery, ['id', 'first_name', 'last_name', 'role', 'code', 'apartment_id'])
                delivery_orm.user_id_delivery = user_orm
                continue
            if field == 'user_id_pickup':
                user_orm = UserMapper.dto_to_orm(dto_object.user_delivery, ['id', 'first_name', 'last_name', 'role', 'code', 'apartment_id'])
                delivery_orm.user_id_pickup = user_orm
                continue
            setattr(delivery_orm, field, getattr(dto_object, field))
        return delivery_orm


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
        user_orm=  orm_object.user_id
        if user_orm is not None:
            user_dto = UserMapper.orm_to_dto(user_orm)
            rfid_dto.user = user_dto
        return rfid_dto

    @staticmethod
    def dto_to_orm(dto_object, fields):
        # type: (RfidDTO, List[str]) -> RFID
        rfid = RFID.get_or_none(tag_string=dto_object.tag_string)
        if rfid is None:
            mandatory_fields = {'tag_string', 'uid_manufacturer', 'enter_count', 'label', 'user_id'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create rfid without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))

        rfid_orm = RFID()
        for field in fields:
            if getattr(rfid_orm, field, None) is None or getattr(rfid_orm, field, None) is None:
                continue
            if field == 'user_id':
                user_orm = UserMapper.dto_to_orm(dto_object.user, ['id', 'first_name', 'last_name', 'role', 'code', 'apartment_id'])
                rfid_orm.user_id = user_orm
                continue
            setattr(rfid_orm, field, getattr(dto_object, field))
        return rfid_orm
