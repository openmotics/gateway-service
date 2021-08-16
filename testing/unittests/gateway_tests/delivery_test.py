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

import mock.mock
from peewee import SqliteDatabase

from gateway.authentication_controller import AuthenticationController, TokenStore
from gateway.dto import DeliveryDTO, UserDTO, SystemRFIDConfigDTO
from gateway.esafe_controller import EsafeController
from gateway.mappers import UserMapper, DeliveryMapper
from gateway.models import Delivery, User, Apartment
from gateway.delivery_controller import DeliveryController
from gateway.pubsub import PubSub
from gateway.rfid_controller import RfidController
from gateway.system_config_controller import SystemConfigController
from gateway.user_controller import UserController
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Delivery, User, Apartment]


class DeliveryControllerTest(unittest.TestCase):
    """ Tests for DeliveryController. """

    @classmethod
    def setUpClass(cls):
        super(DeliveryControllerTest, cls).setUpClass()
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:', pragmas={'foreign_keys': '1'})  # important to mimic the behavior of the real database connection

    @classmethod
    def tearDownClass(cls):
        super(DeliveryControllerTest, cls).tearDownClass()

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.sys_config_controller = SystemConfigController()
        self.sys_config_controller.get_rfid_config = lambda: SystemRFIDConfigDTO(enabled=True, security_enabled=False, max_tags=2)
        SetUpTestInjections(system_config_controller=self.sys_config_controller)
        self.pubsub = PubSub()
        SetUpTestInjections(pubsub=self.pubsub)
        SetUpTestInjections(token_timeout=3)
        self.token_store = TokenStore(token_timeout=3)
        SetUpTestInjections(token_store=self.token_store)
        self.rfid_controller = RfidController()
        self.auth_controller = AuthenticationController(token_timeout=3, token_store=self.token_store, rfid_controller=self.rfid_controller)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        SetUpTestInjections(config={'username': 'test', 'password': 'test'})
        self.user_controller = UserController()
        SetUpTestInjections(user_controller=self.user_controller)
        self.esafe_controller = mock.Mock(EsafeController)
        self.controller = DeliveryController()
        self.controller.set_esafe_controller(self.esafe_controller)
        SetUpTestInjections(delivery_controller=self.controller)

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

        self.test_user_4 = UserDTO(
            username='test_user_4',
            role='COURIER'
        )
        self.test_user_4.set_password('test')

        self.all_users = [self.test_user_1, self.test_user_2, self.test_user_3, self.test_user_4]
        for user in self.all_users:
            user_orm = UserMapper.dto_to_orm(user)
            user_orm.save()

        self.test_delivery_1 = DeliveryDTO(
            type='DELIVERY',
            parcelbox_rebus_id=1,
            courier_firm='TEST',
            user_pickup=self.test_user_1
        )

        self.test_delivery_2 = DeliveryDTO(
            type='DELIVERY',
            parcelbox_rebus_id=2,
            courier_firm='TEST',
            user_pickup=self.test_user_2
        )

        self.test_return_1 = DeliveryDTO(
            type='RETURN',
            parcelbox_rebus_id=10,
            courier_firm='TEST',
            user_delivery=self.test_user_2,
            user_pickup=self.test_user_3
        )
        self.test_return_2 = DeliveryDTO(
            type='RETURN',
            parcelbox_rebus_id=11,
            courier_firm='TEST',
            user_delivery=self.test_user_1,
            user_pickup=self.test_user_4
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
                    self.assertEqual(delivery_dto.user_delivery.username, delivery_orm.user_delivery.username)
                else:
                    self.assertIsNone(delivery_orm.user_delivery)
            elif field == 'user_pickup':
                if delivery_dto.user_pickup is not None:
                    self.assertEqual(delivery_dto.user_pickup.username, delivery_orm.user_pickup.username)
                else:
                    self.assertIsNone(delivery_orm.user_pickup)
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
        self.assertEqual(self.test_delivery_1.user_pickup.username, delivery_orm.user_pickup.username)
        self.test_delivery_1.id = result.id
        self.assert_deliveries_equal(self.test_delivery_1, result)
        self.assert_delivery_in_db(result.id, self.test_delivery_1)

        with mock.patch.object(self.esafe_controller, 'verify_device_exists', return_value=False):
            with self.assertRaises(ValueError):
                result = self.controller.save_delivery(self.test_delivery_1)

    def test_create_delivery_multiple(self):
        """ Test the create delivery functionality """
        result_1 = self.controller.save_delivery(self.test_delivery_1)
        self.assertEqual(1, Delivery.select().count())

        result_2 = self.controller.save_delivery(self.test_delivery_2)
        self.assertEqual(2, Delivery.select().count())

        result_3 = self.controller.save_delivery(self.test_return_1)
        self.assertEqual(3, Delivery.select().count())

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

    def test_pickup_return(self):
        result_1 = self.controller.save_delivery(self.test_return_1)
        result_2 = self.controller.save_delivery(self.test_return_2)
        return_1_id = result_1.id
        return_2_id = result_2.id
        self.assertEqual(len(self.all_users), self.user_controller.get_number_of_users())

        result = self.controller.pickup_delivery(return_1_id)
        self.assertIsNotNone(result.timestamp_pickup)
        self.assertEqual(len(self.all_users) - 1, self.user_controller.get_number_of_users())  # this should be one less since the courier needs to be removed

        return_1_orm = Delivery.get_by_id(return_1_id)
        self.assertIsNotNone(return_1_orm.timestamp_pickup)
        delivery_2_orm = Delivery.get_by_id(return_2_id)
        self.assertIsNone(delivery_2_orm.timestamp_pickup)

        result = self.controller.pickup_delivery(return_2_id)
        self.assertIsNotNone(result.timestamp_pickup)
        self.assertEqual(len(self.all_users) - 2, self.user_controller.get_number_of_users())  # this should be one less since the courier needs to be removed

        delivery_2_orm = Delivery.get_by_id(return_2_id)
        self.assertIsNotNone(delivery_2_orm.timestamp_pickup)

        # Test the double pickup for return deliveries
        with self.assertRaises(RuntimeError):
            result = self.controller.pickup_delivery(return_2_id)

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
        user_orm_1 = User(
            username='test',
            password='test',
            is_active=True,
            accepted_terms=0,
            role='USER'
        )
        user_orm_1.save()

        user_orm_2 = User(
            username='test2',
            password='test2',
            is_active=True,
            accepted_terms=0,
            role='USER'
        )
        user_orm_2.save()

        delivery_orm_1 = Delivery(
            type='DELIVERY',
            timestamp_delivery='2021-05-07T10:10:04+02:00',
            timestamp_pickup='2021-05-08T10:10:04+02:00',
            courier_firm='TNT',
            parcelbox_rebus_id=37,
            user_pickup=user_orm_1.id
        )
        delivery_orm_1.save()

        delivery_orm_2 = Delivery(
            type='DELIVERY',
            timestamp_delivery='2021-05-07T10:10:04+02:00',
            courier_firm='TNT',
            parcelbox_rebus_id=38,
            user_pickup=user_orm_2.id
        )
        delivery_orm_2.save()

        delivery_orm_3 = Delivery(
            type='RETURN',
            timestamp_delivery='2021-05-07T10:10:04+02:00',
            courier_firm='BPOST',
            parcelbox_rebus_id=39,
            user_pickup=user_orm_2.id
        )
        delivery_orm_3.save()

        # check that there are 2 deliveries in the database
        count = Delivery.select().count()
        self.assertEqual(3, count)

        # verify that the user is saved
        user_queried = User.get_by_id(user_orm_1.id)
        self.assertIsNotNone(user_queried)

        delivery_dto = DeliveryMapper.orm_to_dto(delivery_orm_2)
        result = self.controller.load_delivery(delivery_orm_2.id)
        self.assertEqual(delivery_dto, result)

        result = self.controller.load_deliveries()
        # only one delivery should be returned since the first one is already picked up
        self.assertEqual(2, len(result))

        result = self.controller.load_deliveries(user_id=user_orm_2.id)
        # only two deliveries should be returned since the first one is already picked up
        self.assertEqual(2, len(result))

        result = self.controller.load_deliveries(history=True)
        # only two deliveries should be returned since the first one is already picked up
        self.assertEqual(1, len(result))

        result = self.controller.load_deliveries_filter(include_picked_up=True)
        self.assertEqual(3, len(result))

        result = self.controller.load_deliveries_filter(include_picked_up=True, delivery_id=delivery_orm_3.id)
        delivery_dto = DeliveryMapper.orm_to_dto(delivery_orm_3)
        self.assertEqual([delivery_dto], result)

        result = self.controller.load_deliveries_filter(include_picked_up=True, delivery_courier_firm='BPOST')
        delivery_dto = DeliveryMapper.orm_to_dto(delivery_orm_3)
        self.assertEqual([delivery_dto], result)

        result = self.controller.load_deliveries_filter(include_picked_up=True, delivery_courier_firm='TNT')
        expected = [
            DeliveryMapper.orm_to_dto(delivery_orm_1),
            DeliveryMapper.orm_to_dto(delivery_orm_2)
        ]
        self.assertEqual(expected, result)

        result = self.controller.load_deliveries_filter(include_picked_up=False, delivery_courier_firm='TNT')
        expected = [
            DeliveryMapper.orm_to_dto(delivery_orm_2)
        ]
        self.assertEqual(expected, result)

        # add some more deliveries:
        ids = []
        for i in range(20):
            delivery_orm = Delivery(
                type='DELIVERY',
                timestamp_delivery='2021-05-07T10:10:04+02:00',
                timestamp_pickup='2021-05-08T10:10:04+02:00',
                courier_firm='TNT',
                parcelbox_rebus_id=40 + i,
                user_pickup=user_orm_1.id
            )
            delivery_orm.save()
            ids.append(delivery_orm.id)

        # this should return 2 results with the most recent id's
        result = self.controller.load_deliveries(history=True, before_id=None, limit=2)
        self.assertEqual(2, len(result))
        self.assertEqual(ids[-1], result[0].id)
        self.assertEqual(ids[-2], result[1].id)

        # This will match the delivery-id's since all the last ones are picked up deliveries
        result = self.controller.load_deliveries(history=True, before_id=10, limit=2)
        self.assertEqual(2, len(result))
        self.assertEqual(9, result[0].id)
        self.assertEqual(8, result[1].id)

