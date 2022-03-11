# Copyright (C) 2020 OpenMotics BV
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
from __future__ import absolute_import

import logging
import time
import unittest

import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from bus.om_bus_client import MessageClient
from gateway.dto import VentilationDTO, VentilationSourceDTO, \
    VentilationStatusDTO
from gateway.events import GatewayEvent
from gateway.models import Base, Database, Plugin, Ventilation
from gateway.pubsub import PubSub
from gateway.ventilation_controller import VentilationController
from ioc import SetTestMode, SetUpTestInjections


class VentilationControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=True, bind=engine)

        self.session = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()
        self.addCleanup(session_mock.stop)

        self.pubsub = PubSub()
        SetUpTestInjections(pubsub=self.pubsub)
        self.controller = VentilationController()

    def test_set_status(self):
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=2, **fields),
                Ventilation(id=43, name='Bar', external_id='bar', amount_of_levels=4, **fields),
            ])
            db.commit()
        self.controller.set_status(VentilationStatusDTO(42, 'manual', level=0))
        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0))
        status = self.controller.get_status()
        assert {'manual'} == set(x.mode for x in status)
        assert {42, 43} == set(x.id for x in status)
        assert {0, 2} == set(x.level for x in status)
        assert {None, 60.0} == set(x.timer for x in status)

    def test_set_level(self):
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=2, **fields),
                Ventilation(id=43, name='Bar', external_id='bar', amount_of_levels=4, **fields),
            ])
            db.commit()
        self.controller.set_level(42, 0)
        self.controller.set_level(43, 2, timer=60.0)
        status = self.controller.get_status()
        assert {'manual'} == set(x.mode for x in status)
        assert {42, 43} == set(x.id for x in status)
        assert {0, 2} == set(x.level for x in status)
        assert {None, 60.0} == set(x.timer for x in status)

    def test_mode_auto(self):
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=2, **fields),
                Ventilation(id=43, name='Bar', external_id='bar', amount_of_levels=4, **fields),
            ])
            db.commit()

        self.controller.set_mode_auto(42)
        self.controller.set_level(43, 2, timer=60.0)
        status = self.controller.get_status()
        assert {'auto', 'manual'} == set(x.mode for x in status)

        self.controller.set_mode_auto(43)
        status = self.controller.get_status()
        assert {'auto'} == set(x.mode for x in status)
        assert {42, 43} == set(x.id for x in status)
        assert {None} == set(x.level for x in status)
        assert {None} == set(x.timer for x in status)

    def test_set_invalid_level(self):
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=4, **fields)
            ])
            db.commit()
        self.assertRaises(ValueError, self.controller.set_level, 42, 5)
        self.assertRaises(ValueError, self.controller.set_level, 42, -1)

    def test_load_ventilation(self):
        with self.session as db:
            db.add_all([
                Plugin(id=2,
                       name='dummy',
                       version='0.0.1'),
                Ventilation(id=42,
                               source='plugin',
                               external_id='device-000001',
                               name='foo',
                               amount_of_levels=4,
                               device_vendor='example',
                               device_type='model-0',
                               device_serial='device-000001',
                               plugin_id=2)
            ])
            db.commit()

        ventilation_dto = self.controller.load_ventilation(42)
        assert ventilation_dto == VentilationDTO(id=42,
                                                 external_id='device-000001',
                                                 source=VentilationSourceDTO(id=2,
                                                                             name='dummy',
                                                                             type='plugin'),
                                                 name='foo',
                                                 amount_of_levels=4,
                                                 device_vendor='example',
                                                 device_type='model-0',
                                                 device_serial='device-000001')

    def test_create_ventilation(self):
        with self.session as db:
            db.add(Plugin(id=2, name='dummy', version='0.0.1'))
            db.commit()

        ventilation_dto = VentilationDTO(None,
                                         external_id='device-000001',
                                         source=VentilationSourceDTO(id=2,
                                                                     name='dummy',
                                                                     type='plugin'),
                                         name='foo',
                                         amount_of_levels=4,
                                         device_vendor='example',
                                         device_type='model-0',
                                         device_serial='device-000001')
        self.controller.save_ventilation(ventilation_dto)

        with self.session as db:
            query = db.query(Ventilation).filter_by(external_id='device-000001')
            assert query.count() == 1, query.all()
            ventilation = query.one()
            assert ventilation.name == 'foo'
            assert ventilation.amount_of_levels == 4
            assert ventilation.plugin.name == 'dummy'

    def test_update_by_id(self):
        with self.session as db:
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42,
                            external_id='device-000001',
                            name='foo',
                            amount_of_levels=1,
                            device_type='',
                            device_vendor='',
                            device_serial='',
                            source='plugin',
                            plugin_id=2)
            ])
            db.commit()
        ventilation_dto = VentilationDTO(id=42,
                                         external_id='device-000001',
                                         source=VentilationSourceDTO(id=2,
                                                                     name='dummy',
                                                                     type='plugin'),
                                         name='foo',
                                         amount_of_levels=4,
                                         device_vendor='example',
                                         device_type='model-0',
                                         device_serial='device-000001')
        self.controller.save_ventilation(ventilation_dto)
        with self.session as db:
            query = db.query(Ventilation).filter_by(external_id='device-000001')
            assert query.count() == 1, query.all()
            ventilation = query.one()
            assert ventilation.name == 'foo'
            assert ventilation.amount_of_levels == 4
            assert ventilation.device_vendor == 'example'
            assert ventilation.device_type == 'model-0'
            assert ventilation.device_serial == 'device-000001'

    def test_update_ventilation_by_external_id(self):
        with self.session as db:
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42,
                            external_id='device-000001',
                            name='foo',
                            amount_of_levels=1,
                            device_type='',
                            device_vendor='',
                            device_serial='',
                            source='plugin',
                            plugin_id=2)
            ])
            db.commit()
        ventilation_dto = VentilationDTO(None,
                                         external_id='device-000001',
                                         source=VentilationSourceDTO(id=2,
                                                                     name='dummy',
                                                                     type='plugin'),
                                         name='foo',
                                         amount_of_levels=4,
                                         device_vendor='example',
                                         device_type='model-0',
                                         device_serial='device-000001')
        self.controller.save_ventilation(ventilation_dto)
        with self.session as db:
            query = db.query(Ventilation).filter_by(external_id='device-000001')
            assert query.count() == 1, query.all()
            ventilation = query.one()
            assert ventilation.id == 42
            assert ventilation.name == 'foo'
            assert ventilation.amount_of_levels == 4
            assert ventilation.device_vendor == 'example'
            assert ventilation.device_type == 'model-0'
            assert ventilation.device_serial == 'device-000001'

    def test_ventilation_config_events(self):
        with self.session as db:
            db.add(Plugin(id=2, name='dummy', version='0.0.1'))
            db.commit()

        events = []
        def callback(event):
            events.append(event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, callback)

        ventilation_dto = VentilationDTO(id=42,
                                         external_id='device-000001',
                                         source=VentilationSourceDTO(id=2,
                                                                     name='dummy',
                                                                     type='plugin'),
                                         name='foo',
                                         amount_of_levels=4,
                                         device_vendor='example',
                                         device_type='model-0',
                                         device_serial='device-000001')
        self.controller.save_ventilation(ventilation_dto)
        self.pubsub._publish_all_events(blocking=False)
        assert len(events) == 0, events  # No change

        ventilation_dto.name = 'bar'
        self.controller.save_ventilation(ventilation_dto)
        self.pubsub._publish_all_events(blocking=False)
        assert len(events) == 1, events
        assert GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'ventilation'}) in events

    def test_ventilation_change_events(self):
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=2, **fields),
                Ventilation(id=43, name='Bar', external_id='bar', amount_of_levels=4, **fields),
            ])
            db.commit()

        self.controller.set_status(VentilationStatusDTO(42, 'manual', level=0))
        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0))
        self.pubsub._publish_all_events(blocking=False)

        events = []
        def callback(event):
            events.append(event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, callback)

        self.controller.set_status(VentilationStatusDTO(42, 'manual', level=0))
        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0))
        self.pubsub._publish_all_events(blocking=False)
        assert GatewayEvent(GatewayEvent.Types.VENTILATION_CHANGE,
                            {'id': 43, 'mode': 'manual', 'level': 2, 'timer': 60.0,
                             'remaining_time': None,'is_connected': True}) in events
        assert len(events) == 1, events

    def test_ventilation_status_timeout(self):
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=2, **fields),
                Ventilation(id=43, name='Bar', external_id='bar', amount_of_levels=4, **fields),
            ])
            db.commit()

        events = []
        def callback(event):
            events.append(event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, callback)

        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0,
                                                        last_seen=(time.time() - 600)))
        self.pubsub._publish_all_events(blocking=False)

        assert GatewayEvent(GatewayEvent.Types.VENTILATION_CHANGE,
                            {'id': 43, 'mode': 'manual', 'level': 2, 'timer': 60.0,
                             'remaining_time': None, 'is_connected': False}) in events
        assert len(events) == 1, events

    def test_ventilation_controller_inactive_status(self):
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=2, **fields),
                Ventilation(id=43, name='Bar', external_id='bar', amount_of_levels=4, **fields),
            ])
            db.commit()

        events = []
        def callback(event):
            events.append(event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, callback)

        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0,
                                                        last_seen=(time.time() - 600)))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))

        self.controller._check_connected_timeout()
        self.pubsub._publish_all_events(blocking=False)
        self.assertEqual(2, len(events))
        self.assertEqual(1, len(self.controller._status))

        # Check that the last event that has been send is Null
        last_event = events[-1]
        self.assertEqual(None, last_event.data['mode'])
        self.assertEqual(None, last_event.data['level'])

        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(3, len(events))
        self.assertEqual(1, len(self.controller._status))

        self.controller._check_connected_timeout()
        self.pubsub._publish_all_events(blocking=False)
        # Now there would no timeout occur
        self.assertEqual(3, len(events))
        self.assertEqual(1, len(self.controller._status))

    def test_ventilation_timer_expire_manual(self):
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=2, **fields),
                Ventilation(id=43, name='Bar', external_id='bar', amount_of_levels=4, **fields),
            ])
            db.commit()

        events = []
        def callback(event):
            events.append(event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, callback)

        # first timer is running
        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0, remaining_time=5.0,
                                                        last_seen=(time.time() - 10)))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))

        # This should not trigger an event
        self.controller._check_connected_timeout()
        # This should trigger an update event.
        self.controller._periodic_event_update()
        self.pubsub._publish_all_events(blocking=False)
        self.assertEqual(2, len(events))
        self.assertEqual(1, len(self.controller._status))

        events = []
        # event that timer has been done
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=None, remaining_time=None,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))
        self.assertEqual(None, events[-1].data['remaining_time'])
        self.assertEqual(None, events[-1].data['timer'])

        events = []
        # event that timer has been started
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=30, remaining_time=None,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))
        self.assertEqual(None, events[-1].data['remaining_time'])
        self.assertEqual(30, events[-1].data['timer'])

        events = []
        # event from ventilation plugin
        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=1, timer=None, remaining_time=29,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))
        self.assertEqual(29, events[-1].data['remaining_time'])
        self.assertEqual(30, events[-1].data['timer'])  # this value should be kept in cache

        events = []
        # event from ventilation plugin
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=None, remaining_time=15,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))
        self.assertEqual(15, events[-1].data['remaining_time'])  # this value should update from the event
        self.assertEqual(30, events[-1].data['timer'])  # this value should be kept in cache

        events = []
        # event from ventilation plugin (same value)
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=None, remaining_time=15,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(0, len(events))
        self.assertEqual(1, len(self.controller._status))

        # event from ventilation plugin
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=None, remaining_time=14,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))
        self.assertEqual(14, events[-1].data['remaining_time'])  # this value should update from the event
        self.assertEqual(30, events[-1].data['timer'])  # this value should be kept in cache

        events = []
        # event from ventilation plugin -> Timer has expired, but is still in manual mode
        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=1, timer=None, remaining_time=None,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))
        self.assertEqual(None, events[-1].data['remaining_time'])
        self.assertEqual(None, events[-1].data['timer'])  # this value should now be cleared when timer has done

    def test_ventilation_timer_expire_automatic(self):
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=2, **fields),
                Ventilation(id=43, name='Bar', external_id='bar', amount_of_levels=4, **fields),
            ])
            db.commit()

        events = []
        def callback(event):
            events.append(event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, callback)

        # event that ventilation box is running in automatic mode
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=None, remaining_time=None,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))
        self.assertEqual(None, events[-1].data['remaining_time'])  # no timers running
        self.assertEqual(None, events[-1].data['timer'])  # no timers running

        events = []
        # event that timer has been started
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=30, remaining_time=None,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))
        self.assertEqual(None, events[-1].data['remaining_time'])  # There has not been an update from the ventilation box or plugin
        self.assertEqual(30, events[-1].data['timer'])

        for i in range(30, 0, -1):
            events = []
            # event from ventilation plugin
            mode = 'automatic' if i % 2 == 0 else 'manual'
            self.controller.set_status(VentilationStatusDTO(43, mode, level=1, timer=None, remaining_time=i,
                                                            last_seen=time.time()))
            self.pubsub._publish_all_events(blocking=False)

            self.assertEqual(1, len(events))
            self.assertEqual(1, len(self.controller._status))
            self.assertEqual(i, events[-1].data['remaining_time'])
            self.assertEqual(30, events[-1].data['timer'])  # this value should be kept in cache

        events = []
        # event from ventilation plugin -> Timer has expired, and has switched to automatic mode
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=None, remaining_time=None,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))
        self.assertEqual(1, len(self.controller._status))
        self.assertEqual(None, events[-1].data['remaining_time'])
        self.assertEqual(None, events[-1].data['timer'])  # this value should now be cleared when timer has done

    def test_ventilation_status_equal_evaluation(self):
        status_dto_1 = VentilationStatusDTO(1, 'automatic', level=1, timer=None, remaining_time=None,
                                            last_seen=time.time())
        status_dto_2 = VentilationStatusDTO(1, 'manual', level=1, timer=30, remaining_time=None,
                                            last_seen=time.time())
        status_dto_3 = VentilationStatusDTO(1, 'manual', level=1, timer=None, remaining_time=15,
                                            last_seen=time.time())
        status_dto_4 = VentilationStatusDTO(1, 'manual', level=1, timer=None, remaining_time=None,
                                            last_seen=time.time())
        status_dto_5 = VentilationStatusDTO(1, 'automatic', level=1, timer=None, remaining_time=None,
                                            last_seen=time.time())

        self.assertEqual(True, (status_dto_1 == status_dto_5))
        self.assertEqual(False, (status_dto_1 == status_dto_2))
        self.assertNotEqual(status_dto_1, status_dto_2)  # Difference between no timer and setup timer
        self.assertNotEqual(status_dto_1, status_dto_3)  # difference between no timer and running timer
        self.assertNotEqual(status_dto_2, status_dto_3)  # Difference between status and start timer status
        self.assertNotEqual(status_dto_1, status_dto_4)  # difference in mode
        self.assertEqual(status_dto_1, status_dto_5)     # Equal values, but different objects




    def test_ventilation_plugin_anti_ping_pong(self):
        # This test will see if the gateway will not keep sending events back and forth when an event change happens
        # This can be caused by ping-ponging back and forth between the plugin and gateway when sending updates
        with self.session as db:
            fields = {'source': 'plugin',
                      'plugin_id': 2,
                      'device_serial': '',
                      'device_type': '',
                      'device_vendor': ''}
            db.add_all([
                Plugin(id=2, name='dummy', version='0.0.1'),
                Ventilation(id=42, name='Foo', external_id='foo', amount_of_levels=2, **fields),
                Ventilation(id=43, name='Bar', external_id='bar', amount_of_levels=4, **fields),
            ])
            db.commit()

        events = []
        def callback(event, self=self):
            events.append(event)
            if len(events) > 20:
                self.fail('There should never be more than 20 events due to ventilation in this test')
            # resend the same event to mock the plugin who will send an event back with the same status
            # id, mode, level=None, timer=None, remaining_time=None, last_seen=None
            status_dto = VentilationStatusDTO(
                id=event.data['id'],
                mode=event.data['mode'],
                level=event.data['level'],
                remaining_time=event.data['timer'],
            )
            self.controller.set_status(status_dto)
            self.pubsub._publish_all_events(blocking=False)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, callback)

        # event that ventilation box is running in automatic mode
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=None, remaining_time=None,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertEqual(1, len(events))

        events = []
        # event that timer has been started
        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=1, timer=30, remaining_time=None,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertGreaterEqual(10, len(events))

        # event that timer is running
        self.controller.set_status(VentilationStatusDTO(43, 'manual', level=1, timer=None, remaining_time=15,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertGreaterEqual(10, len(events))

        # event that timer is done
        self.controller.set_status(VentilationStatusDTO(43, 'automatic', level=1, timer=None, remaining_time=None,
                                                        last_seen=time.time()))
        self.pubsub._publish_all_events(blocking=False)

        self.assertGreaterEqual(10, len(events))
