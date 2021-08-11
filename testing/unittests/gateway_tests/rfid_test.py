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
RFID controller tests
"""
from __future__ import absolute_import
import unittest

from peewee import SqliteDatabase

from gateway.dto import RfidDTO, UserDTO
from gateway.mappers import UserMapper, RfidMapper
from gateway.models import RFID, User, Apartment
from gateway.rfid_controller import RfidController
from ioc import SetTestMode

MODELS = [RFID, User, Apartment]

class RFIDControllerTest(unittest.TestCase):
    """ Tests for DeliveryController. """

    @classmethod
    def setUpClass(cls):
        super(RFIDControllerTest, cls).setUpClass()
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:', pragmas={'foreign_keys': 1})

    @classmethod
    def tearDownClass(cls):
        super(RFIDControllerTest, cls).tearDownClass()

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=True, bind_backrefs=True)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.controller = RfidController

        self.test_admin_1 = UserDTO(
            username='test_admin_1',
            role='ADMIN'
        )
        self.test_admin_1.set_password('test')

        self.test_technician_1 = UserDTO(
            username='test_technician_1',
            role='TECHNICIAN'
        )
        self.test_technician_1.set_password('test')

        self.test_user_1 = UserDTO(
            username='test_user_1',
            role='USER'
        )
        self.test_user_1.set_password('test')

        self.test_courier_1 = UserDTO(
            username='test_courier_1',
            role='COURIER'
        )
        self.test_courier_1.set_password('test')

        self.test_rfid_1 = RfidDTO(
            tag_string='abcdef',
            label='tester',
            uid_manufacturer='manufact_1',
            enter_count=0,
            user=self.test_user_1
        )

        self.test_rfid_2 = RfidDTO(
            tag_string='ghijkl',
            label='tester',
            uid_manufacturer='manufact_2',
            enter_count=2,
            timestamp_created='2021-04-16T14:59:16+02:00',
            user=self.test_admin_1
        )

        self.test_rfid_3 = RfidDTO(
            tag_string='mnopqr',
            label='tester',
            uid_manufacturer='manufact_2',
            enter_count=2,
            user=self.test_user_1
        )

    def assert_rfid_equal(self, expected, testee):
        # type: (RfidDTO, RfidDTO) -> None
        for field in expected.loaded_fields:
            if field != 'user':
                self.assertEqual(getattr(expected, field), getattr(testee, field),
                                 "field {} did not match for the rfid_dto instances".format(field))


    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_create_rfid(self):
        """ Test the create delivery functionality """
        result_1 = self.controller.save_rfid(self.test_rfid_1)
        self.assertEqual(1, RFID.select().count())

        rfid_orm_1 = RFID.select().first()
        self.assertEqual(self.test_rfid_1.tag_string, rfid_orm_1.tag_string)
        self.assertEqual(self.test_rfid_1.label, rfid_orm_1.label)
        self.assertEqual(self.test_rfid_1.uid_manufacturer, rfid_orm_1.uid_manufacturer)

        self.assert_rfid_equal(self.test_rfid_1, result_1)

        result_2 = self.controller.save_rfid(self.test_rfid_2)
        self.assertEqual(2, RFID.select().count())
        rfid_orm_2 = RFID.select().where(RFID.tag_string == self.test_rfid_2.tag_string).first()
        self.assertEqual(self.test_rfid_2.tag_string, rfid_orm_2.tag_string)
        self.assertEqual(self.test_rfid_2.label, rfid_orm_2.label)
        self.assertEqual(self.test_rfid_2.uid_manufacturer, rfid_orm_2.uid_manufacturer)
        self.assertEqual(self.test_rfid_2.timestamp_created, rfid_orm_2.timestamp_created)
        self.assert_rfid_equal(self.test_rfid_2, result_2)

        # Same uid manufacturer
        with self.assertRaises(Exception):
            self.controller.save_rfid(self.test_rfid_3)

        # update the label on one of the rfid instances
        self.test_rfid_2.label = 'new label'
        result_3 = self.controller.save_rfid(self.test_rfid_2)
        self.assertEqual(2, RFID.select().count())
        rfid_orm_3 = RFID.select().where(RFID.tag_string == self.test_rfid_2.tag_string).first()
        self.assertEqual(self.test_rfid_2.tag_string, rfid_orm_3.tag_string)
        self.assertEqual(self.test_rfid_2.label, rfid_orm_3.label)
        self.assertEqual(self.test_rfid_2.uid_manufacturer, rfid_orm_3.uid_manufacturer)
        self.assertEqual(self.test_rfid_2.timestamp_created, rfid_orm_3.timestamp_created)
        self.assert_rfid_equal(self.test_rfid_2, result_3)
        self.assertEqual(rfid_orm_3.id, rfid_orm_2.id)

    def test_delete_rfid(self):
        res_1 = self.controller.save_rfid(self.test_rfid_1)
        res_2 = self.controller.save_rfid(self.test_rfid_2)
        self.assertEqual(2, RFID.select().count())

        self.controller.delete_rfid(res_1.id)
        self.assertEqual(1, RFID.select().count())

        self.controller.delete_rfid(res_2.id)
        self.assertEqual(0, RFID.select().count())

        res_3 = self.controller.save_rfid(self.test_rfid_1)
        # Should get a new id when created
        self.assertNotEqual(res_1.id, res_3.id)
        self.assertEqual(1, RFID.select().count())

        # Delete the user to check if the badges get deleted too
        rfid_orm = RFID.select().where(RFID.tag_string == self.test_rfid_1.tag_string).first()  # type: RFID
        user_orm = rfid_orm.user  # type: User
        self.assertIsNotNone(user_orm)

        User.delete().where(User.id == user_orm.id).execute()

        # check that the badge is deleted too
        self.assertEqual(0, RFID.select().count())


    def test_get_rfid(self):
        res_1 = self.controller.save_rfid(self.test_rfid_1)
        res_2 = self.controller.save_rfid(self.test_rfid_2)

        result = self.controller.load_rfids(res_1.user.id)
        self.assertEqual([res_1], result)

        result = self.controller.load_rfids(user_id=37)
        self.assertEqual([], result)

