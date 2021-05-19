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

from __future__ import absolute_import

import mock
import datetime
import unittest
from gateway.dto import DeliveryDTO, UserDTO
from gateway.mappers import DeliveryMapper
from gateway.models import Delivery
from gateway.api.serializers import DeliverySerializer


class DeliveryMapperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        pass


    def test_mapper(self):
        user_delivery = UserDTO(id=4, username='delivery user')
        user_pickup = UserDTO(id=5, username='pickup user')
        delivery_dto = DeliveryDTO(
            id=4,
            type='DELIVERY',
            timestamp_delivery='2020-10-07T15:28:19+02:00',
            timestamp_pickup='2020-10-07T15:28:42+02:00',
            user_delivery=user_delivery,
            user_pickup=user_pickup,
            courier_firm='BPost',
            parcelbox_rebus_id=37
        )

        print(delivery_dto)

        with mock.patch.object(Delivery, 'get_by_id', return_value=None):
            delivery_orm = DeliveryMapper.dto_to_orm(delivery_dto)
            self.assertEqual(delivery_dto.type, delivery_orm.type)
            self.assertEqual(delivery_dto.courier_firm, delivery_orm.courier_firm)
            self.assertEqual(delivery_dto.parcelbox_rebus_id, delivery_orm.parcelbox_rebus_id)
            self.assertEqual('2020-10-07T15:28:19+02:00', delivery_orm.timestamp_delivery)  # test that the time is converted to a string
            self.assertEqual('2020-10-07T15:28:42+02:00', delivery_orm.timestamp_pickup)  # test that the time is converted into a string
            delivery_dto_converted = DeliveryMapper.orm_to_dto(delivery_orm)
        print(delivery_orm)
        print(delivery_dto_converted)
        # ignore the users
        delivery_dto.user_delivery = None
        delivery_dto.user_pickup = None
        delivery_dto_converted.user_delivery = None
        delivery_dto_converted.user_pickup = None
        self.assertEqual(delivery_dto, delivery_dto_converted)
