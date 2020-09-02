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
import unittest
import os
import xmlrunner
import tempfile
from peewee import SqliteDatabase
from ioc import SetTestMode
from gateway.dto import RoomDTO, FloorDTO
from gateway.models import Room, Floor
from gateway.room_controller import RoomController

MODELS = [Room, Floor]


class RoomControllerTest(unittest.TestCase):
    _db_filename = None

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls._db_filename = tempfile.mktemp()
        cls.test_db = SqliteDatabase(cls._db_filename)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._db_filename):
            os.remove(cls._db_filename)

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_save_load(self):
        controller = RoomController()
        rooms = controller.load_rooms()
        self.assertEqual(0, len(rooms))
        room_dto_1 = RoomDTO(id=1, name='one')
        controller.save_rooms([(room_dto_1, ['id', 'name'])])
        rooms = controller.load_rooms()
        self.assertEqual(1, len(rooms))
        self.assertEqual(room_dto_1, rooms[0])
        room_dto_2 = RoomDTO(id=2, name='two', floor=FloorDTO(id=1))
        controller.save_rooms([(room_dto_2, ['id', 'name', 'floor'])])
        rooms = controller.load_rooms()
        self.assertEqual(2, len(rooms))
        self.assertIn(room_dto_1, rooms)
        self.assertIn(room_dto_2, rooms)
        room_dto_1.name = ''
        controller.save_rooms([(room_dto_1, ['id', 'name'])])
        rooms = controller.load_rooms()
        self.assertEqual(1, len(rooms))
        self.assertNotIn(room_dto_1, rooms)
        self.assertIn(room_dto_2, rooms)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
