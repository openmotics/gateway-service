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
Tests for the apartments module.
"""

from __future__ import absolute_import

import fakesleep
import time
import unittest
import sqlite3
import mock
import logging

import peewee
from peewee import SqliteDatabase

from gateway.dto import ApartmentDTO
from gateway.mappers import ApartmentMapper
from gateway.models import Apartment
from gateway.apartment_controller import ApartmentController
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs

MODELS = [Apartment]


class ApartmentControllerTest(unittest.TestCase):
    """ Tests for ApartmentController. """

    @classmethod
    def setUpClass(cls):
        super(ApartmentControllerTest, cls).setUpClass()
        Logs.setup_logger(log_level_override=logging.DEBUG)
        Logs.set_service_loglevel(level=logging.DEBUG, namespace='peewee')
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    @classmethod
    def tearDownClass(cls):
        super(ApartmentControllerTest, cls).tearDownClass()

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.controller = ApartmentController()
        self.rebus_controller = mock.Mock()
        self.controller.set_rebus_controller(self.rebus_controller)
        self.pubsub = mock.Mock()
        SetUpTestInjections(pubsub=self.pubsub)

        self.test_apartment_1 = ApartmentDTO(
            name='Test-Apartment-1',
            mailbox_rebus_id=1,
            doorbell_rebus_id=1
        )
        self.test_apartment_2 = ApartmentDTO(
            name='Test-Apartment-2',
            mailbox_rebus_id=2,
            doorbell_rebus_id=2
        )

        self.test_apartment_3 = ApartmentDTO(
            name=None,
            mailbox_rebus_id=1,
            doorbell_rebus_id=1
        )

        self.test_apartment_4 = ApartmentDTO(
            mailbox_rebus_id=4,
            doorbell_rebus_id=4
        )

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_create_apartment(self):
        """ Test the create apartment functionality """
        result = self.controller.save_apartment(self.test_apartment_1)
        self.assertEqual(1, Apartment.select().count())
        self.assertEqual(1, self.controller.get_apartment_count())

        apartment_orm = Apartment.select().first()
        self.assertEqual(self.test_apartment_1.name, apartment_orm.name)
        self.assertEqual(self.test_apartment_1.mailbox_rebus_id, apartment_orm.mailbox_rebus_id)
        self.assertEqual(self.test_apartment_1.doorbell_rebus_id, apartment_orm.doorbell_rebus_id)
        self.test_apartment_1.id = result.id
        self.assertEqual(self.test_apartment_1, result)

        apartment_dto = ApartmentDTO(name='test')
        self.controller.save_apartment(apartment_dto)
        apartment_orm = Apartment.select().where(Apartment.name == 'test').first()
        self.assertEqual('test', apartment_orm.name)

    def test_load_apartment(self):
        """ Test the create apartment functionality """
        result = self.controller.save_apartment(self.test_apartment_1)
        loaded = self.controller.load_apartment(result.id)
        self.assertEqual(result, loaded)
        self.assertEqual(1, self.controller.get_apartment_count())

    def test_update_apartment(self):
        """ Test the create apartment functionality """
        result = self.controller.save_apartment(self.test_apartment_1)
        loaded = self.controller.load_apartment(result.id)
        self.assertEqual(result, loaded)
        # Set the id of apartment to id 1 to update the apartment with id 1
        self.test_apartment_2.id = 1
        result = self.controller.update_apartment(self.test_apartment_2)
        self.assertEqual(result.id, self.test_apartment_2.id)
        loaded = self.controller.load_apartment(result.id)
        self.assertEqual(result, loaded)

    def test_update_apartments(self):
        """ Test the create apartment functionality """
        apartment_1_dto = self.controller.save_apartment(self.test_apartment_1)
        loaded = self.controller.load_apartment(apartment_1_dto.id)
        self.assertEqual(apartment_1_dto, loaded)

        apartment_2_dto = self.controller.save_apartment(self.test_apartment_2)
        loaded = self.controller.load_apartment(apartment_2_dto.id)
        self.assertEqual(apartment_2_dto, loaded)

        # Switch the mailboxes arround to test if they actually get switched in the database
        self.test_apartment_1.mailbox_rebus_id, self.test_apartment_2.mailbox_rebus_id = self.test_apartment_2.mailbox_rebus_id, self.test_apartment_1.mailbox_rebus_id
        # Set the id
        self.test_apartment_1.id = apartment_1_dto.id
        self.test_apartment_2.id = apartment_2_dto.id
        result = self.controller.update_apartments([self.test_apartment_1, self.test_apartment_2])
        self.assertEqual(result[0].id, self.test_apartment_1.id)
        self.assertEqual(result[1].id, self.test_apartment_2.id)
        loaded = self.controller.load_apartment(result[0].id)
        self.assertEqual(result[0], loaded)
        loaded = self.controller.load_apartment(result[1].id)
        self.assertEqual(result[1], loaded)

    def test_delete_apartment(self):
        """ Test the create apartment functionality """
        result_1 = self.controller.save_apartment(self.test_apartment_1)
        loaded = self.controller.load_apartment(result_1.id)
        self.assertEqual(result_1, loaded)

        result_2 = self.controller.save_apartment(self.test_apartment_2)
        loaded = self.controller.load_apartment(result_2.id)
        self.assertEqual(result_2, loaded)

        self.assertEqual(2, self.controller.get_apartment_count())
        # delete the apartment by id
        self.controller.delete_apartment(result_1)
        self.assertEqual(1, self.controller.get_apartment_count())

        loaded = self.controller.load_apartment(result_2.id)
        self.assertEqual(result_2, loaded)

        # delete apartment by name instead of id
        self.controller.delete_apartment(self.test_apartment_2)
        self.assertEqual(0, self.controller.get_apartment_count())

    def test_create_apartment_faulty(self):
        """ Test the create apartment functionality """
        # should work
        result = self.controller.save_apartment(self.test_apartment_1)
        self.assertEqual(1, Apartment.select().count())
        self.test_apartment_1.id = result.id
        self.assertEqual(self.test_apartment_1, result)

        try:
            # Same rebus id's as test apartment 1, so should not be saved
            self.controller.save_apartment(self.test_apartment_3)
            self.fail('Should raise an error')
        except peewee.IntegrityError:
            pass
        self.assertEqual(1, Apartment.select().count())

    def test_update_apartment_faulty(self):
        """ Test the update apartment functionality """
        # should work
        self.controller.save_apartment(self.test_apartment_1)
        self.assertEqual(1, Apartment.select().count())
        to_update_apartment = self.controller.save_apartment(self.test_apartment_2)
        self.assertEqual(2, Apartment.select().count())

        try:
            self.test_apartment_3.id = to_update_apartment.id
            self.test_apartment_3.name = "test"
            # Same rebus id's as test apartment 1, so should not be saved
            self.controller.update_apartment(self.test_apartment_3)
            self.fail('Should raise an error')
        except Exception:
            pass

        # make sure the contents of DB is not changed
        self.assertEqual(2, Apartment.select().count())
        loaded = self.controller.load_apartment(1)
        self.test_apartment_1.id = 1
        self.assertEqual(self.test_apartment_1, loaded)
        loaded = self.controller.load_apartment(to_update_apartment.id)
        self.test_apartment_2.id = to_update_apartment.id
        self.assertEqual(self.test_apartment_2, loaded)

    def test_delete_apartment_faulty(self):
        """ Test the delete apartment functionality """
        self.test_apartment_1.name = "testerken"
        result_1 = self.controller.save_apartment(self.test_apartment_1)
        loaded = self.controller.load_apartment(result_1.id)
        self.assertEqual(result_1, loaded)

        self.test_apartment_2.name = "testerken"
        result_2 = self.controller.save_apartment(self.test_apartment_2)
        loaded = self.controller.load_apartment(result_2.id)
        self.assertEqual(result_2, loaded)
        self.assertEqual(2, self.controller.get_apartment_count())

        try:
            self.controller.delete_apartment(self.test_apartment_4)
            self.fail("Should raise an error, no id or name is given in apartment to delete")
        except RuntimeError:
            pass
        self.assertEqual(2, self.controller.get_apartment_count())

        try:
            # name exists already twice
            self.test_apartment_4.name = "testerken"
            self.controller.delete_apartment(self.test_apartment_4)
            self.fail("Should raise an error, no id or name is given in apartment to delete")
        except RuntimeError:
            pass
        self.assertEqual(2, self.controller.get_apartment_count())
