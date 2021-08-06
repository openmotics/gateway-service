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

logger = logging.getLogger(__name__)

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
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    @Inject
    def deserialize(api_data, user_controller=INJECTED):
        # type: (Dict[str,Any], UserController) -> DeliveryDTO

        to_load_fields = ['id', 'type', 'timestamp_delivery', 'timestamp_pickup', 'courier_firm',
                          'signature_delivery', 'signature_pickup', 'parcelbox_rebus_id']
        delivery_dto_fields = {k: v for k, v in api_data.items() if k in to_load_fields}
        delivery_dto = DeliveryDTO(**delivery_dto_fields)

        if 'user_id_delivery' in api_data and api_data['user_id_delivery'] is not None:
            user_id = api_data['user_id_delivery']
            user_delivery_dto = user_controller.load_user(user_id)
            if user_delivery_dto is None:
                raise RuntimeError('user_id_delivery provided in the delivery json does not exists')
            delivery_dto.user_delivery = user_delivery_dto

        if 'user_id_pickup' in api_data and api_data['user_id_pickup'] is not None:
            user_id = api_data['user_id_pickup']
            user_pickup_dto = user_controller.load_user(user_id)
            if user_pickup_dto is None:
                raise RuntimeError('user_id_pickup provided in the delivery json does not exists')
            delivery_dto.user_pickup = user_pickup_dto

        if delivery_dto.type not in ['DELIVERY', 'RETURN']:
            raise ValueError('Field "type" has to be "DELIVERY" or "RETURN"')

        return delivery_dto

