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

from bus.om_bus_client import MessageClient
from gateway.dto import OutputDTO, OutputStateDTO
from gateway.events import GatewayEvent
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from gateway.maintenance_controller import MaintenanceController
from gateway.models import Output, Room
from gateway.output_controller import OutputController, OutputStateCache
from ioc import SetTestMode, SetUpTestInjections


class OutputControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.master_controller = mock.Mock(MasterController)
        SetUpTestInjections(maintenance_controller=mock.Mock(MaintenanceController),
                            master_controller=self.master_controller,
                            message_client=mock.Mock(MessageClient))
        self.controller = OutputController()

    def test_output_sync_change(self):
        events = []

        def on_change(gateway_event):
            events.append(gateway_event)

        outputs = {2: OutputDTO(id=2),
                   40: OutputDTO(id=40, module_type='D')}

        self.controller.subscribe_events(on_change)
        with mock.patch.object(Output, 'select',
                               return_value=[Output(id=0, number=2),
                                             Output(id=1, number=40, room=Room(id=2, number=3))]), \
             mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: outputs.get(output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[{'id': 2, 'status': True},
                                             {'id': 40, 'status': True}]):
            self.controller._sync_state()
            assert [GatewayEvent('OUTPUT_CHANGE', {'id': 2, 'status': {'on': True, 'locked': False}, 'location': {'room_id': 255}}),
                    GatewayEvent('OUTPUT_CHANGE', {'id': 40, 'status': {'on': True, 'value': 0, 'locked': False}, 'location': {'room_id': 3}})] == events

        with mock.patch.object(Output, 'select',
                               return_value=[Output(id=0, number=2),
                                             Output(id=1, number=40, room=Room(id=2, number=3))]), \
             mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: outputs.get(output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[{'id': 2, 'status': True, 'dimmer': 0},
                                             {'id': 40, 'status': True, 'dimmer': 50}]):
            events = []
            self.controller._sync_state()
            assert [GatewayEvent('OUTPUT_CHANGE', {'id': 40, 'status': {'on': True, 'value': 50, 'locked': False}, 'location': {'room_id': 3}})] == events

    def test_output_master_change(self):
        events = []

        def on_change(gateway_event):
            events.append(gateway_event)

        self.controller.subscribe_events(on_change)
        self.controller._cache.update_outputs([OutputDTO(id=2),
                                               OutputDTO(id=40, module_type='D', room=3)])
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'id': 2, 'status': False}))
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'id': 40, 'status': True, 'dimmer': 100}))

        events = []
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'id': 2, 'status': True}))
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'id': 40, 'status': True}))

        assert [GatewayEvent('OUTPUT_CHANGE', {'id': 2, 'status': {'on': True, 'locked': False}, 'location': {'room_id': 255}})] == events

        events = []
        self.controller._handle_master_event(MasterEvent('OUTPUT_STATUS', {'id': 40, 'dimmer': 50}))
        assert [GatewayEvent('OUTPUT_CHANGE', {'id': 40, 'status': {'on': True, 'value': 50, 'locked': False}, 'location': {'room_id': 3}})] == events

    def test_get_output_status(self):
        with mock.patch.object(Output, 'select',
                               return_value=[Output(id=0, number=2),
                                             Output(id=1, number=40, room=Room(id=2, number=3))]), \
             mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: OutputDTO(id=output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[{'id': 2, 'status': False},
                                             {'id': 40, 'status': True}]):
            self.controller._sync_state()
            status = self.controller.get_output_status(40)
            assert status == OutputStateDTO(id=40, status=True)

    def test_get_output_statuses(self):
        with mock.patch.object(Output, 'select',
                               return_value=[Output(id=0, number=2),
                                             Output(id=1, number=40, module_type='D', room=Room(id=2, number=3))]), \
             mock.patch.object(self.master_controller, 'load_output',
                               side_effect=lambda output_id: OutputDTO(id=output_id)), \
             mock.patch.object(self.master_controller, 'load_output_status',
                               return_value=[{'id': 2, 'status': False, 'dimmer': 0},
                                             {'id': 40, 'status': True, 'dimmer': 50}]):
            self.controller._sync_state()
            status = self.controller.get_output_statuses()
            assert len(status) == 2
            assert OutputStateDTO(id=2, status=False) in status
            assert OutputStateDTO(id=40, status=True, dimmer=50) in status

    def test_load_output(self):
        with mock.patch.object(Output, 'get', return_value=Output(id=1, number=42, room=Room(id=2, number=3))), \
             mock.patch.object(self.master_controller, 'load_output',
                               return_value=OutputDTO(id=42)) as load:
            output = self.controller.load_output(42)
            assert output == OutputDTO(id=42, room=3)
            load.assert_called_with(output_id=42)

    def test_load_outputs(self):
        with mock.patch.object(Output, 'select', return_value=[Output(id=1, number=42, room=Room(id=2, number=3))]), \
             mock.patch.object(self.master_controller, 'load_output',
                               return_value=OutputDTO(id=42)) as load:
            outputs = self.controller.load_outputs()
            assert OutputDTO(id=42, room=3) in outputs
            load.assert_called_with(output_id=42)


class OutputStateCacheTest(unittest.TestCase):
    def test_update(self):
        cache = OutputStateCache()

        cache.update_outputs([OutputDTO(id=0),
                              OutputDTO(id=1),
                              OutputDTO(id=2)])
        current_state = cache.get_state()
        assert {0: OutputStateDTO(id=0),
                1: OutputStateDTO(id=1),
                2: OutputStateDTO(id=2)} == current_state

        # Everything is off.
        assert cache.handle_change(0, {'status': False}) is None
        assert cache.handle_change(1, {'status': False}) is None
        assert cache.handle_change(2, {'status': False}) is None

        # Turn two outputs on.
        assert cache.handle_change(0, {'status': False}) is None
        change = cache.handle_change(2, {'status': True})
        assert change.state.status == True
        change = cache.handle_change(1, {'status': True})
        assert change.state.status == True

        # Turn one outputs off again.
        assert cache.handle_change(0, {'status': False}) is None
        change = cache.handle_change(1, {'status': False})
        assert change.state.status == False

        # Change dimmer value.
        assert cache.handle_change(0, {'dimmer': 0}) is None
        change = cache.handle_change(1, {'status': True, 'dimmer': 100})
        assert change.state.dimmer == 100
        change = cache.handle_change(1, {'dimmer': 50})
        assert change.state.dimmer == 50

        # Change lock.
        assert cache.handle_change(0, {'locked': False}) is None
        change = cache.handle_change(1, {'locked': True})
        assert change.state.locked == True
