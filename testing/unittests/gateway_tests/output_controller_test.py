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

import unittest

import fakesleep
import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bus.om_bus_client import MessageClient
from gateway.dto import OutputDTO, OutputStatusDTO
from gateway.events import GatewayEvent
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from gateway.maintenance_controller import MaintenanceController
from gateway.models import Database, Base, Output, Room
from gateway.output_controller import OutputController, OutputStateCache
from gateway.pubsub import PubSub
from ioc import SetTestMode, SetUpTestInjections


class OutputControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        fakesleep.monkey_patch()

    @classmethod
    def tearDownClass(cls):
        super(OutputControllerTest, cls).tearDownClass()
        fakesleep.monkey_restore()

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

        self.master_controller = mock.Mock(MasterController)
        self.pubsub = PubSub()
        SetUpTestInjections(maintenance_controller=mock.Mock(MaintenanceController),
                            master_controller=self.master_controller,
                            message_client=mock.Mock(MessageClient),
                            pubsub=self.pubsub)
        self.controller = OutputController()

    def test_orm_sync(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        output_dto = OutputDTO(id=42)
        with mock.patch.object(self.master_controller, 'load_outputs', return_value=[output_dto]):
            self.controller._sync_structures = True
            self.controller.run_sync_orm()
            self.pubsub._publish_all_events(blocking=False)
            with self.session as db:
                assert db.query(Output).where(Output.number == output_dto.id).count() == 1
            assert GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'output'}) in events
            assert len(events) == 1

    def test_output_sync_change(self):
        events = []

        def on_change(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, on_change)

        outputs = {2: OutputDTO(id=2),
                   40: OutputDTO(id=40, module_type='D')}
        with Database.get_session() as db:
            room = Room(number=3)
            db.add_all([room,
                        Output(number=2),
                        Output(number=40, room=room)])
            db.commit()
        with mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: outputs.get(output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[OutputStatusDTO(id=2, status=True),
                                             OutputStatusDTO(id=40, status=True)]):
            self.controller._sync_state()
            self.pubsub._publish_all_events(blocking=False)
            assert [GatewayEvent('OUTPUT_CHANGE', {'id': 2, 'status': {'on': True, 'locked': False}, 'location': {'room_id': 255}}),
                    GatewayEvent('OUTPUT_CHANGE', {'id': 40, 'status': {'on': True, 'value': 0, 'locked': False}, 'location': {'room_id': 3}})] == events

        with mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: outputs.get(output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[OutputStatusDTO(id=2, status=True, dimmer=0),
                                             OutputStatusDTO(id=40, status=True, dimmer=50)]):
            events = []
            self.controller._sync_state()
            self.pubsub._publish_all_events(blocking=False)
            assert [GatewayEvent('OUTPUT_CHANGE', {'id': 2, 'status': {'on': True, 'locked': False}, 'location': {'room_id': 255}}),
                    GatewayEvent('OUTPUT_CHANGE', {'id': 40, 'status': {'on': True, 'value': 50, 'locked': False}, 'location': {'room_id': 3}})] == events

    def test_output_master_change(self):
        events = []

        def on_change(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, on_change)

        self.controller._cache.update_outputs([OutputDTO(id=2),
                                               OutputDTO(id=40, module_type='D', room=3)])
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStatusDTO(id=2, status=False)}))
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStatusDTO(id=40, status=True, dimmer=100)}))
        self.pubsub._publish_all_events(blocking=False)

        events = []
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStatusDTO(id=2, status=True)}))
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStatusDTO(id=40, status=True)}))
        self.pubsub._publish_all_events(blocking=False)

        assert [GatewayEvent('OUTPUT_CHANGE', {'id': 2, 'status': {'on': True, 'locked': False}, 'location': {'room_id': 255}})] == events

        events = []
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStatusDTO(id=40, dimmer=50)}))
        self.pubsub._publish_all_events(blocking=False)
        assert [GatewayEvent('OUTPUT_CHANGE', {'id': 40, 'status': {'on': True, 'value': 50, 'locked': False}, 'location': {'room_id': 3}})] == events

    def test_get_last_outputs(self):
        master_dtos = {1: OutputDTO(id=1, name='one'),
                       2: OutputDTO(id=2, name='two')}
        with Database.get_session() as db:
            db.add_all([
                Output(number=1),
                Output(number=2)
            ])
            db.commit()
        with mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: master_dtos.get(output_id)):
            fakesleep.reset(0)
            self.controller.load_outputs()
            # test 1: all outputs should have a new status upon init
            last_outputs = self.controller.get_last_outputs()
            self.assertEqual([1, 2], last_outputs)

            # test 2: after 10 seconds, all statuses are stable, and not in last outputs
            fakesleep.sleep(15)
            last_outputs = self.controller.get_last_outputs()
            self.assertEqual([], last_outputs)

            # test 3: a new state comes from the master, this should trigger and appear in the recent list
            master_event = MasterEvent(event_type=MasterEvent.Types.OUTPUT_STATUS,
                                       data={'state': OutputStatusDTO(id=2, status=True)})
            self.controller._handle_master_event(master_event)
            last_outputs = self.controller.get_last_outputs()
            self.assertEqual([2], last_outputs)

            # test 4: after 10 seconds, all statuses are stable, and not in last outputs
            fakesleep.sleep(15)
            last_outputs = self.controller.get_last_outputs()
            self.assertEqual([], last_outputs)

            # test 3: a new state comes from the master, this should also trigger and appear in the recent list
            master_event = MasterEvent(event_type=MasterEvent.Types.OUTPUT_STATUS,
                                       data={'state': OutputStatusDTO(id=2, status=False)})
            self.controller._handle_master_event(master_event)
            last_outputs = self.controller.get_last_outputs()
            self.assertEqual([2], last_outputs)

    def test_get_output_status(self):
        with Database.get_session() as db:
            db.add_all([
                Output(number=2),
                Output(number=40, room=Room(number=3))
            ])
            db.commit()
        with mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: OutputDTO(id=output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[OutputStatusDTO(id=2, status=False),
                                             OutputStatusDTO(id=40, status=True)]):
            self.controller._sync_state()
            status = self.controller.get_output_status(40)
            assert status == OutputStatusDTO(id=40, status=True)

    def test_get_output_statuses(self):
        with Database.get_session() as db:
            db.add_all([
                Output(number=2),
                Output(number=40, room=Room(number=3))
            ])
            db.commit()
        with mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: OutputDTO(id=output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[OutputStatusDTO(id=2, status=False, dimmer=0),
                                             OutputStatusDTO(id=40, status=True, dimmer=50)]):
            self.controller._sync_state()
            status = self.controller.get_output_statuses()
            assert len(status) == 2
            assert OutputStatusDTO(id=2, status=False) in status
            assert OutputStatusDTO(id=40, status=True, dimmer=50) in status

    def test_load_output(self):
        with Database.get_session() as db:
            db.add(Output(number=42, room=Room(number=3)))
            db.commit()
        with mock.patch.object(self.master_controller, 'load_output',
                               return_value=OutputDTO(id=42)) as load:
            output = self.controller.load_output(42)
            assert output == OutputDTO(id=42, room=3)
            load.assert_called_with(output_id=42)

    def test_load_outputs(self):
        with Database.get_session() as db:
            db.add(Output(number=42, room=Room(number=3)))
            db.commit()
        with mock.patch.object(self.master_controller, 'load_output',
                               return_value=OutputDTO(id=42)) as load:
            outputs = self.controller.load_outputs()
            assert OutputDTO(id=42, room=3) in outputs
            load.assert_called_with(output_id=42)

    def test_save_outputs(self):
        with Database.get_session() as db:
            db.add_all([
                Room(number=3),
                Output(number=42, in_use=False)
            ])
            db.commit()
        with mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: OutputDTO(id=output_id)) as load, \
             mock.patch.object(self.master_controller, 'save_outputs') as save:
            self.controller.save_outputs([
                OutputDTO(id=42, name='foo', room=3, in_use=True),
            ])
            save.assert_called()
            assert save.call_args_list[0][0][0][0].id == 42
            assert save.call_args_list[0][0][0][0].name == 'foo'
            outputs = self.controller.load_outputs()
            assert OutputDTO(id=42, name='foo', room=3, in_use=True) in outputs

    def test_output_actions(self):
        with Database.get_session() as db:
            db.add_all([
                Output(number=1, in_use=False),
                Output(number=2, in_use=True)
            ])
            db.commit()
        with mock.patch.object(self.master_controller, 'set_all_lights') as call:
            self.controller.set_all_lights(action='OFF')
            call.assert_called_once_with(action='OFF', output_ids=[2])
        with mock.patch.object(self.master_controller, 'set_all_lights') as call:
            self.controller.set_all_lights(action='ON')
            call.assert_called_once_with(action='ON', output_ids=[2])


