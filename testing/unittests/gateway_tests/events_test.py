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
import mock
from mock import Mock, patch
from gateway.events import GatewayEvent
from gateway.models import Config, Input, Base, Database
from ioc import SetTestMode, SetUpTestInjections
from sqlalchemy import create_engine, select
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool
from logs import Logs
from cloud.events import EventSender


class EventsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=True, bind=engine)

        self.session = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()
        self.addCleanup(session_mock.stop)

        cloud_api_client = Mock()
        self.sent_events = {}
        cloud_api_client.send_events = lambda events: self.sent_events.update({'events': events})
        SetUpTestInjections(cloud_api_client=cloud_api_client)

    def test_events_sent_to_cloud(self):
        event_sender = EventSender()  # Don't start, trigger manually
        self.assertEqual(len(event_sender._queue), 0)
        self.assertFalse(event_sender._batch_send_events())

        with Database.get_session() as db:
            db.add_all([Input(number=1, event_enabled=True),
                        Input(number=2, event_enabled=False)])
            db.commit()

        with patch.object(Config, 'get_entry', return_value=True):
            event_sender.enqueue_event(GatewayEvent(GatewayEvent.Types.OUTPUT_CHANGE, {'id': 1}))
            event_sender.enqueue_event(GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE, {'id': 1}))
            event_sender.enqueue_event(GatewayEvent(GatewayEvent.Types.INPUT_CHANGE, {'id': 1}))
            event_sender.enqueue_event(GatewayEvent(GatewayEvent.Types.INPUT_CHANGE, {'id': 2}))
        with patch.object(Config, 'get_entry', return_value=False):
            event_sender.enqueue_event(GatewayEvent(GatewayEvent.Types.INPUT_CHANGE, {'id': 3}))

        self.assertEqual(3, len(event_sender._queue))
        self.assertTrue(event_sender._batch_send_events())
        self.assertEqual(0, len(event_sender._queue))
        events = self.sent_events.get('events', [])
        self.assertEqual(3, len(events))
        input_event = [event for event in events
                       if event.type == GatewayEvent.Types.INPUT_CHANGE][0]
        self.assertEqual(1, input_event.data['id'])
