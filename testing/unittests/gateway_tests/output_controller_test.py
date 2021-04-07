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

import mock
from peewee import SqliteDatabase

from bus.om_bus_client import MessageClient
from gateway.dto import OutputDTO, OutputStateDTO
from gateway.events import GatewayEvent
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from gateway.maintenance_controller import MaintenanceController
from gateway.models import Output, Room, Floor
from gateway.output_controller import OutputController, OutputStateCache
from gateway.pubsub import PubSub
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Output, Room, Floor]


class OutputControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.master_controller = mock.Mock(MasterController)
        self.pubsub = PubSub()
        SetUpTestInjections(maintenance_controller=mock.Mock(MaintenanceController),
                            master_controller=self.master_controller,
                            message_client=mock.Mock(MessageClient),
                            pubsub=self.pubsub)
        self.controller = OutputController()

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_orm_sync(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        output_dto = OutputDTO(id=42)
        with mock.patch.object(self.master_controller, 'load_outputs', return_value=[output_dto]):
            self.controller.run_sync_orm()
            self.pubsub._publish_all_events()
            assert Output.select().where(Output.number == output_dto.id).count() == 1
            assert GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'output'}) in events
            assert len(events) == 1

    def test_output_sync_change(self):
        events = []

        def on_change(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, on_change)

        outputs = {2: OutputDTO(id=2),
                   40: OutputDTO(id=40, module_type='D')}
        select_mock = mock.Mock()
        select_mock.join_from.return_value = [Output(id=0, number=2),
                                              Output(id=1, number=40, room=Room(id=2, number=3))]
        with mock.patch.object(Output, 'select', return_value=select_mock), \
             mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: outputs.get(output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[OutputStateDTO(id=2, status=True),
                                             OutputStateDTO(id=40, status=True)]):
            self.controller._sync_state()
            self.pubsub._publish_all_events()
            assert [GatewayEvent('OUTPUT_CHANGE', {'id': 2, 'status': {'on': True, 'locked': False}, 'location': {'room_id': 255}}),
                    GatewayEvent('OUTPUT_CHANGE', {'id': 40, 'status': {'on': True, 'value': 0, 'locked': False}, 'location': {'room_id': 3}})] == events

        select_mock = mock.Mock()
        select_mock.join_from.return_value = [Output(id=0, number=2),
                                              Output(id=1, number=40, room=Room(id=2, number=3))]
        with mock.patch.object(Output, 'select', return_value=select_mock), \
             mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: outputs.get(output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[OutputStateDTO(id=2, status=True, dimmer=0),
                                             OutputStateDTO(id=40, status=True, dimmer=50)]):
            events = []
            self.controller._sync_state()
            self.pubsub._publish_all_events()
            assert [GatewayEvent('OUTPUT_CHANGE', {'id': 2, 'status': {'on': True, 'locked': False}, 'location': {'room_id': 255}}),
                    GatewayEvent('OUTPUT_CHANGE', {'id': 40, 'status': {'on': True, 'value': 50, 'locked': False}, 'location': {'room_id': 3}})] == events

    def test_output_master_change(self):
        events = []

        def on_change(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, on_change)

        self.controller._cache.update_outputs([OutputDTO(id=2),
                                               OutputDTO(id=40, module_type='D', room=3)])
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStateDTO(id=2, status=False)}))
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStateDTO(id=40, status=True, dimmer=100)}))
        self.pubsub._publish_all_events()

        events = []
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStateDTO(id=2, status=True)}))
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStateDTO(id=40, status=True)}))
        self.pubsub._publish_all_events()

        assert [GatewayEvent('OUTPUT_CHANGE', {'id': 2, 'status': {'on': True, 'locked': False}, 'location': {'room_id': 255}})] == events

        events = []
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'state': OutputStateDTO(id=40, dimmer=50)}))
        self.pubsub._publish_all_events()
        assert [GatewayEvent('OUTPUT_CHANGE', {'id': 40, 'status': {'on': True, 'value': 50, 'locked': False}, 'location': {'room_id': 3}})] == events

    def test_get_output_status(self):
        select_mock = mock.Mock()
        select_mock.join_from.return_value = [Output(id=0, number=2),
                                              Output(id=1, number=40, room=Room(id=2, number=3))]
        with mock.patch.object(Output, 'select', return_value=select_mock), \
             mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: OutputDTO(id=output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[OutputStateDTO(id=2, status=False),
                                             OutputStateDTO(id=40, status=True)]):
            self.controller._sync_state()
            status = self.controller.get_output_status(40)
            assert status == OutputStateDTO(id=40, status=True)

    def test_get_output_statuses(self):
        select_mock = mock.Mock()
        select_mock.join_from.return_value = [Output(id=0, number=2),
                                              Output(id=1, number=40, module_type='D', room=Room(id=2, number=3))]
        with mock.patch.object(Output, 'select', return_value=select_mock), \
             mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: OutputDTO(id=output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[OutputStateDTO(id=2, status=False, dimmer=0),
                                             OutputStateDTO(id=40, status=True, dimmer=50)]):
            self.controller._sync_state()
            status = self.controller.get_output_statuses()
            assert len(status) == 2
            assert OutputStateDTO(id=2, status=False) in status
            assert OutputStateDTO(id=40, status=True, dimmer=50) in status

    def test_load_output(self):
        where_mock = mock.Mock()
        where_mock.get.return_value = Output(id=1, number=42, room=Room(id=2, number=3))
        join_from_mock = mock.Mock()
        join_from_mock.where.return_value = where_mock
        select_mock = mock.Mock()
        select_mock.join_from.return_value = join_from_mock
        with mock.patch.object(Output, 'select', return_value=select_mock), \
             mock.patch.object(self.master_controller, 'load_output',
                               return_value=OutputDTO(id=42)) as load:
            output = self.controller.load_output(42)
            assert output == OutputDTO(id=42, room=3)
            load.assert_called_with(output_id=42)

    def test_load_outputs(self):
        select_mock = mock.Mock()
        select_mock.join_from.return_value = [Output(id=1, number=42, room=Room(id=2, number=3))]
        with mock.patch.object(Output, 'select', return_value=select_mock), \
             mock.patch.object(self.master_controller, 'load_output',
                               return_value=OutputDTO(id=42)) as load:
            outputs = self.controller.load_outputs()
            assert OutputDTO(id=42, room=3) in outputs
            load.assert_called_with(output_id=42)

    def test_output_actions(self):
        floor = Floor.create(number=5)
        room = Room.create(number=10, floor=floor)
        Output.create(number=2, room=room)
        Output.create(number=3)

        with mock.patch.object(self.master_controller, 'set_all_lights') as call:
            self.controller.set_all_lights_floor(action='OFF')
            call.assert_called_once()
        with mock.patch.object(self.master_controller, 'set_all_lights_floor') as call:
            self.controller.set_all_lights_floor(action='OFF', floor_id=1)
            call.assert_called_once_with(action='OFF', floor_id=1, output_ids=[])
        with mock.patch.object(self.master_controller, 'set_all_lights_floor') as call:
            self.controller.set_all_lights_floor(action='OFF', floor_id=5)
            call.assert_called_once_with(action='OFF', floor_id=5, output_ids=[2])
        with mock.patch.object(self.master_controller, 'set_all_lights_floor') as call:
            self.controller.set_all_lights_floor(action='ON', floor_id=5)
            call.assert_called_once_with(action='ON', floor_id=5, output_ids=[2])


