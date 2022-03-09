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
import logging
import mock
import xmlrunner
from sqlalchemy import create_engine, select
from sqlalchemy.orm import scoped_session, sessionmaker
from gateway.models import Database, Base, Room
from gateway.dto import RoomDTO
from gateway.models import Database, Room
from gateway.room_controller import RoomController
from ioc import SetTestMode
from logs import Logs
MODELS = [Room]


class RoomControllerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super(RoomControllerTest, cls).setUpClass()
        SetTestMode()
        Logs.set_loglevel(logging.DEBUG, namespace='gateway.input_controller')
        # Logs.set_loglevel(logging.DEBUG, namespace='sqlalchemy.engine')

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=True, bind=engine)

        self.db = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.db)
        session_mock.start()
        self.addCleanup(session_mock.stop)


    def test_save_load(self):
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
