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
from mock import Mock, patch
import requests
import ujson as json

from gateway.api.V1.ventilation_units import PluginVentilation, \
    VentilationUnits
from gateway.authentication_controller import AuthenticationController, \
    AuthenticationToken, LoginMethod
from gateway.dto.ventilation import VentilationDTO, VentilationSourceDTO
from gateway.exceptions import *
from gateway.user_controller import UserController
from gateway.ventilation_controller import VentilationController
from ioc import SetTestMode, SetUpTestInjections
from plugin_runtime.sdk import VentilationSDK

from .base import BaseCherryPyUnitTester


class VentilationUnitsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.auth_controller = Mock(AuthenticationController)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        self.user_controller = Mock(UserController)
        self.user_controller.authentication_controller = self.auth_controller
        self.ventilation_dto = VentilationDTO(1,
                                              name='foo',
                                              device_vendor='OpenMotics',
                                              external_id='1111',
                                              source=VentilationSourceDTO('plugin', name='DummyPlugin'))
        self.ventilation_controller = Mock(VentilationController)
        self.ventilation_controller.load_ventilations.return_value = [self.ventilation_dto]
        SetUpTestInjections(ventilation_controller=self.ventilation_controller,
                            user_controller=self.user_controller)
        self.web = VentilationUnits()

    def test_ventilation_units_list(self):
        response = self.web.list()
        expected = [
            {'id': 1,
             'name': 'foo',
             'room': None,
             'amount_of_levels': 0,
             'source': 'plugin',
             'external_id': '1111',
             'device': {'vendor': 'OpenMotics', 'type': '', 'serial': ''}},
        ]
        self.assertEqual(expected, json.loads(response))

    def test_ventilation_units_sync(self):
        response = self.web.sync()
        expected = [
            {'id': 1, 'name': 'foo', 'room': None}
        ]
        self.assertEqual(expected, json.loads(response))

    def test_ventilation_unit_update(self):
        self.ventilation_controller.save_ventilation.side_effect = lambda x: x
        response = self.web.update(ventilation_id=1, request_body={'name': 'foo', 'room': 2, 'amount_of_levels': 4})
        expected = {'id': 1,
                    'name': 'foo',
                    'room': 2,
                    'amount_of_levels': 4,
                    'source': None}
        self.assertEqual(expected, json.loads(response))
        self.ventilation_controller.save_ventilation.assert_called_with(
            VentilationDTO(1, name='foo', room=2, amount_of_levels=4)
        )

class PluginVentilationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.auth_controller = Mock(AuthenticationController)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        self.user_controller = Mock(UserController)
        self.user_controller.authentication_controller = self.auth_controller
        self.ventilation_controller = Mock(VentilationController)
        SetUpTestInjections(ventilation_controller=self.ventilation_controller,
                            user_controller=self.user_controller)
        self.web = PluginVentilation()

    def test_register(self):
        self.ventilation_controller.register_ventilation.return_value = VentilationDTO(id=10, amount_of_levels=4)
        response = self.web.register(request_body={
            'source': 'plugin',
            'plugin': 'DummyPlugin',
            'external_id': '1111',
            'config': {'amount_of_levels': 4}
        })
        expected = {'id': 10, 'name': '', 'room': None}
        self.assertEqual(expected, json.loads(response))
        self.ventilation_controller.register_ventilation.assert_called_with(
            VentilationSourceDTO('plugin', name='DummyPlugin'), '1111', {'amount_of_levels': 4}
        )

    def test_plugin_sdk(self):
        with patch.object(requests, 'request') as req:
            req.json.return_value = {}
            notification = VentilationSDK('https://api.example.org', 'DummyPlugin')
            notification.register('1111', {'amount_of_levels': 4})
            req.assert_called_with('POST',
                                   'https://api.example.org/plugin/ventilation/register',
                                   headers={'User-Agent': 'Plugin DummyPlugin'},
                                   timeout=30.0,
                                   json={'source': 'plugin',
                                         'plugin': 'DummyPlugin',
                                         'external_id': '1111',
                                         'config': {'amount_of_levels': 4}})
