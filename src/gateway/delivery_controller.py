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
import logging

from gateway.models import Delivery
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
        delivery_orm = DeliveryMapper.dto_to_orm(delivery_dto)
        delivery_orm.save()
        return DeliveryController.load_delivery(delivery_orm.id)

    @staticmethod
    def update_delivery(delivery_dto):
        # type: (DeliveryDTO) -> Optional[DeliveryDTO]
        if 'id' not in delivery_dto.loaded_fields or delivery_dto.id is None:
            raise RuntimeError('cannot update an delivery without the id being set')
        try:
            delivery_orm = Delivery.select().where(Delivery.id == delivery_dto.id).first()
            for field in delivery_dto.loaded_fields:
                if field == 'id':
                    continue
                if hasattr(delivery_orm, field):
                    setattr(delivery_orm, field, getattr(delivery_dto, field))
            delivery_orm.save()
        except Exception as e:
            raise RuntimeError('Could not update the user: {}'.format(e))
        return DeliveryController.load_delivery(delivery_dto.id)

    @staticmethod
    def delete_delivery(delivery_dto):
        # type: (DeliveryDTO) -> None
        if "id" in delivery_dto.loaded_fields and delivery_dto.id is not None:
            Delivery.delete_by_id(delivery_dto.id)
        else:
            raise RuntimeError('Could not find an delivery with the id {} to delete'.format(delivery_dto.id))
        return

