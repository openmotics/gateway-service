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
Authentication api tests
"""
from __future__ import absolute_import

import time
import unittest

import cherrypy
import mock
import ujson as json

from gateway.api.V1.rooms import Rooms
from gateway.authentication_controller import AuthenticationController, \
    AuthenticationToken, LoginMethod
from gateway.dto.room import RoomDTO
from gateway.exceptions import *
from gateway.room_controller import RoomController
from gateway.user_controller import UserController
from ioc import SetTestMode, SetUpTestInjections

from .base import BaseCherryPyUnitTester


class RoomsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.auth_controller = mock.Mock(AuthenticationController)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        self.user_controller = mock.Mock(UserController)
        self.user_controller.authentication_controller = self.auth_controller
        self.room_controller = mock.Mock(RoomController)
        self.room_controller.load_rooms.return_value = [
            RoomDTO(0, name='Livingroom'),
            RoomDTO(1, name='Bathroom'),
        ]
        SetUpTestInjections(room_controller=self.room_controller,
                            user_controller=self.user_controller)
        self.web = Rooms()

    def test_rooms_list(self):
        response = self.web.list()
        expected = [
            {'id': 0, 'name': 'Livingroom'},
            {'id': 1, 'name': 'Bathroom'},
        ]
        self.assertEqual(expected, json.loads(response))
