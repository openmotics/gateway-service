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
PubSub tests
"""

from __future__ import absolute_import

import time
import unittest

from mock import Mock, patch, call

from gateway.events import GatewayEvent
from gateway.pubsub import PubSub
from gateway.hal.master_event import MasterEvent
from ioc import SetTestMode, SetUpTestInjections


class PubSubTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.pubsub = PubSub()

        def sub_gateway_mock_func(gw_event):
            pass
        self.sub_gateway_mock = Mock(sub_gateway_mock_func)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, self.sub_gateway_mock)

    def test_pubsub_basic(self):
        event = GatewayEvent(GatewayEvent.Types.INPUT_CHANGE, {'data': 'Some Test Data'})
        self.pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, event)
        self.pubsub._publish_all_events(blocking=False)
        self.sub_gateway_mock.assert_called_once_with(event)

    def test_pubsub_multiple(self):
        gw_event = GatewayEvent(GatewayEvent.Types.INPUT_CHANGE, {'data': 'Some Test Data'})
        num_events = 10
        for _ in range(num_events):
            self.pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gw_event)
        self.pubsub._publish_all_events(blocking=False)
        self.sub_gateway_mock.assert_has_calls([call(gw_event) for _ in range(num_events)], any_order=False)
        self.assertEqual(self.sub_gateway_mock.call_count, num_events)

    def test_pubsub_event_topic_filter(self):
        gw_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'data': 'Some Test Data'})
        self.pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gw_event)
        self.pubsub._publish_all_events(blocking=False)
        self.sub_gateway_mock.assert_not_called()

    def test_pubsub_events_mixed(self):
        event_data = {'data': 'some_data'}
        master_event = MasterEvent(MasterEvent.Types.INPUT_CHANGE, event_data)
        gw_event = GatewayEvent(GatewayEvent.Types.INPUT_CHANGE, event_data)

        def master_callback(event):
            _ = event
            pass
        master_callback_mock = Mock(master_callback)

        def gateway_callback(event):
            _ = event
            pass
        gateway_callback_mock = Mock(gateway_callback)

        self.pubsub.subscribe_master_events(PubSub.MasterTopics.INPUT, master_callback_mock)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, gateway_callback_mock)

        self.pubsub.publish_master_event(PubSub.MasterTopics.INPUT, master_event)
        self.pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gw_event)

        self.pubsub._publish_all_events(blocking=False)

        master_callback_mock.assert_called_once_with(master_event)
        gateway_callback_mock.assert_called_once_with(gw_event)

        master_callback_mock.reset_mock()
        gateway_callback_mock.reset_mock()

        # Test the time constraint
        self.pubsub.publish_master_event(PubSub.MasterTopics.INPUT, master_event)
        self.pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gw_event)

        t_start = time.time()
        self.pubsub._publish_all_events(blocking=True)  # Set the wait for end of queue to be true
        t_end = time.time()
        t_delta = t_end - t_start
        self.assertLess(t_delta, 0.5)  # assert that all the events are send in less than half a second

        master_callback_mock.assert_called_once_with(master_event)
        gateway_callback_mock.assert_called_once_with(gw_event)
