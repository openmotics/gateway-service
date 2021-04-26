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
Delivery Mapper
"""
from __future__ import absolute_import

import logging

from gateway.dto.delivery import DeliveryDTO
from gateway.mappers.user import UserMapper
from gateway.models import Delivery

logger = logging.getLogger('openmotics')


class DeliveryMapper(object):
    @staticmethod
    def orm_to_dto(orm_object):
        # type: (Delivery) -> DeliveryDTO
        user_dto_delivery = None
        if orm_object.user_id_delivery is not None:
            user_dto_delivery = UserMapper.orm_to_dto(orm_object.user_id_delivery)
        user_dto_pickup = None
        if orm_object.user_id_pickup is not None:
            user_dto_pickup = UserMapper.orm_to_dto(orm_object.user_id_pickup)
        delivery_dto = DeliveryDTO(id=orm_object.id,
                                   type=orm_object.type,
                                   timestamp_delivery=orm_object.timestamp_delivery,
                                   timestamp_pickup=orm_object.timestamp_pickup,
                                   courier_firm=orm_object.courier_firm,
                                   signature_delivery=orm_object.signature_delivery,
                                   signature_pickup=orm_object.signature_pickup,
                                   parcelbox_rebus_id=orm_object.parcelbox_rebus_id,
                                   user_delivery=user_dto_delivery,
                                   user_pickup=user_dto_pickup)
        return delivery_dto

    @staticmethod
    def dto_to_orm(dto_object):
        # type: (DeliveryDTO) -> Delivery
        delivery = Delivery.get_or_none(type=dto_object.type,
                                        user_id_delivery=dto_object.user_id_delivery,
                                        timestamp_delivery=dto_object.timestamp_delivery,
                                        parcelbox_rebus_id=dto_object.parcelbox_rebus_id)
        if delivery is None:
            mandatory_fields = {'type', 'timestamp_delivery', 'user_id_delivery', 'parcelbox_rebus_id'}
            if not mandatory_fields.issubset(set(dto_object.loaded_fields)):
                raise ValueError('Cannot create delivery without mandatory fields `{0}`\nGot fields: {1}\nDifference: {2}'
                                 .format('`, `'.join(mandatory_fields),
                                         dto_object.loaded_fields,
                                         mandatory_fields - set(dto_object.loaded_fields)))

        delivery_orm = Delivery()
        for field in dto_object.loaded_fields:
            if getattr(dto_object, field, None) is None:
                continue
            if field == 'user_id_delivery' and dto_object.user_delivery is not None:
                user_orm = UserMapper.dto_to_orm(dto_object.user_delivery)
                delivery_orm.user_id_delivery = user_orm
                continue
            if field == 'user_id_pickup' and dto_object.user_pickup is not None:
                user_orm = UserMapper.dto_to_orm(dto_object.user_pickup)
                delivery_orm.user_id_pickup = user_orm
                continue
            setattr(delivery_orm, field, getattr(dto_object, field))
        return delivery_orm
