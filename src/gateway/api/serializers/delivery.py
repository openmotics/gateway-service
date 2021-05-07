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
from gateway.dto import DeliveryDTO, UserDTO
from ioc import Inject, INJECTED

if False:  # MYPY
    from gateway.user_controller import UserController
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
                'user_id_delivery': dto_object.user_delivery.id if dto_object.user_delivery is not None else None,
                'user_id_pickup': dto_object.user_pickup.id if dto_object.user_pickup is not None else None}
        # if dto_object.user_delivery is not None:
        #     user_data = UserSerializer.serialize(dto_object.user_delivery)
        #     data['user_delivery'] = user_data
        # if dto_object.user_pickup is not None:
        #     user_data = UserSerializer.serialize(dto_object.user_pickup)
        #     data['user_pickup'] = user_data
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    @Inject
    def deserialize(api_data, user_controller=INJECTED):
        # type: (Dict[str,Any], UserController) -> DeliveryDTO

        delivery_dto = DeliveryDTO()
        for field in ['id', 'type', 'timestamp_delivery', 'timestamp_pickup', 'courier_firm',
                      'signature_delivery', 'signature_pickup', 'parcelbox_rebus_id']:
            if field in api_data:
                setattr(delivery_dto, field, api_data[field])

        if 'user_id_delivery' in api_data and api_data['user_id_delivery'] is not None:
            user_id = api_data['user_id_delivery']
            if user_controller.user_id_exists(user_id):
                user_delivery_dto = user_controller.load_user(user_id)
            else:
                raise RuntimeError('user_id_delivery provided in the delivery json does not exists')
            delivery_dto.user_delivery = user_delivery_dto

        if 'user_id_pickup' in api_data and api_data['user_id_pickup'] is not None:
            user_id = api_data['user_id_pickup']
            if user_controller.user_id_exists(user_id):
                user_pickup_dto = user_controller.load_user(user_id)
            else:
                raise RuntimeError('user_id_pickup provided in the delivery json does not exists')
            delivery_dto.user_pickup = user_pickup_dto

        if delivery_dto.type not in ['DELIVERY', 'RETURN']:
            raise ValueError('Field "type" has to be "DELIVERY" or "RETURN"')

        required_fields = ['type', 'parcelbox_rebus_id', 'user_pickup']
        for field in required_fields:
            if field not in delivery_dto.loaded_fields:
                raise ValueError('Field "{}" has not been specified to create a new delivery'.format(field))

        if delivery_dto.type == 'DELIVERY':
            if 'courier_firm' not in delivery_dto.loaded_fields:
                raise ValueError('Field "{}" has been specified to create a new delivery'.format('courier_firm'))
        else:
            if 'user_delivery' not in delivery_dto.loaded_fields:
                raise ValueError('Field "{}" has been specified to create a new delivery'.format('user_id_delivery'))


        return delivery_dto

