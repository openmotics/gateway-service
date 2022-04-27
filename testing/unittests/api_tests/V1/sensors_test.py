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
import requests
import ujson as json
from mock import Mock, patch

from gateway.api.V1.sensors import PluginSensor
from gateway.authentication_controller import AuthenticationController, \
    AuthenticationToken, LoginMethod
from gateway.dto.sensor import SensorDTO, SensorSourceDTO
from gateway.exceptions import *
from gateway.sensor_controller import SensorController
from gateway.user_controller import UserController
from ioc import SetTestMode, SetUpTestInjections
from plugin_runtime.sdk import SensorSDK

from .base import BaseCherryPyUnitTester


class PluginSensorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.auth_controller = Mock(AuthenticationController)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        self.user_controller = Mock(UserController)
        self.user_controller.authentication_controller = self.auth_controller
        self.sensor_controller = Mock(SensorController)
        SetUpTestInjections(sensor_controller=self.sensor_controller,
                            user_controller=self.user_controller)
        self.web = PluginSensor()

    def test_register(self):
        self.sensor_controller.register_sensor.return_value = SensorDTO(id=10,
                                                                        physical_quantity='temperature',
                                                                        unit='celcius')
        response = self.web.register(request_body={
            'source': 'plugin',
            'plugin': 'DummyPlugin',
            'external_id': '1111',
            'physical_quantity': 'temperature',
            'config': {'unit': 'celcius'}
        })
        expected = {'id': 10, 'name': '', 'room': None, 'physical_quantity': 'temperature', 'in_use': True}
        self.assertEqual(expected, json.loads(response))
        self.sensor_controller.register_sensor.assert_called_with(
            SensorSourceDTO('plugin', name='DummyPlugin'), '1111', 'temperature', {'unit': 'celcius'}
        )

    def test_plugin_sdk(self):
        with patch.object(requests, 'request') as req:
            req.json.return_value = {}
            notification = SensorSDK('https://api.example.org', 'DummyPlugin')
            notification.register('1111', 'temperature')
            req.assert_called_with('POST',
                                   'https://api.example.org/plugin/sensor/register',
                                   headers={'User-Agent': 'Plugin DummyPlugin'},
                                   timeout=30.0,
                                   json={'source': 'plugin',
                                         'plugin': 'DummyPlugin',
                                         'external_id': '1111',
                                         'physical_quantity': 'temperature',
                                         'config': {}})
