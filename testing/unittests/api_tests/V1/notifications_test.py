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

from gateway.api.V1.notifications import PluginNotification
from gateway.authentication_controller import AuthenticationController, \
    AuthenticationToken, LoginMethod
from gateway.events import GatewayEvent
from gateway.exceptions import *
from gateway.user_controller import UserController
from ioc import SetTestMode, SetUpTestInjections
from plugin_runtime.sdk import NotificationSDK

from .base import BaseCherryPyUnitTester

from cloud.events import EventSender


class PluginNotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.auth_controller = Mock(AuthenticationController)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        self.user_controller = Mock(UserController)
        self.user_controller.authentication_controller = self.auth_controller
        self.event_sender = Mock(EventSender)
        SetUpTestInjections(event_sender=self.event_sender,
                            user_controller=self.user_controller)
        self.web = PluginNotification()

    def test_register(self):
        response = self.web.create(request_body={
            'source': 'plugin',
            'plugin': 'DummyPlugin',
            'topic': 'test',
            'message': 'example notification message',
        })
        expected = {}
        self.assertEqual(expected, json.loads(response))
        self.event_sender.enqueue_event.assert_called_with(
            GatewayEvent('NOTIFICATION',
                         {'source': 'plugin',
                          'plugin': 'DummyPlugin',
                          'type': 'USER',
                          'topic': 'test',
                          'message': 'example notification message'})
        )

    def test_plugin_sdk(self):
        with patch.object(requests, 'request') as req:
            req.json.return_value = {}
            notification = NotificationSDK('https://api.example.org', 'DummyPlugin')
            notification.send('test', 'example notification message')
            req.assert_called_with('POST',
                                   'https://api.example.org/plugin/notification',
                                   headers={'User-Agent': 'Plugin DummyPlugin'},
                                   timeout=30.0,
                                   json={'source': 'plugin',
                                         'plugin': 'DummyPlugin',
                                         'type': 'USER',
                                         'topic': 'test',
                                         'message': 'example notification message'})
