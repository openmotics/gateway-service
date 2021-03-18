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
eSafe (de)serializer
"""
from __future__ import absolute_import

import logging

from gateway.api.serializers.base import SerializerToolbox
from gateway.dto.esafe import EsafeUserDTO, RfidDTO, DeliveryDTO, ApartmentDTO
from toolbox import Toolbox

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple

logger = logging.getLogger('openmotics')

class ApartmentSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (ApartmentDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'name': dto_object.name,
                'mailbox_rebus_id': dto_object.mailbox_rebus_id,
                'doorbell_rebus_id': dto_object.doorbell_rebus_id}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> Tuple[ApartmentDTO, List[str]]
        loaded_fields = []
        apartment_id = None
        if 'id' in api_data:
            loaded_fields.append('id')
            apartment_id = api_data['id']
        name = ''
        if 'name' in api_data:
            loaded_fields.append('name')
            name = api_data['name']
        mailbox_rebus_id = None
        if 'mailbox_rebus_id' in api_data:
            loaded_fields.append('mailbox_rebus_id')
            mailbox_rebus_id = api_data['mailbox_rebus_id']
        doorbell_rebus_id = None
        if 'doorbell_rebus_id' in api_data:
            loaded_fields.append('doorbell_rebus_id')
            doorbell_rebus_id = api_data['doorbell_rebus_id']
        apartment_dto = ApartmentDTO(apartment_id, name, mailbox_rebus_id, doorbell_rebus_id)
        return apartment_dto, loaded_fields


class EsafeUserSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (EsafeUserDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'first_name': dto_object.first_name,
                'last_name': dto_object.last_name,
                'role': dto_object.role,
                'code': dto_object.code,
                'apartment': None}
        if fields is not None:
            if 'apartment' in fields:
                apartment_data = ApartmentSerializer.serialize(dto_object.apartment)
                data['apartment'] = apartment_data
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> Tuple[EsafeUserDTO, List[str]]
        loaded_fields = []
        user_id = None
        if 'id' in api_data:
            loaded_fields.append('id')
            user_id = api_data['id']
        user_dto = EsafeUserDTO(user_id)
        for field in ['first_name', 'last_name', 'role', 'code']:
            if field in api_data:
                loaded_fields.append(field)
                setattr(user_dto, field, api_data[field])
        if 'apartment' in api_data:
            apartment_dto, _ = ApartmentSerializer.deserialize(api_data['apartment'])
            user_dto.apartment = apartment_dto
            loaded_fields.append('apartment')
        return user_dto, loaded_fields


class RfidSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (RfidDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'tag_string': dto_object.tag_string,
                'uid_manufacturer': dto_object.uid_manufacturer,
                'uid_extension': dto_object.uid_extension,
                'enter_count': dto_object.enter_count,
                'blacklisted': dto_object.blacklisted,
                'label': dto_object.label,
                'timestamp_created': dto_object.timestamp_created,
                'timestamp_last_used': dto_object.timestamp_last_used,
                'user': None}
        user_data = EsafeUserSerializer.serialize(dto_object.user)
        data['user'] = user_data
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> Tuple[RfidDTO, List[str]]
        loaded_fields = []
        id = None
        if 'id' in api_data:
            loaded_fields.append('id')
            id = api_data['id']
        tag_string = ''
        if 'tag_string' in api_data:
            loaded_fields.append('tag_string')
            key = api_data['tag_string']
        uid_manu = None
        if 'uid_manufacturer' in api_data:
            loaded_fields.append('uid_manufacturer')
            uid_manu = api_data['uid_manufacturer']
        rfid_dto = RfidDTO(id, tag_string, uid_manu)
        for field in ['uid_extension', 'enter_count', 'blacklisted', 'label', 'timestamp_created', 'timestamp_last_used']:
            if field in api_data:
                loaded_fields.append(field)
                setattr(rfid_dto, field, api_data[field])
        if 'user' in api_data:
            loaded_fields.append('user')
            user_dto, _ = EsafeUserSerializer.deserialize(api_data['user'])
            rfid_dto.user = user_dto
        return rfid_dto, loaded_fields

class DeliverySerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (DeliveryDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'type': dto_object.type,
                'timestamp_delivery': dto_object.timestamp_delivery,
                'timestamp_pickup': dto_object.timestamp_pickup,
                'courier_firm': dto_object.courier_firm,
                'signature_delivery': dto_object.signature_delivery,
                'signature_pickup': dto_object.signature_pickup,
                'parcelbox_rebus_id': dto_object.parcelbox_rebus_id,
                'user_delivery': None,
                'user_pickup': None}
        user_data = EsafeUserSerializer.serialize(dto_object.user_delivery)
        data['user_delivery'] = user_data
        user_data = EsafeUserSerializer.serialize(dto_object.user_pickup)
        data['user_pickup'] = user_data
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> Tuple[DeliveryDTO, List[str]]
        loaded_fields = []
        id = None
        if 'id' in api_data:
            loaded_fields.append('id')
            id = api_data['id']
        type = ''
        if 'type' in api_data:
            loaded_fields.append('type')
            type = api_data['type']
        delivery_dto = DeliveryDTO(id, type)
        for field in ['timestamp_delivery', 'timestamp_pickup', 'courier_firm', 'signature_delivery', 'signature_pickup', 'parcelbox_rebus_id']:
            if field in api_data:
                loaded_fields.append(field)
                setattr(delivery_dto, field, api_data[field])
        if 'user_delivery' in api_data:
            loaded_fields.append('user_delivery')
            user_dto, _ = EsafeUserSerializer.deserialize(api_data['user_delivery'])
            delivery_dto.user_delivery = user_dto
        if 'user_pickup' in api_data:
            loaded_fields.append('user_pickup')
            user_dto, _ = EsafeUserSerializer.deserialize(api_data['user_pickup'])
            delivery_dto.user_pickup = user_dto
        return delivery_dto, loaded_fields

