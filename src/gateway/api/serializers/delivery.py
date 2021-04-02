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
delivery (de)serializer
"""
from __future__ import absolute_import

import logging

from gateway.api.serializers.base import SerializerToolbox
from gateway.api.serializers.user import UserSerializer
from gateway.dto.delivery import DeliveryDTO

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple

logger = logging.getLogger('openmotics')

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
        user_data = UserSerializer.serialize(dto_object.user_delivery)
        data['user_delivery'] = user_data
        if dto_object.user_pickup is not None:
            user_data = UserSerializer.serialize(dto_object.user_pickup)
            data['user_pickup'] = user_data
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> DeliveryDTO
        id = api_data.get('id')
        type = api_data.get('type')
        timestamp_delivery = api_data.get('timestamp_delivery')
        user_delivery_serial = api_data.get('user_delivery')
        user_delivery_dto = None
        if user_delivery_serial is not None:
            user_delivery_dto = UserSerializer.deserialize(user_delivery_serial)

        delivery_dto = DeliveryDTO(id, type, timestamp_delivery, user_delivery_dto)

        for field in ['timestamp_pickup', 'courier_firm', 'signature_delivery', 'signature_pickup', 'parcelbox_rebus_id']:
            if field in api_data:
                # loaded_fields.append(field)
                setattr(delivery_dto, field, api_data[field])
        if 'user_pickup' in api_data and api_data['user_pickup'] is not None:
            user_dto = UserSerializer.deserialize(api_data['user_pickup'])
            delivery_dto.user_pickup = user_dto
        return delivery_dto

