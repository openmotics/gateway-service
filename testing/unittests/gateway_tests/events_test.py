# Copyright (C) 2019 OpenMotics BV
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
Tests for events.
"""
from __future__ import absolute_import

import unittest

import xmlrunner
from mock import Mock

from gateway.events import GatewayEvent
from ioc import SetTestMode, SetUpTestInjections

from cloud.events import EventSender


class EventsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        cloud_api_client = Mock()
        self.sent_events = {}
        cloud_api_client.send_events = lambda events: self.sent_events.update({'events': events})
        SetUpTestInjections(cloud_api_client=cloud_api_client,
                            input_controller=Mock())

    def test_events_sent_to_cloud(self):
        event_sender = EventSender()  # Don't start, trigger manually
        self.assertEqual(len(event_sender._queue), 0)
        self.assertFalse(event_sender._batch_send_events())
        event_sender.enqueue_event(GatewayEvent(GatewayEvent.Types.OUTPUT_CHANGE, {'id': 1}))
        event_sender.enqueue_event(GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE, {'id': 1}))
        event_sender.enqueue_event(GatewayEvent(GatewayEvent.Types.INPUT_CHANGE, {'id': 1}))
        self.assertEqual(len(event_sender._queue), 3)
        self.assertTrue(event_sender._batch_send_events())
        self.assertEqual(len(event_sender._queue), 0)
        self.assertEqual(len(self.sent_events.get('events', [])), 3)
