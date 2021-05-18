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
Tests for the delivery module.
"""

from __future__ import absolute_import
import unittest

from peewee import SqliteDatabase

from gateway.dto import DeliveryDTO, UserDTO
from gateway.mappers import UserMapper, DeliveryMapper
from gateway.models import Delivery, User
from gateway.delivery_controller import DeliveryController
from ioc import SetTestMode

MODELS = [Delivery, User]

class DeliveryControllerTest(unittest.TestCase):
    """ Tests for DeliveryController. """

    @classmethod
    def setUpClass(cls):
        super(DeliveryControllerTest, cls).setUpClass()
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    @classmethod
    def tearDownClass(cls):
        super(DeliveryControllerTest, cls).tearDownClass()

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.controller = DeliveryController

        self.test_user_1 = UserDTO(
            username='test_user_1',
            role='ADMIN'
        )
        self.test_user_1.set_password('test')

        self.test_user_2 = UserDTO(
            username='test_user_2',
            role='USER'
        )
        self.test_user_2.set_password('test')

        self.test_user_3 = UserDTO(
            username='test_user_3',
            role='COURIER'
        )
        self.test_user_3.set_password('test')

        self.test_delivery_1 = DeliveryDTO(
            type='DELIVERY',
            parcelbox_rebus_id=1,
            user_pickup=self.test_user_1
        )

        self.test_delivery_2 = DeliveryDTO(
            type='DELIVERY',
            parcelbox_rebus_id=2,
            user_pickup=self.test_user_2
        )

        self.test_return_1 = DeliveryDTO(
            type='RETURN',
            parcelbox_rebus_id=10,
            user_pickup=self.test_user_2,
            user_delivery=self.test_user_3
        )

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def assert_deliveries_equal(self, expected, tester):
        # type: (DeliveryDTO, DeliveryDTO) -> None
        _ = self
        # only test one of the 2 to be not none, otherwise test could pass, but should fail
        if expected.user_delivery is not None:
            self.assertEqual(expected.user_delivery.username, tester.user_delivery.username)

        if expected.user_pickup is not None:
            self.assertEqual(expected.user_pickup.username, tester.user_pickup.username)

        for field in expected.loaded_fields:
            if field not in ['user_delivery', 'user_pickup']:
                self.assertEqual(getattr(expected, field), getattr(tester, field))

    def assert_delivery_in_db(self, delivery_id, delivery_dto):
        # type: (int, DeliveryDTO) -> None
        delivery_orm = Delivery.select().where(Delivery.id == delivery_id).first()
        for field in delivery_dto.loaded_fields:
            if field == 'user_delivery':
                if delivery_dto.user_delivery is not None:
                    self.assertEqual(delivery_dto.user_delivery.username, delivery_orm.user_id_delivery.username)
                else:
                    self.assertIsNone(delivery_orm.user_id_delivery)
            elif field == 'user_pickup':
                if delivery_dto.user_pickup is not None:
                    self.assertEqual(delivery_dto.user_pickup.username, delivery_orm.user_id_pickup.username)
                else:
                    self.assertIsNone(delivery_orm.user_id_pickup)
            else:
                self.assertEqual(getattr(delivery_dto, field),
                                 getattr(delivery_orm, field))

    def test_create_delivery(self):
        """ Test the create delivery functionality """
        result = self.controller.save_delivery(self.test_delivery_1)
        self.assertEqual(1, Delivery.select().count())

        delivery_orm = Delivery.select().first()
        self.assertEqual(self.test_delivery_1.type, delivery_orm.type)
        self.assertEqual(self.test_delivery_1.parcelbox_rebus_id, delivery_orm.parcelbox_rebus_id)
        self.assertEqual(self.test_delivery_1.user_pickup.username, delivery_orm.user_id_pickup.username)
        self.test_delivery_1.id = result.id
        self.assert_deliveries_equal(self.test_delivery_1, result)
        self.assert_delivery_in_db(result.id, self.test_delivery_1)

    def test_create_delivery_multiple(self):
        """ Test the create delivery functionality """
        result_1 = self.controller.save_delivery(self.test_delivery_1)
        self.assertEqual(1, Delivery.select().count())
        self.assertEqual(1, User.select().count())

        result_2 = self.controller.save_delivery(self.test_delivery_2)
        self.assertEqual(2, Delivery.select().count())
        self.assertEqual(2, User.select().count())

        result_3 = self.controller.save_delivery(self.test_return_1)
        self.assertEqual(3, Delivery.select().count())
        self.assertEqual(3, User.select().count())

        self.assert_deliveries_equal(self.test_delivery_1, result_1)
        self.assert_deliveries_equal(self.test_delivery_2, result_2)
        self.assert_deliveries_equal(self.test_return_1, result_3)
        self.assert_delivery_in_db(result_1.id, self.test_delivery_1)
        self.assert_delivery_in_db(result_2.id, self.test_delivery_2)
        self.assert_delivery_in_db(result_3.id, self.test_return_1)

    def test_create_delivery_multiple_rebus_id_taken(self):
        """ Test the create delivery functionality """
        result_1 = self.controller.save_delivery(self.test_delivery_1)
        self.assertEqual(1, Delivery.select().count())

        # Set the same rebus id, should fail!
        self.test_delivery_2.parcelbox_rebus_id = self.test_delivery_1.parcelbox_rebus_id
        with self.assertRaises(RuntimeError):
            self.controller.save_delivery(self.test_delivery_2)
            
        self.assertEqual(1, Delivery.select().count())

    def test_create_delivery_multiple_rebus_id_taken(self):
        """ Test the create delivery functionality """
        result_1 = self.controller.save_delivery(self.test_delivery_1)
        self.assertEqual(1, Delivery.select().count())

        # Set the same rebus id, should fail!
        self.test_delivery_2.parcelbox_rebus_id = self.test_delivery_1.parcelbox_rebus_id
        with self.assertRaises(RuntimeError):
            self.controller.save_delivery(self.test_delivery_2)

        self.assertEqual(1, Delivery.select().count())

    def test_create_delivery_no_user_defined(self):
        """ Test the create delivery functionality """
        delivery_no_user_dto = DeliveryDTO(
            type='DELIVERY',
            timestamp_delivery='2021-05-07T10:10:04+02:00',
            parcelbox_rebus_id=37
        )
        with self.assertRaises(ValueError):
            self.controller.save_delivery(delivery_no_user_dto)

    def test_create_delivery_return_to_non_courier(self):
        """ Test the create delivery functionality """
        # set the pickup user to be a non courier
        self.test_return_1.user_pickup = self.test_user_1
        self.test_return_1.user_delivery = self.test_user_2
        with self.assertRaises(ValueError):
            self.controller.save_delivery(self.test_return_1)

    def test_pickup_delivery(self):
        result_1 = self.controller.save_delivery(self.test_delivery_1)
        result_2 = self.controller.save_delivery(self.test_delivery_2)
        delivery_1_id = result_1.id
        delivery_2_id = result_2.id

        result = self.controller.pickup_delivery(delivery_1_id)
        self.assertIsNotNone(result.timestamp_pickup)

        delivery_1_orm = Delivery.get_by_id(delivery_1_id)
        self.assertIsNotNone(delivery_1_orm.timestamp_pickup)
        delivery_2_orm = Delivery.get_by_id(delivery_2_id)
        self.assertIsNone(delivery_2_orm.timestamp_pickup)

        result = self.controller.pickup_delivery(delivery_2_id)
        self.assertIsNotNone(result.timestamp_pickup)

        delivery_2_orm = Delivery.get_by_id(delivery_2_id)
        self.assertIsNotNone(delivery_2_orm.timestamp_pickup)

    def test_pickup_delivery_double_pickup(self):
        result_1 = self.controller.save_delivery(self.test_delivery_1)
        delivery_1_id = result_1.id

        # first pickup
        result = self.controller.pickup_delivery(delivery_1_id)
        self.assertIsNotNone(result.timestamp_pickup)
        delivery_1_orm = Delivery.get_by_id(delivery_1_id)
        self.assertIsNotNone(delivery_1_orm.timestamp_pickup)

        # second pickup
        with self.assertRaises(RuntimeError):
            self.controller.pickup_delivery(delivery_1_id)

    def test_load_delivery(self):
        user_orm = User(
            username='test',
            password='test',
            is_active=True,
            accepted_terms=0,
            role='USER'
        )
        user_orm.save()
        user_id = user_orm.id

        delivery_orm = Delivery(
            type='DELIVERY',
            timestamp_delivery='2021-05-07T10:10:04+02:00',
            courier_firm='TNT',
            parcelbox_rebus_id=37,
            user_id_pickup=user_id
        )
        delivery_orm.save()
        delivery_id = delivery_orm.id

        # verify that the user is saved
        user_queried = User.get_by_id(user_id)
        self.assertIsNotNone(user_queried)

        delivery_dto = DeliveryMapper.orm_to_dto(delivery_orm)
        result = self.controller.load_delivery(delivery_id)
        self.assertEqual(delivery_dto, result)


