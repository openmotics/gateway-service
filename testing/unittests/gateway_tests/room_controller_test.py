# Copyright (C) 2017 OpenMotics BV
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
Tests for the room controller.
"""
from __future__ import absolute_import

import os
import tempfile
import unittest

import mock
import xmlrunner
from gateway.dto import RoomDTO
from gateway.models import Database, Room
from gateway.room_controller import RoomController
from ioc import SetTestMode
from peewee import SqliteDatabase

MODELS = [Room]


class RoomControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_save_load(self):
        with mock.patch.object(Database, 'get_db', return_value=self.test_db):
            controller = RoomController()
            rooms = controller.load_rooms()
            self.assertEqual(0, len(rooms))
            room_dto_1 = RoomDTO(id=1, name='one')
            controller.save_rooms([room_dto_1])
            rooms = controller.load_rooms()
            self.assertEqual(1, len(rooms))
            self.assertEqual(room_dto_1, rooms[0])
            room_dto_2 = RoomDTO(id=2, name='two')
            controller.save_rooms([room_dto_2])
            rooms = controller.load_rooms()
            self.assertEqual(2, len(rooms))
            self.assertIn(room_dto_1, rooms)
            self.assertIn(room_dto_2, rooms)
            room_dto_1.name = ''
            controller.save_rooms([room_dto_1])
            rooms = controller.load_rooms()
            self.assertEqual(1, len(rooms))
            self.assertNotIn(room_dto_1, rooms)
            self.assertIn(room_dto_2, rooms)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
