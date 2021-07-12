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

import unittest

from mock import Mock, patch, call

from gateway.events import GatewayEvent, EsafeEvent
from gateway.pubsub import PubSub
from ioc import SetTestMode, SetUpTestInjections

from cloud.events import EventSender


class PubSubTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.pubsub = PubSub()

        def sub_gateway_mock_func(gw_event):
            pass
        self.sub_gateway_mock = Mock(sub_gateway_mock_func)

        def sub_esafe_mock_func(es_event):
            pass
        self.sub_esafe_mock = Mock(sub_esafe_mock_func)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, self.sub_gateway_mock)
        self.pubsub.subscribe_esafe_events(PubSub.EsafeTopics.DELIVERY, self.sub_esafe_mock)

    def test_pubsub_basic(self):

        event = GatewayEvent(GatewayEvent.Types.INPUT_CHANGE, {'data': 'Some Test Data'})
        self.pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, event)
        self.pubsub._publish_all_events()
        self.sub_gateway_mock.assert_called_once_with(event)

        event = EsafeEvent(EsafeEvent.Types.DELIVERY_CHANGE, {'delivery_id': 37, 'delivery_type': 'RETURN'})
        self.pubsub.publish_esafe_event(PubSub.EsafeTopics.DELIVERY, event)
        self.pubsub._publish_all_events()
        self.sub_esafe_mock.assert_called_once_with(event)

    def test_pubsub_multiple(self):
        gw_event = GatewayEvent(GatewayEvent.Types.INPUT_CHANGE, {'data': 'Some Test Data'})
        es_event = EsafeEvent(EsafeEvent.Types.DELIVERY_CHANGE, {'delivery_id': 37, 'delivery_type': 'RETURN'})
        num_events = 10
        for _ in range(num_events):
            self.pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gw_event)
        for _ in range(num_events):
            self.pubsub.publish_esafe_event(PubSub.EsafeTopics.DELIVERY, es_event)
        self.pubsub._publish_all_events()
        self.sub_gateway_mock.assert_has_calls([call(gw_event) for _ in range(num_events)], any_order=False)
        self.sub_esafe_mock.assert_has_calls([call(es_event) for _ in range(num_events)], any_order=False)
        self.assertEqual(self.sub_gateway_mock.call_count, num_events)
        self.assertEqual(self.sub_esafe_mock.call_count, num_events)
