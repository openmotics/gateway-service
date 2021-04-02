"""
# Copyright (C) 2016 OpenMotics BV
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
from __future__ import absolute_import

import time
import unittest

import mock

import gateway.hal.master_controller_classic
import master.classic.master_api
import master.classic.master_communicator
from gateway.dto import InputDTO, OutputDTO, OutputStateDTO
from gateway.hal.master_controller_classic import MasterClassicController
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Scope, SetTestMode, SetUpTestInjections
from master.classic.eeprom_controller import EepromController
from master.classic.eeprom_models import InputConfiguration
from master.classic.inputs import InputStatus
from master.classic.master_communicator import BackgroundConsumer
from master.classic.validationbits import ValidationBitStatus


class MasterClassicControllerTest(unittest.TestCase):
    """ Tests for MasterClassicController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_input_module_type(self):
        input_data = {'id': 1, 'module_type': 'I'}
        controller = get_classic_controller_dummy([
            InputConfiguration.deserialize(input_data)
        ])
        data = controller.get_input_module_type(1)
        self.assertEqual(data, 'I')

    def test_load_input(self):
        input_data = {'id': 1, 'module_type': 'I', 'name': 'foo', 'action': 255,
                      'basic_actions': '', 'invert': 255, 'can': ' '}
        controller = get_classic_controller_dummy([
            InputConfiguration.deserialize(input_data)
        ])
        data = controller.load_input(1)
        self.assertEqual(data.id, 1)

    def test_load_input_with_invalid_type(self):
        input_data = {'id': 1, 'module_type': 'O', 'name': 'foo', 'action': 255,
                      'basic_actions': '', 'invert': 255, 'can': ' '}
        controller = get_classic_controller_dummy([
            InputConfiguration.deserialize(input_data)
        ])
        self.assertRaises(TypeError, controller.load_input, 1)

    def test_load_inputs(self):
        input_data1 = {'id': 1, 'module_type': 'I', 'name': 'foo', 'action': 255,
                       'basic_actions': '', 'invert': 255, 'can': ' '}
        input_data2 = {'id': 2, 'module_type': 'I', 'name': 'foo', 'action': 255,
                       'basic_actions': '', 'invert': 255, 'can': ' '}
        controller = get_classic_controller_dummy([
            InputConfiguration.deserialize(input_data1),
            InputConfiguration.deserialize(input_data2)
        ])
        inputs = controller.load_inputs()
        self.assertEqual([x.id for x in inputs], [1, 2])

    def test_load_inputs_skips_invalid_type(self):
        input_data1 = {'id': 1, 'module_type': 'I', 'name': 'foo', 'action': 255,
                       'basic_actions': '', 'invert': 255, 'can': ' '}
        input_data2 = {'id': 2, 'module_type': 'O', 'name': 'foo', 'action': 255,
                       'basic_actions': '', 'invert': 255, 'can': ' '}
        controller = get_classic_controller_dummy([
            InputConfiguration.deserialize(input_data1),
            InputConfiguration.deserialize(input_data2)
        ])
        inputs = controller.load_inputs()
        self.assertEqual([x.id for x in inputs], [1])

    def test_input_event_consumer(self):
        with mock.patch.object(gateway.hal.master_controller_classic, 'BackgroundConsumer',
                               return_value=None) as consumer:
            controller = get_classic_controller_dummy()
            controller._register_version_depending_background_consumers()
            expected_call = mock.call(master.classic.master_api.input_list((3, 143, 102)), 0, mock.ANY)
            self.assertIn(expected_call, consumer.call_args_list)

    def test_subscribe_input_events(self):
        consumer_list = []

        def new_consumer(*args):
            consumer = BackgroundConsumer(*args)
            consumer_list.append(consumer)
            return consumer

        subscriber = mock.Mock()
        with mock.patch.object(gateway.hal.master_controller_classic, 'BackgroundConsumer',
                               side_effect=new_consumer) as new_consumer:
            controller = get_classic_controller_dummy()
            pubsub = get_pubsub()
            controller._register_version_depending_background_consumers()
            controller._input_config = {1: InputDTO(id=1)}  # TODO: cleanup
            pubsub.subscribe_master_events(PubSub.MasterTopics.INPUT, subscriber.callback)
            new_consumer.assert_called()
            consumer_list[-2].deliver({'input': 1})
            pubsub._publish_all_events()
            try:
                consumer_list[-2]._consume()
            except:
                pass  # Just ensure it has at least consumed once
            expected_event = MasterEvent.deserialize({'type': 'INPUT_CHANGE',
                                                      'data': {'id': 1,
                                                               'status': True,
                                                               'location': {'room_id': 255}}})
            subscriber.callback.assert_called_with(expected_event)

    def test_get_inputs_with_status(self):
        controller = get_classic_controller_dummy()
        with mock.patch.object(InputStatus, 'get_inputs', return_value=[]) as get:
            controller.get_inputs_with_status()
            self.assertIn(mock.call(), get.call_args_list)

    def test_get_recent_inputs(self):
        controller = get_classic_controller_dummy()
        with mock.patch.object(InputStatus, 'get_recent', return_value=[]) as get:
            controller.get_recent_inputs()
            self.assertIn(mock.call(), get.call_args_list)

    def test_master_output_event(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        classic = get_classic_controller_dummy()
        pubsub = get_pubsub()
        pubsub.subscribe_master_events(PubSub.MasterTopics.OUTPUT, _on_event)
        classic._output_config = {0: OutputDTO(id=0),
                                  1: OutputDTO(id=1),
                                  2: OutputDTO(id=2, room=3)}

        pubsub._publish_all_events()
        events = []
        classic._on_master_output_event({'outputs': [(0, 0), (2, 5)]})
        pubsub._publish_all_events()
        self.assertEqual(events, [MasterEvent('OUTPUT_STATUS', {'state': OutputStateDTO(id=0, status=True, dimmer=0)}),
                                  MasterEvent('OUTPUT_STATUS', {'state': OutputStateDTO(id=1, status=False)}),
                                  MasterEvent('OUTPUT_STATUS', {'state': OutputStateDTO(id=2, status=True, dimmer=5)})])

    def test_validation_bits_passthrough(self):
        # Important note: bits are ordened per byte, so the sequence is like:
        # [[7, 6, 5, 4, 3, 2, 1, 0], [15, 14, 13, 12, 11, 10, 9, 8], [23, 22, ...], ...]
        bit_data = [0b00000010, 0b00000000, 0b00000000, 0b00000000,
                    0b00000000, 0b00000000, 0b00000000, 0b00000000,
                    0b00000000, 0b00000000, 0b00000000, 0b00000000,
                    0b00000000, 0b00000000, 0b00000000, 0b00000000,
                    0b00000000, 0b00000000, 0b00000000, 0b00000000,
                    0b00000000, 0b00000000, 0b00000000, 0b00000000,
                    0b00000000, 0b00000000, 0b00000000, 0b00000000,
                    0b00000000, 0b00000000, 0b00000000, 0b01000000]

        def _do_command(cmd, fields):
            start = fields['number'] // 8
            return {'data': bit_data[start:start + 11]}

        classic = get_classic_controller_dummy()
        classic._master_communicator.do_command = _do_command
        classic._master_version = (0, 0, 0)
        pubsub = get_pubsub()

        bits = classic.load_validation_bits()
        self.assertIsNone(bits)

        classic._master_version = (3, 143, 102)

        bits = classic.load_validation_bits()
        expected_bits = {i: False for i in range(256)}
        expected_bits[1] = True
        expected_bits[254] = True
        self.assertEqual(expected_bits, bits)

        events = []

        def _on_event(master_event):
            if master_event.type == MasterEvent.Types.OUTPUT_STATUS:
                events.append(master_event.data)

        pubsub.subscribe_master_events(PubSub.MasterTopics.OUTPUT, _on_event)
        classic._validation_bits = ValidationBitStatus(on_validation_bit_change=classic._validation_bit_changed)
        classic._output_config = {0: OutputDTO(0, lock_bit_id=5)}
        pubsub._publish_all_events()

        classic._refresh_validation_bits()
        classic._on_master_validation_bit_change(5, True)
        classic._on_master_validation_bit_change(6, True)
        classic._on_master_validation_bit_change(5, False)
        pubsub._publish_all_events()
        self.assertEqual(events, [{'state': OutputStateDTO(id=0, locked=False)},
                                  {'state': OutputStateDTO(id=0, locked=True)},
                                  {'state': OutputStateDTO(id=0, locked=False)}])

    def test_module_discover(self):
        subscriber = mock.Mock()
        subscriber.callback.return_value = None

        with mock.patch.object(MasterClassicController, '_synchronize') as synchronize:
            controller = get_classic_controller_dummy([])
            pubsub = get_pubsub()

            invalidate = controller._eeprom_controller.invalidate_cache.call_args_list

            try:
                controller.start()
                controller.module_discover_start(30)
                time.sleep(0.2)
                assert len(synchronize.call_args_list) == 1
                assert len(invalidate) == 0

                pubsub.subscribe_master_events(PubSub.MasterTopics.MODULE, subscriber.callback)
                controller.module_discover_stop()
                pubsub._publish_all_events()
                time.sleep(0.2)
                assert len(invalidate) == 1

                assert len(subscriber.callback.call_args_list) == 1
                event = subscriber.callback.call_args_list[0][0][0]
                assert event.type == MasterEvent.Types.MODULE_DISCOVERY
            finally:
                controller.stop()

    def test_module_discover_timeout(self):
        controller = get_classic_controller_dummy()
        with mock.patch.object(controller, 'module_discover_stop') as stop:
            controller.module_discover_start(0)
            time.sleep(0.2)
            stop.assert_called_with()

    def test_master_maintenance_event(self):
        controller = get_classic_controller_dummy()
        pubsub = get_pubsub()
        with mock.patch.object(controller._eeprom_controller, 'invalidate_cache') as invalidate:
            master_event = MasterEvent(MasterEvent.Types.MAINTENANCE_EXIT, {})
            pubsub.publish_master_event(PubSub.MasterTopics.MAINTENANCE, master_event)
            pubsub._publish_all_events()
            invalidate.assert_called()

    def test_master_eeprom_event(self):
        controller = get_classic_controller_dummy()
        controller._input_last_updated = 1603178386.0
        pubsub = get_pubsub()
        master_event = MasterEvent(MasterEvent.Types.EEPROM_CHANGE, {})
        pubsub.publish_master_event(PubSub.MasterTopics.EEPROM, master_event)
        pubsub._publish_all_events()
        assert controller._input_last_updated == 0.0


@Scope
def get_classic_controller_dummy(inputs=None):
    communicator_mock = mock.Mock()
    eeprom_mock = mock.Mock(EepromController)
    eeprom_mock.invalidate_cache.return_value = None
    eeprom_mock.read.return_value = inputs[0] if inputs else []
    eeprom_mock.read_all.return_value = inputs
    SetUpTestInjections(configuration_controller=mock.Mock(),
                        master_communicator=communicator_mock,
                        eeprom_controller=eeprom_mock,
                        pubsub=PubSub())

    controller = MasterClassicController()
    controller._master_version = (3, 143, 102)
    return controller


@Inject
def get_pubsub(pubsub=INJECTED):
    return pubsub
