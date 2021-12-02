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

from gateway.api.serializers import DeliverySerializer
from gateway.dto import DeliveryDTO
from gateway.events import EsafeEvent
from gateway.models import Delivery, User
from gateway.mappers import DeliveryMapper
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Injectable, Singleton


if False:  # MyPy
    from typing import List, Optional, Dict, Any
    from gateway.user_controller import UserController
    from esafe.rebus.rebus_controller import RebusController

logger = logging.getLogger(__name__)


@Injectable.named('delivery_controller')
@Singleton
class DeliveryController(object):

    @Inject
    def __init__(self, user_controller=INJECTED, pubsub=INJECTED):
        # type: (UserController, PubSub) -> None
        self.user_controller = user_controller
        self.pubsub = pubsub
        self.rebus_controller = None  # type: Optional[RebusController]

    def set_rebus_controller(self, rebus_controller):
        # type: (Optional[RebusController]) -> None
        self.rebus_controller = rebus_controller

    @staticmethod
    def load_delivery(delivery_id, include_picked_up=False):
        # type: (int, bool) -> Optional[DeliveryDTO]
        if include_picked_up:
            delivery_orm = Delivery.select().where(Delivery.id == delivery_id).first()
        else:
            delivery_orm = Delivery.select().where(Delivery.id == delivery_id).where(Delivery.timestamp_pickup.is_null()).first()
        if delivery_orm is None:
            return None
        delivery_dto = DeliveryMapper.orm_to_dto(delivery_orm)
        return delivery_dto

    @staticmethod
    def load_deliveries(user_id=None, delivery_type=None, history=False, before_id=None, limit=100):
        # type: (Optional[int], Optional[str], bool, int, int) -> List[DeliveryDTO]
        deliveries = []
        query = Delivery.select()
        # filter on user id when needed
        if user_id is not None:
            query = query.where(
                ((Delivery.user_delivery_id == user_id) |
                 (Delivery.user_pickup_id == user_id))
            )
        # Filter on delivery type
        if delivery_type is not None:
            query = query.where(Delivery.type == delivery_type)
        # filter on picked up when needed
        if history is False:
            query = query.where(Delivery.timestamp_pickup.is_null(True))

        # add the from_id
        if before_id is not None:
            query = query.where(Delivery.id < before_id)

        # Add the limit
        query = query.limit(limit)

        # Sort on id
        query = query.order_by(-Delivery.id)  # sort by id descending

        for delivery_orm in query:
            delivery_dto = DeliveryMapper.orm_to_dto(delivery_orm)
            deliveries.append(delivery_dto)
        return deliveries

    @staticmethod
    def load_deliveries_filter(include_picked_up=False, **kwargs):
        # type: (bool, Dict[str, Any]) -> List[DeliveryDTO]
        query = Delivery.select()
        for arg, value in kwargs.items():
            if not arg.startswith('delivery_'):
                raise ValueError('Cannot filter on value that does not start with "delivery_"')
            field = arg.replace('delivery_', '')
            field_orm = getattr(Delivery, field, None)
            if field_orm is None:
                raise ValueError('Cannot filter deliveries on {}: Delivery does not contain that key'.format(field))
            query = query.where(field_orm == value)
        if not include_picked_up:
            query = query.where(Delivery.timestamp_pickup.is_null())
        deliveries = []
        for delivery_orm in query:
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
        ids = (x.id for x in deliveries)
        return delivery_id in ids

    def save_delivery(self, delivery_dto):
        # type: (DeliveryDTO) -> Optional[DeliveryDTO]
        if self.rebus_controller is not None:
            exists = self.rebus_controller.verify_device_exists(delivery_dto.parcelbox_rebus_id)
            if not exists:
                raise ValueError('Could not save the delivery, the parcelbox_id "{}" does not exists'.format(delivery_dto.parcelbox_rebus_id))
        else:
            raise RuntimeError('Cannot verify if parcelbox exists, not saving delivery')
        if delivery_dto.parcelbox_rebus_id is None:
            raise RuntimeError('Could not save the delivery since the parcelbox id is not defined')
        if not DeliveryController.parcel_id_available(delivery_dto.parcelbox_rebus_id, delivery_dto.id):
            raise RuntimeError('Could not save the delivery: parcelbox id is already in use')
        if 'timestamp_delivery' not in delivery_dto.loaded_fields:
            # save a default timestamp of now
            delivery_dto.timestamp_delivery = DeliveryController.current_timestamp_to_string_format()
        DeliveryController._validate_delivery_type(delivery_dto)

        delivery_orm = DeliveryMapper.dto_to_orm(delivery_dto)
        delivery_orm.save()
        delivery_dto_saved = DeliveryMapper.orm_to_dto(delivery_orm)
        if delivery_dto_saved.timestamp_pickup is None:
            event = EsafeEvent(EsafeEvent.Types.DELIVERY_CHANGE, {
                'id': delivery_orm.id,
                'action': 'DELIVERY',
                'delivery': DeliverySerializer.serialize(delivery_dto_saved)
            })
            self.pubsub.publish_esafe_event(PubSub.EsafeTopics.DELIVERY, event)
        return delivery_dto_saved

    @staticmethod
    def parcel_id_available(parcelbox_id, delivery_id=None):
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

    @classmethod
    def current_timestamp_to_string_format(cls):
        # type: () -> str
        timestamp = datetime.datetime.now(tzlocal())
        return cls.datetime_to_string_format(timestamp)

    def pickup_delivery(self, delivery_id):
        delivery_dto = DeliveryController.load_delivery(delivery_id, include_picked_up=True)
        if delivery_dto is None:
            raise RuntimeError('Cannot update the delivery with id {}: Delivery does not exists'.format(delivery_id))

        if delivery_dto.timestamp_pickup is not None:
            raise RuntimeError('Cannot update the delivery with id: {}: Delivery has already been picked up'.format(delivery_id))

        delivery_dto.timestamp_pickup = DeliveryController.current_timestamp_to_string_format()

        # first send the event to get the return_pickup_code if needed
        event = EsafeEvent(EsafeEvent.Types.DELIVERY_CHANGE, {
            'id': delivery_id,
            'action': 'PICKUP',
            'delivery': DeliverySerializer.serialize(delivery_dto),
        })
        self.pubsub.publish_esafe_event(PubSub.EsafeTopics.DELIVERY, event)

        # if applicable, delete the courier user in case it is an return
        # else, just save the delivery
        if delivery_dto.type == Delivery.DeliveryType.RETURN:
            pickup_user_dto = delivery_dto.user_pickup
            delivery_dto_saved = self.save_delivery(delivery_dto)
            self.user_controller.remove_user(pickup_user_dto)
        else:
            delivery_dto_saved = self.save_delivery(delivery_dto)

        return delivery_dto_saved

    @staticmethod
    def _validate_delivery_type(delivery_dto):
        # type: (DeliveryDTO) -> None
        if delivery_dto.type == Delivery.DeliveryType.RETURN:
            # Delivery needs a delivery user, otherwise it does not come from one of the local users
            if delivery_dto.user_delivery is None:
                raise ValueError('Delivery needs an delivery user when it is a return delivery')

            # Delivery needs a courier when it is not picked up, otherwise the user needs to be deleted.
            if delivery_dto.timestamp_pickup is None:
                # not picked up
                if delivery_dto.user_pickup is None or delivery_dto.user_pickup.role != User.UserRoles.COURIER:
                    raise ValueError('when the delivery is not picked up, the delivery needs a COURIER pickup user')
        else:
            if delivery_dto.user_delivery is not None:
                raise ValueError('Delivery cannot have a delivery user when the delivery is of type DELIVERY')
