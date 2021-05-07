# Copyright (C) 2021 OpenMotics BV
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
delivery controller manages the delivery objects that are known in the system
"""

import datetime
from dateutil.tz import tzlocal
import logging

from gateway.models import Delivery, User
from gateway.mappers import DeliveryMapper
from gateway.dto import DeliveryDTO
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MyPy
    from typing import List, Optional

logger = logging.getLogger('openmotics')


@Injectable.named('delivery_controller')
@Singleton
class DeliveryController(object):
    def __init__(self):
        pass

    @staticmethod
    def load_delivery(delivery_id):
        # type: (int) -> Optional[DeliveryDTO]
        delivery_orm = Delivery.select().where(Delivery.id == delivery_id).first()
        if delivery_orm is None:
            return None
        delivery_dto = DeliveryMapper.orm_to_dto(delivery_orm)
        return delivery_dto

    @staticmethod
    def load_deliveries():
        # type: () -> List[DeliveryDTO]
        deliveries = []
        for delivery_orm in Delivery.select():
            delivery_dto = DeliveryMapper.orm_to_dto(delivery_orm)
            deliveries.append(delivery_dto)
        return deliveries

    @staticmethod
    def get_delivery_count():
        # type: () -> int
        return Delivery.select().count()

    @staticmethod
    def delivery_id_exists(delivery_id):
        # type: (int) -> bool
        deliveries = DeliveryController.load_deliveries()
        ids = [x.id for x in deliveries]
        return delivery_id in ids

    @staticmethod
    def save_delivery(delivery_dto):
        # type: (DeliveryDTO) -> Optional[DeliveryDTO]
        # TODO: Check if parcelbox id exists!
        if delivery_dto.parcelbox_rebus_id is None:
            raise RuntimeError('Could not save the delivery since the parcelbox id is not defined')
        if not DeliveryController.parcel_id_available(delivery_dto.parcelbox_rebus_id, delivery_dto.id):
            raise RuntimeError('Could not save the delivery: parcelbox id is already in use')
        if 'timestamp_delivery' not in delivery_dto.loaded_fields:
            # save a default timestamp of now
            delivery_dto.timestamp_delivery = DeliveryController.current_timestamp_to_string_format()
        DeliveryController._validate_delivery_type(delivery_dto)

        delivery_orm = DeliveryMapper.dto_to_orm(delivery_dto)
        if delivery_orm.user_id_delivery is not None:
            delivery_orm.user_id_delivery.save()
        if delivery_orm.user_id_pickup is not None:
            delivery_orm.user_id_pickup.save()
        delivery_orm.save()
        return DeliveryMapper.orm_to_dto(delivery_orm)

    @staticmethod
    def parcel_id_available(parcelbox_id, delivery_id):
        if delivery_id is None:
            delivery_id = -1
        query = Delivery.select().where((Delivery.parcelbox_rebus_id == parcelbox_id) &
                                        (Delivery.timestamp_pickup.is_null()) &
                                        (Delivery.id != delivery_id))
        delivery_orm = query.first()
        return delivery_orm is None

    @staticmethod
    def datetime_to_string_format(timestamp):
        # type: (datetime.datetime) -> str
        # replace the microseconds to not show them in the string
        return timestamp.replace(microsecond=0).isoformat('T')

    @staticmethod
    def current_timestamp_to_string_format():
        # type: () -> str
        timestamp = datetime.datetime.now(tzlocal())
        # replace the microseconds to not show them in the string
        return timestamp.replace(microsecond=0).isoformat('T')

    @staticmethod
    def pickup_delivery(delivery_id):
        delivery_dto = DeliveryController.load_delivery(delivery_id)
        if delivery_dto is None:
            raise RuntimeError('Cannot update the delivery with id {}: Delivery does not exists'.format(delivery_id))

        if delivery_dto.timestamp_pickup is not None:
            raise RuntimeError('Cannot update the delivery with id: {}: Delivery has already been picked up'.format(delivery_id))

        delivery_dto.timestamp_pickup = DeliveryController.current_timestamp_to_string_format()
        return DeliveryController.save_delivery(delivery_dto)

    @staticmethod
    def _validate_delivery_type(delivery_dto):
        # type: (DeliveryDTO) -> None
        if delivery_dto.type == Delivery.DeliveryType.RETURN:
            # check that the pickup user is filled in and is an courier user
            if delivery_dto.user_delivery is None:
                raise ValueError('Delivery needs an pickup user when it is a return delivery')
            if delivery_dto.user_delivery.role is not User.UserRoles.COURIER:
                raise ValueError('Delivery should have a courier as a pickup user')
        else:
            if delivery_dto.user_delivery is not None:
                raise ValueError('Delivery cannot have a delivery user when the delivery is of type DELIVERY')
