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
Ventilation Mapper
"""
from __future__ import absolute_import

import logging

from gateway.dto.esafe import EsafeDeliveryDTO, EsafeRfidDTO, EsafeSystemDTO, EsafeApartmentDTO, EsafeUserDTO
from gateway.models import EsafeApartment, EsafeUser, EsafeRFID, EsafeSystem, EsafeDelivery

if False:  # MYPY
    from typing import Any, Dict, List

logger = logging.getLogger('openmotics')


class EsafeUserMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):
        # type: (EsafeUser) -> EsafeUserDTO
        apartment_orm = orm_object.apartment_id
        user_dto = EsafeUserDTO(orm_object.id,
                                orm_object.first_name,
                                orm_object.last_name,
                                orm_object.role,
                                orm_object.code,
                                None)
        if apartment_orm is not None:
            apartment_dto = EsafeApartmentMapper.orm_to_dto(apartment_orm)
            user_dto.apartment = apartment_dto

        return user_dto

    @staticmethod
    def dto_to_orm(dto_object, fields):
        # type: (EsafeUserDTO, List[str]) -> EsafeUser
        user = EsafeUser.get_or_none(first_name=dto_object.first_name,
                                     last_name=dto_object.last_name)
        if user is None:
            mandatory_fields = {'role', 'code', 'first_name', 'last_name'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create eSafe user without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))

        user_orm = EsafeUser()
        for field in fields:
            if getattr(user_orm, field, None) is None or getattr(user_orm, field, None) is None:
                continue
            if field == 'apartment_id':
                apartment_orm, _ = EsafeApartmentMapper.dto_to_orm(dto_object.apartment, ['id', 'name', 'mailbox_rebus_id', 'doorbell_rebus_id'])
                user_orm.apartment_id = apartment_orm
                continue
            setattr(user_orm, field, getattr(dto_object, field))
        return user_orm



class EsafeApartmentMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):
        # type: (EsafeApartment) -> EsafeApartmentDTO
        apartment_dto = EsafeApartmentDTO(orm_object.id,
                                          orm_object.name,
                                          orm_object.mailbox_rebus_id,
                                          orm_object.doorbell_rebus_id)
        return apartment_dto

    @staticmethod
    def dto_to_orm(dto_object, fields):
        # type: (EsafeApartmentDTO, List[str]) -> EsafeApartment
        apartment = EsafeUser.get_or_none(name=dto_object.name,
                                          mailbox_rebus_id=dto_object.mailbox_rebus_id,
                                          doorbell_rebus_id=dto_object.doorbell_rebus_id)
        if apartment is None:
            mandatory_fields = {'name', 'mailbox_rebus_id', 'doorbell_rebus_id'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create eSafe apartment without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))
        apartment_orm = EsafeApartment()
        for field in fields:
            if getattr(apartment_orm, field, None) is None or getattr(apartment_orm, field, None) is None:
                continue
            setattr(apartment_orm, field, getattr(dto_object, field))
        return apartment_orm


class EsafeDeliveryMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):
        # type: (EsafeDelivery) -> EsafeDeliveryDTO
        delivery_dto = EsafeDeliveryDTO(orm_object.id,
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
        # type: (EsafeDeliveryDTO, List[str]) -> EsafeDelivery
        delivery = EsafeDelivery.get_or_none(type=dto_object.type,
                                             user_id_delivery=dto_object.user_delivery.id,
                                             timestamp_delivery=dto_object.timestamp_delivery,
                                             parcelbox_rebus_id=dto_object.parcelbox_rebus_id)
        if delivery is None:
            mandatory_fields = {'type', 'timestamp_delivery', 'user_id_delivery', 'parcelbox_rebus_id'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create eSafe delivery without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))

        delivery_orm = EsafeDelivery()
        for field in fields:
            if getattr(delivery_orm, field, None) is None or getattr(delivery_orm, field, None) is None:
                continue
            if field == 'user_id_delivery':
                user_orm = EsafeUserMapper.dto_to_orm(dto_object.user_delivery, ['id', 'first_name', 'last_name', 'role', 'code', 'apartment_id'])
                delivery_orm.user_id_delivery = user_orm
                continue
            if field == 'user_id_pickup':
                user_orm = EsafeUserMapper.dto_to_orm(dto_object.user_delivery, ['id', 'first_name', 'last_name', 'role', 'code', 'apartment_id'])
                delivery_orm.user_id_pickup = user_orm
                continue
            setattr(delivery_orm, field, getattr(dto_object, field))
        return delivery_orm


class EsafeRfidMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):
        # type: (EsafeRFID) -> EsafeRfidDTO
        rfid_dto = EsafeRfidDTO(orm_object.id,
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
            user_dto = EsafeUserMapper.orm_to_dto(user_orm)
            rfid_dto.user = user_dto
        return rfid_dto

    @staticmethod
    def dto_to_orm(dto_object, fields):
        # type: (EsafeRfidDTO, List[str]) -> EsafeRFID
        esafe_rfid = EsafeRFID.get_or_none(tag_string=dto_object.tag_string)
        if esafe_rfid is None:
            mandatory_fields = {'tag_string', 'uid_manufacturer', 'enter_count', 'label', 'user_id'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create rfid without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))

        rfid_orm = EsafeRFID()
        for field in fields:
            if getattr(rfid_orm, field, None) is None or getattr(rfid_orm, field, None) is None:
                continue
            if field == 'user_id':
                user_orm = EsafeUserMapper.dto_to_orm(dto_object.user, ['id', 'first_name', 'last_name', 'role', 'code', 'apartment_id'])
                rfid_orm.user_id = user_orm
                continue
            setattr(rfid_orm, field, getattr(dto_object, field))
        return rfid_orm


class EsafeSystemMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):
        # type: (EsafeSystem) -> EsafeSystemDTO
        system_dto = EsafeSystemDTO(orm_object.key,
                                    orm_object.value)
        return system_dto

    @staticmethod
    def dto_to_orm(dto_object, fields):
        # type: (EsafeSystemDTO, List[str]) -> EsafeSystem
        esafe_system = EsafeSystem.get_or_none(key=dto_object.key)
        if esafe_system is None:
            mandatory_fields = {'key'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError('Cannot create system without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))

        system_orm = EsafeSystem()
        for field in fields:
            if getattr(system_orm, field, None) is None or getattr(system_orm, field, None) is None:
                continue
            setattr(system_orm, field, getattr(dto_object, field))
        return system_orm


