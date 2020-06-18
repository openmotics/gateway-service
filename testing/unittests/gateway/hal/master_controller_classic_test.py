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
import unittest

import gateway.hal.master_controller_classic
import master.classic.master_api
import master.classic.master_communicator
import mock
import xmlrunner
from ioc import Scope, SetTestMode, SetUpTestInjections
from gateway.dto import InputDTO, OutputDTO
from master.classic.eeprom_controller import EepromController
from master.classic.eeprom_models import InputConfiguration
from master.classic.inputs import InputStatus
from master.classic.master_communicator import BackgroundConsumer
from master.classic.validationbits import ValidationBitStatus
from master.classic.outputs import OutputStatus


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
                      'basic_actions': '', 'invert': 255, 'can': ' ', 'event_enabled': False}
        controller = get_classic_controller_dummy([
            InputConfiguration.deserialize(input_data)
        ])
        data = controller.load_input(1)
        self.assertEqual(data.id, 1)

    def test_load_input_with_invalid_type(self):
        input_data = {'id': 1, 'module_type': 'O', 'name': 'foo', 'action': 255,
                      'basic_actions': '', 'invert': 255, 'can': ' ', 'event_enabled': False}
        controller = get_classic_controller_dummy([
            InputConfiguration.deserialize(input_data)
        ])
        self.assertRaises(TypeError, controller.load_input, 1)

    def test_load_inputs(self):
        input_data1 = {'id': 1, 'module_type': 'I', 'name': 'foo', 'action': 255,
                       'basic_actions': '', 'invert': 255, 'can': ' ', 'event_enabled': False}
        input_data2 = {'id': 2, 'module_type': 'I', 'name': 'foo', 'action': 255,
                       'basic_actions': '', 'invert': 255, 'can': ' ', 'event_enabled': False}
        controller = get_classic_controller_dummy([
            InputConfiguration.deserialize(input_data1),
            InputConfiguration.deserialize(input_data2)
        ])
        inputs = controller.load_inputs()
        self.assertEqual([x.id for x in inputs], [1, 2])

    def test_load_inputs_skips_invalid_type(self):
        input_data1 = {'id': 1, 'module_type': 'I', 'name': 'foo', 'action': 255,
                       'basic_actions': '', 'invert': 255, 'can': ' ', 'event_enabled': False}
        input_data2 = {'id': 2, 'module_type': 'O', 'name': 'foo', 'action': 255,
                       'basic_actions': '', 'invert': 255, 'can': ' ', 'event_enabled': False}
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
            expected_call = mock.call(master.classic.master_api.input_list(None), 0, mock.ANY)
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
            controller._register_version_depending_background_consumers()
            controller._input_config = {1: InputDTO(id=1)}  # TODO: cleanup
            controller.subscribe_event(subscriber.callback)
            new_consumer.assert_called()
            consumer_list[-2].deliver({'input': 1})
            from gateway.hal.master_event import MasterEvent
            expected_event = MasterEvent.deserialize({'type': 'INPUT_CHANGE',
                                                      'data': {'id': 1,
                                                               'status': True,
                                                               'location': {'room_id': 255}}})
            subscriber.callback.assert_called_with(expected_event)

    def test_get_inputs_with_status(self):
        classic = get_classic_controller_dummy()
        with mock.patch.object(InputStatus, 'get_inputs', return_value=[]) as get:
            classic.get_inputs_with_status()
            self.assertIn(mock.call(), get.call_args_list)

    def test_get_recent_inputs(self):
        classic = get_classic_controller_dummy()
        with mock.patch.object(InputStatus, 'get_recent', return_value=[]) as get:
            classic.get_recent_inputs()
            self.assertIn(mock.call(), get.call_args_list)

    def test_validation_bits_passthrough(self):
        # Imporatnt note: bits are ordened per byte, so the sequence is like:
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
            start = fields['number'] / 8
            return {'data': bit_data[start:start + 11]}

        classic = get_classic_controller_dummy()
        classic._master_communicator.do_command = _do_command

        bits = classic.load_validation_bits()
        self.assertIsNone(bits)

        classic._master_version = (3, 143, 102)

        bits = classic.load_validation_bits()
        expected_bits = {i: False for i in range(256)}
        expected_bits[1] = True
        expected_bits[254] = True
        self.assertEqual(expected_bits, bits)

        events = []

        def _on_change(output_id, state):
            events.append((output_id, state))

        classic._validation_bits = ValidationBitStatus(on_validation_bit_change=classic._validation_bit_changed)
        classic._output_status = OutputStatus(on_output_change=_on_change)
        classic._output_config = {0: OutputDTO(0, lock_bit_id=5)}

        classic._refresh_validation_bits()
        classic._on_master_validation_bit_change(5, True)
        classic._on_master_validation_bit_change(6, True)
        classic._on_master_validation_bit_change(5, False)
        self.assertEqual([(0, {'on': False, 'locked': False, 'value': 0}),
                          (0, {'on': False, 'locked': True, 'value': 0}),
                          (0, {'on': False, 'locked': False, 'value': 0})], events)

@Scope
def get_classic_controller_dummy(inputs=None):
    from gateway.hal.master_controller_classic import MasterClassicController
    eeprom_mock = mock.Mock(EepromController)
    eeprom_mock.read.return_value = inputs[0] if inputs else []
    eeprom_mock.read_all.return_value = inputs
    SetUpTestInjections(configuration_controller=mock.Mock(),
                        master_communicator=mock.Mock(),
                        eeprom_controller=eeprom_mock)
    return MasterClassicController()


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