class OutputStateCacheTest(unittest.TestCase):
    def test_update(self):
        _ = self

        cache = OutputStateCache()

        cache.update_outputs([OutputDTO(id=0),
                              OutputDTO(id=1),
                              OutputDTO(id=2)])
        current_state = cache.get_state()
        assert {0: OutputStatusDTO(id=0),
                1: OutputStatusDTO(id=1),
                2: OutputStatusDTO(id=2)} == current_state

        # Everything is off.
        assert cache.handle_change(OutputStatusDTO(0, status=False))[0] is False
        assert cache.handle_change(OutputStatusDTO(1, status=False))[0] is False
        assert cache.handle_change(OutputStatusDTO(2, status=False))[0] is False

        # Turn two outputs on.
        assert cache.handle_change(OutputStatusDTO(0, status=False))[0] is False
        changed, output_dto = cache.handle_change(OutputStatusDTO(2, status=True))
        assert output_dto.state.status is True
        assert changed is True
        changed, output_dto = cache.handle_change(OutputStatusDTO(1, status=True))
        assert output_dto.state.status is True
        assert changed is True

        # Turn one outputs off again.
        assert cache.handle_change(OutputStatusDTO(0, status=False))[0] is False
        changed, output_dto = cache.handle_change(OutputStatusDTO(1, status=False))
        assert output_dto.state.status is False
        assert changed is True

        # Change dimmer value.
        assert cache.handle_change(OutputStatusDTO(0, dimmer=0))[0] is False
        changed, output_dto = cache.handle_change(OutputStatusDTO(1, status=True, dimmer=100))
        assert output_dto.state.dimmer == 100
        assert changed is True
        changed, output_dto = cache.handle_change(OutputStatusDTO(1, dimmer=50))
        assert output_dto.state.dimmer is 50
        assert changed is True

        # Change lock.
        assert cache.handle_change(OutputStatusDTO(0, locked=False))[0] is False
        changed, output_dto = cache.handle_change(OutputStatusDTO(1, locked=True))
        assert output_dto.state.locked is True
        assert changed is True