class OutputStateCacheTest(unittest.TestCase):
    def test_update(self):
        _ = self

        cache = OutputStateCache()

        cache.update_outputs([OutputDTO(id=0),
                              OutputDTO(id=1),
                              OutputDTO(id=2)])
        current_state = cache.get_state()
        assert {0: OutputStateDTO(id=0),
                1: OutputStateDTO(id=1),
                2: OutputStateDTO(id=2)} == current_state

        # Everything is off.
        assert cache.handle_change(OutputStateDTO(0, status=False))[0] is False
        assert cache.handle_change(OutputStateDTO(1, status=False))[0] is False
        assert cache.handle_change(OutputStateDTO(2, status=False))[0] is False

        # Turn two outputs on.
        assert cache.handle_change(OutputStateDTO(0, status=False))[0] is False
        changed, output_dto = cache.handle_change(OutputStateDTO(2, status=True))
        assert output_dto.state.status is True
        assert changed is True
        changed, output_dto = cache.handle_change(OutputStateDTO(1, status=True))
        assert output_dto.state.status is True
        assert changed is True

        # Turn one outputs off again.
        assert cache.handle_change(OutputStateDTO(0, status=False))[0] is False
        changed, output_dto = cache.handle_change(OutputStateDTO(1, status=False))
        assert output_dto.state.status is False
        assert changed is True

        # Change dimmer value.
        assert cache.handle_change(OutputStateDTO(0, dimmer=0))[0] is False
        changed, output_dto = cache.handle_change(OutputStateDTO(1, status=True, dimmer=100))
        assert output_dto.state.dimmer == 100
        assert changed is True
        changed, output_dto = cache.handle_change(OutputStateDTO(1, dimmer=50))
        assert output_dto.state.dimmer is 50
        assert changed is True

        # Change lock.
        assert cache.handle_change(OutputStateDTO(0, locked=False))[0] is False
        changed, output_dto = cache.handle_change(OutputStateDTO(1, locked=True))
        assert output_dto.state.locked is True
        assert changed is True
