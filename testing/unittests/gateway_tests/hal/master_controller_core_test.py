from __future__ import absolute_import

import copy
import time
import unittest

import mock
from six.moves import map
from six.moves.queue import Queue

from enums import HardwareType, OutputType
import gateway.hal.master_controller_core
from gateway.dto import InputDTO, OutputStatusDTO, OutputDTO, PulseCounterDTO
from gateway.dto.input import InputStatusDTO
from gateway.hal.master_controller_core import MasterCoreController
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import SetTestMode
from master.core.can_feedback import CANFeedbackController
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer
from master.core.memory_models import InputConfiguration, \
    InputModuleConfiguration, OutputConfiguration, OutputModuleConfiguration, \
    SensorModuleConfiguration, ShutterConfiguration, GlobalConfiguration
from master.core.system_value import Dimmer
from mocked_core_helper import MockedCore


class MasterCoreControllerTest(unittest.TestCase):
    """ Tests for MasterCoreController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.mocked_core = MockedCore()
        self.controller = self.mocked_core.controller
        self.pubsub = self.mocked_core.pubsub
        self.return_data = self.mocked_core.return_data

        # Provide wide set of configured modules for testing purposes
        global_configuration = GlobalConfiguration()
        global_configuration.number_of_output_modules = 50
        global_configuration.number_of_input_modules = 50
        global_configuration.number_of_sensor_modules = 50
        global_configuration.number_of_can_control_modules = 50
        global_configuration.save()

        # For testing purposes, remove read-only flag from certain properties
        for field_name in ['device_type', 'address', 'firmware_version']:
            for model_type in [OutputModuleConfiguration, InputModuleConfiguration, SensorModuleConfiguration]:
                if hasattr(model_type, '_{0}'.format(field_name)):
                    getattr(model_type, '_{0}'.format(field_name))._read_only = False
                else:
                    getattr(model_type, field_name)._read_only = False

    def test_master_output_event(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        self.pubsub.subscribe_master_events(PubSub.MasterTopics.OUTPUT, _on_event)

        events = []
        self.controller._handle_event({'type': 0, 'device_nr': 0, 'action': 0, 'data': bytearray([255, 0, 0, 0])})
        self.controller._handle_event({'type': 0, 'device_nr': 2, 'action': 1, 'data': bytearray([128, 2, 0xff, 0xfe])})
        self.controller._handle_event({'type': 0, 'device_nr': 4, 'action': 2, 'data': bytearray([1, 0, 0, 0])})
        self.controller._handle_event({'type': 0, 'device_nr': 6, 'action': 2, 'data': bytearray([0, 0, 0, 0])})
        self.pubsub._publish_all_events(blocking=False)
        self.assertEqual([MasterEvent(MasterEvent.Types.OUTPUT_STATUS, {'state': OutputStatusDTO(id=0, status=False, dimmer=100, ctimer=0)}),
                          MasterEvent(MasterEvent.Types.OUTPUT_STATUS, {'state': OutputStatusDTO(id=2, status=True, dimmer=50, ctimer=65534)}),
                          MasterEvent(MasterEvent.Types.OUTPUT_STATUS, {'state': OutputStatusDTO(id=4, locked=True)}),
                          MasterEvent(MasterEvent.Types.OUTPUT_STATUS, {'state': OutputStatusDTO(id=6, locked=False)})],
                         events)

    def test_master_shutter_event(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        self.pubsub.subscribe_master_events(PubSub.MasterTopics.SHUTTER, _on_event)

        self.controller._output_states = {0: OutputStatusDTO(id=0, status=False),
                                          10: OutputStatusDTO(id=10, status=False),
                                          11: OutputStatusDTO(id=11, status=False)}
        self.controller._output_shutter_map = {10: 1, 11: 1}
        self.controller._shutter_status = {1: (False, False)}
        self.pubsub._publish_all_events(blocking=False)

        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy):
            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 10, 'action': 0, 'data': [0, 0, 0, 0]})
            self.controller._handle_event({'type': 0, 'device_nr': 11, 'action': 0, 'data': [0, 0, 0, 0]})
            self.pubsub._publish_all_events(blocking=False)
            assert [] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 10, 'action': 1, 'data': [0, 0, 0, 0]})
            self.pubsub._publish_all_events(blocking=False)
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_up', 'location': {'room_id': 255}})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 11, 'action': 1, 'data': [0, 0, 0, 0]})
            self.pubsub._publish_all_events(blocking=False)
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'stopped', 'location': {'room_id': 255}})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 10, 'action': 0, 'data': [0, 0, 0, 0]})
            self.pubsub._publish_all_events(blocking=False)
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_down', 'location': {'room_id': 255}})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 11, 'action': 0, 'data': [0, 0, 0, 0]})
            self.pubsub._publish_all_events(blocking=False)
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'stopped', 'location': {'room_id': 255}})] == events

    def test_master_shutter_refresh(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        self.pubsub.subscribe_master_events(PubSub.MasterTopics.SHUTTER, _on_event)

        output_status = [OutputStatusDTO(id=0, status=False, dimmer=0),
                         OutputStatusDTO(id=1, status=False, dimmer=0),
                         OutputStatusDTO(id=10, status=False, dimmer=0),
                         OutputStatusDTO(id=11, status=False, dimmer=0)]
        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy), \
             mock.patch.object(self.controller, 'load_output_status', return_value=output_status):
            events = []
            self.controller._refresh_shutter_states()
            self.pubsub._publish_all_events(blocking=False)
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'stopped', 'location': {'room_id': 255}})] == events

        output_status = [OutputStatusDTO(id=0, status=False, dimmer=0),
                         OutputStatusDTO(id=1, status=True, dimmer=0),
                         OutputStatusDTO(id=10, status=True, dimmer=0),
                         OutputStatusDTO(id=11, status=False, dimmer=0)]
        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy), \
             mock.patch.object(self.controller, 'load_output_status', return_value=output_status):
            events = []
            self.controller._refresh_shutter_states()
            self.pubsub._publish_all_events(blocking=False)
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_up', 'location': {'room_id': 255}})] == events

        output_status = [OutputStatusDTO(id=0, status=False, dimmer=0),
                         OutputStatusDTO(id=1, status=True, dimmer=0),
                         OutputStatusDTO(id=10, status=False, dimmer=0),
                         OutputStatusDTO(id=11, status=True, dimmer=0)]
        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy), \
             mock.patch.object(self.controller, 'load_output_status', return_value=output_status):
            events = []
            self.controller._refresh_shutter_states()
            self.pubsub._publish_all_events(blocking=False)
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_down', 'location': {'room_id': 255}})] == events

    def test_input_module_type(self):
        with mock.patch.object(gateway.hal.master_controller_core, 'InputConfiguration',
                               return_value=get_core_input_dummy(1)):
            data = self.controller.get_input_module_type(1)
            self.assertEqual('I', data)

    def test_load_input(self):
        data = self.controller.load_input(1)
        self.assertEqual(data.id, 1)

    def test_load_inputs(self):
        global_configuration = GlobalConfiguration()
        global_configuration.number_of_input_modules = 2
        global_configuration.save()

        input_modules = list(map(get_core_input_dummy, range(16)))
        with mock.patch.object(gateway.hal.master_controller_core, 'InputConfiguration',
                               side_effect=input_modules):
            inputs = self.controller.load_inputs()
            self.assertEqual([x.id for x in inputs], list(range(16)))

    def test_save_inputs(self):
        data = [InputDTO(id=1, name='foo', module_type='I'),
                InputDTO(id=2, name='bar', module_type='I')]
        input_mock = mock.Mock(InputConfiguration)
        with mock.patch.object(InputConfiguration, 'deserialize', return_value=input_mock) as deserialize, \
                mock.patch.object(input_mock, 'save', return_value=None) as save:
            self.controller.save_inputs(data)
            self.assertIn(mock.call({'id': 1, 'name': 'foo'}), deserialize.call_args_list)
            self.assertIn(mock.call({'id': 2, 'name': 'bar'}), deserialize.call_args_list)
            save.assert_called_with(commit=False)

    def test_save_outputs(self):
        self.controller.save_outputs([
            OutputDTO(1, name='foo', module_type='O', output_type=OutputType.LIGHT),
            OutputDTO(2, name='bar', module_type='O', output_type=OutputType.OUTLET)
        ])
        output = OutputConfiguration(1)
        self.assertEqual(output.name, 'foo')
        self.assertEqual(output.output_type, 255)
        output = OutputConfiguration(2)
        self.assertEqual(output.name, 'bar')
        self.assertEqual(output.output_type, 0)

    def test_save_outputs_shutter_link(self):
        module = OutputModuleConfiguration(1)
        module.shutter_config.are_01_outputs = False  # shutter:4 outputs:8,9
        module.save()

        def assert_existing_shutter_config():
            module = OutputModuleConfiguration(1)
            self.assertFalse(module.shutter_config.are_01_outputs)
            self.assertTrue(module.shutter_config.are_45_outputs)
            self.assertTrue(module.shutter_config.are_67_outputs)

        # Convert to shutter
        self.controller.save_outputs([
            OutputDTO(11, name='DOWN', module_type='O', output_type=OutputType.SHUTTER_RELAY),  # output -> shutter
        ])
        output = OutputConfiguration(11)
        self.assertEqual(output.name, 'DOWN')
        self.assertEqual(output.output_type, 127)
        self.assertFalse(output.module.shutter_config.are_23_outputs)
        output = OutputConfiguration(10)
        self.assertEqual(output.output_type, 127)  # both outputs changed
        assert_existing_shutter_config()
        shutter = ShutterConfiguration(5)
        self.assertEqual(shutter.outputs.output_0, 10)
        self.assertEqual(shutter.outputs.output_1, 11)

        # Unlink shutter
        self.controller.save_outputs([
            OutputDTO(10, name='UP', module_type='O', output_type=OutputType.OUTLET),  # shutter -> output
        ])
        output = OutputConfiguration(10)
        self.assertEqual(output.name, 'UP')
        self.assertEqual(output.output_type, 0)
        self.assertTrue(output.module.shutter_config.are_23_outputs)
        output = OutputConfiguration(11)
        self.assertEqual(output.output_type, 0)  # both outputs changed
        assert_existing_shutter_config()
        shutter = ShutterConfiguration(5)
        self.assertEqual(shutter.outputs.output_0, 510)  # disabled
        self.assertEqual(shutter.outputs.output_1, 511)

    def test_save_outputs_shutter_dynamic_outputs(self):
        module = OutputModuleConfiguration(1)
        module.shutter_config.are_01_outputs = False
        module.save()

        shutter = ShutterConfiguration(0)
        shutter.outputs.output_0 = 8  # shutter:0, outputs:8,9
        shutter.save()

        # Convert to shutter
        self.controller.save_outputs([
            OutputDTO(9, name='UP', module_type='O', output_type=OutputType.OUTLET),
        ])
        output = OutputConfiguration(9)
        self.assertEqual(output.output_type, 0)
        self.assertTrue(output.module.shutter_config.are_01_outputs)
        self.assertTrue(output.module.shutter_config.are_23_outputs)
        shutter = ShutterConfiguration(0)
        self.assertEqual(shutter.outputs.output_0, 510)  # disabled
        self.assertEqual(shutter.outputs.output_1, 511)

    def test_inputs_with_status(self):
        from gateway.hal.master_controller_core import MasterInputState
        with mock.patch.object(MasterInputState, 'get_inputs', return_value=[]) as get:
            self.controller.load_input_status()
            get.assert_called_with()

    def test_event_consumer(self):
        with mock.patch.object(gateway.hal.master_controller_core, 'BackgroundConsumer',
                               return_value=None) as new_consumer:
            _ = MasterCoreController()
            expected_call = mock.call(CoreAPI.event_information(), 0, mock.ANY)
            self.assertIn(expected_call, new_consumer.call_args_list)

    def test_subscribe_input_events(self):
        consumer_list = []

        def new_consumer(*args):
            consumer = BackgroundConsumer(*args)
            consumer_list.append(consumer)
            return consumer

        subscriber = mock.Mock()
        with mock.patch.object(gateway.hal.master_controller_core, 'BackgroundConsumer',
                               side_effect=new_consumer) as new_consumer:
            _ = MasterCoreController()
        self.pubsub.subscribe_master_events(PubSub.MasterTopics.INPUT, subscriber.callback)

        new_consumer.assert_called()
        event_data = {'type': 1, 'action': 1, 'device_nr': 2,
                      'data': {}}
        with mock.patch.object(Queue, 'get', return_value=event_data):
            consumer_list[0].deliver()
        self.pubsub._publish_all_events(blocking=False)

        expected_event = MasterEvent.deserialize({'type': 'INPUT_CHANGE',
                                                  'data': {'state': InputStatusDTO(id=2, status=True)}})
        subscriber.callback.assert_called_with(expected_event)

    def test_get_modules(self):
        from master.core.memory_models import (
            InputModuleConfiguration, OutputModuleConfiguration, SensorModuleConfiguration,
            GlobalConfiguration
        )
        global_configuration = GlobalConfiguration()
        global_configuration.number_of_output_modules = 5
        global_configuration.number_of_input_modules = 4
        global_configuration.number_of_sensor_modules = 2
        global_configuration.number_of_can_control_modules = 1
        global_configuration.save()
        for module_id, module_class, device_type, address in [(0, InputModuleConfiguration, 'I', '{0}.123.123.123'.format(ord('I'))),
                                                              (1, InputModuleConfiguration, 'i', '{0}.123.123.123'.format(ord('i'))),
                                                              (2, InputModuleConfiguration, 'i', '{0}.000.000.000'.format(ord('i'))),
                                                              (3, InputModuleConfiguration, 'b', '{0}.123.132.123'.format(ord('b'))),
                                                              (0, OutputModuleConfiguration, 'o', '{0}.000.000.000'.format(ord('o'))),
                                                              (1, OutputModuleConfiguration, 'o', '{0}.000.000.001'.format(ord('o'))),
                                                              (2, OutputModuleConfiguration, 'o', '{0}.000.000.002'.format(ord('o'))),
                                                              (3, OutputModuleConfiguration, 'o', '{0}.123.123.123'.format(ord('o'))),
                                                              (4, OutputModuleConfiguration, 'O', '{0}.123.123.123'.format(ord('O'))),
                                                              (0, SensorModuleConfiguration, 's', '{0}.123.123.123'.format(ord('s'))),
                                                              (1, SensorModuleConfiguration, 'T', '{0}.123.123.123'.format(ord('T')))]:
            instance = module_class(module_id)
            instance.device_type = device_type
            instance.address = address
            instance.save()

        self.assertEqual({'can_inputs': ['I', 'T', 'C', 'E'],
                          'inputs': ['I', 'i', 'J', 'T'],
                          'outputs': ['P', 'P', 'P', 'o', 'O'],
                          'shutters': []}, self.controller.get_modules())

    def test_master_eeprom_event(self):
        master_event = MasterEvent(MasterEvent.Types.EEPROM_CHANGE, {})
        self.controller._output_last_updated = 1603178386.0
        self.pubsub.publish_master_event(PubSub.MasterTopics.EEPROM, master_event)
        self.pubsub._publish_all_events(blocking=False)
        assert self.controller._output_last_updated == 0

    def test_can_feedback_controller_calls(self):
        with mock.patch.object(CANFeedbackController, 'load_global_led_feedback_configuration') as call:
            self.controller.load_global_feedback(0)
            call.assert_called_once()

        with mock.patch.object(CANFeedbackController, 'load_global_led_feedback_configuration') as call:
            self.controller.load_global_feedbacks()
            call.assert_called_once()

        with mock.patch.object(CANFeedbackController, 'save_global_led_feedback_configuration') as call:
            self.controller.save_global_feedbacks([])
            call.assert_called_once()

        with mock.patch.object(CANFeedbackController, 'load_output_led_feedback_configuration') as call:
            self.controller.load_output(0)
            call.assert_called_once()

        with mock.patch.object(CANFeedbackController, 'save_output_led_feedback_configuration') as call:
            self.controller.save_outputs([OutputDTO(id=0)])
            call.assert_called_once()

    def test_save_pulse_counters(self):
        self.return_data['GC'] = {'input': 1}
        module = InputModuleConfiguration(0)
        module.device_type = 'I'
        module.save()
        expected_pulse_counters = [PulseCounterDTO(id=0, input_id=4, persistent=True, name='PulseCounter 0'),
                                   PulseCounterDTO(id=1, input_id=5, persistent=True, name='PulseCounter 1'),
                                   PulseCounterDTO(id=20, input_id=7, persistent=True, name='PulseCounter 20')]
        modules_to_save = copy.deepcopy(expected_pulse_counters)
        self.controller.save_pulse_counters(modules_to_save)
        self.assertEqual(expected_pulse_counters, [pc for pc in self.controller.load_pulse_counters()
                                                   if pc.id in [0, 1, 20]])
        expected_pulse_counters[1].input_id = None  # Remove Input ID - should clear the PC
        modules_to_save = copy.deepcopy(expected_pulse_counters)
        modules_to_save.pop(0)  # Remove first one to make sure PCs that are not passed in are not removed
        self.controller.save_pulse_counters(modules_to_save)
        self.assertEqual(expected_pulse_counters, [pc for pc in self.controller.load_pulse_counters()
                                                   if pc.id in [0, 1, 20]])


class MasterInputState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_handle_event(self):
        from gateway.hal.master_controller_core import MasterCoreEvent, MasterInputState
        state = MasterInputState()
        core_event = MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': 2, 'data': {}})
        with mock.patch.object(time, 'time', return_value=30):
            event = state.handle_event(core_event)
            expected_data = {'type': 'INPUT_CHANGE',
                             'data': {'state': InputStatusDTO(id=2, status=True)}}
            self.assertEqual(expected_data, event.serialize())
            self.assertIn({'id': 2, 'status': 1}, state.get_inputs())

    def test_refresh(self):
        from gateway.hal.master_controller_core import MasterCoreEvent, MasterInputState
        state = MasterInputState(interval=10)
        core_events = [
            MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': 1, 'data': {}}),
            MasterCoreEvent({'type': 1, 'action': 0, 'device_nr': 2, 'data': {}}),
        ]
        with mock.patch.object(time, 'time', return_value=30):
            for core_event in core_events:
                state.handle_event(core_event)
            self.assertTrue(state.should_refresh())
            events = state.refresh([0b00000110])
            self.assertEqual(1, len(events))

            expected_event = MasterEvent(event_type=MasterEvent.Types.INPUT_CHANGE,
                                         data={'state': InputStatusDTO(id=2, status=True)})
            self.assertIn(expected_event, events)
            self.assertFalse(state.should_refresh())

            events = state.refresh([0b00000110])
            self.assertEqual([], events)

        with mock.patch.object(time, 'time', return_value=60):
            self.assertTrue(state.should_refresh())

    def test_recent(self):
        from gateway.hal.master_controller_core import MasterCoreEvent, MasterInputState
        state = MasterInputState()
        with mock.patch.object(time, 'time', return_value=0):
            core_event = MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': 1, 'data': {}})
            state.handle_event(core_event)
            self.assertEqual([1], state.get_recent())

        with mock.patch.object(time, 'time', return_value=30):
            for i in range(2, 10):
                core_event = MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': i, 'data': {}})
                state.handle_event(core_event)
            devices = state.get_recent()
            self.assertEqual(5, len(devices))
            self.assertNotIn(1, devices)

        with mock.patch.object(time, 'time', return_value=60):
            self.assertEqual(0, len(state.get_recent()))

        with mock.patch.object(time, 'time', return_value=60):
            state.handle_event(MasterCoreEvent({'type': 1, 'action': 0, 'device_nr': 1, 'data': {}}))
            state.handle_event(MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': 2, 'data': {}}))
            devices = state.get_recent()
            self.assertIn(1, devices)
            self.assertNotIn(2, devices)

    def test_dimmer_stability(self):
        # Validates a stable conversion:
        # +----------------------> Original percentage set by external user -> `percentage` in test below
        # |    +-----------------> Original value converted to svt (precision loss) -> `svt` in test below
        # |    |    +------------> Recovered percentage -> `recovered_percentage` in test below
        # |    |    |    +-------> New svt based on recovered percentage (should be stable with first svt conversion) -> `new_svt`in test below
        # |    |    |    |    +--> New percentage (should be stable with recovered percentage) -> `new_percentage` in test below
        # 0 -> 0 -> 0 -> 0 -> 0
        # 1 -> 0 -> 0 -> 0 -> 0
        # 2 -> 1 -> 2 -> 1 -> 2
        # 3 -> 1 -> 2 -> 1 -> 2
        for percentage in range(0, 101):
            svt = Dimmer.dimmer_to_system_value(percentage)
            recovered_percentage = Dimmer.system_value_to_dimmer(svt)
            new_svt = Dimmer.dimmer_to_system_value(recovered_percentage)
            self.assertEqual(svt, new_svt)
            new_percentage = Dimmer.system_value_to_dimmer(new_svt)
            self.assertEqual(recovered_percentage, new_percentage)


def get_core_output_dummy(i):
    return OutputConfiguration.deserialize({
        'id': i,
        'name': 'foo',
        'module': {'id': i // 8,
                   'device_type': 'O',
                   'address': '0.0.0.0',
                   'firmware_version': '0.0.1'}
    })


def get_core_input_dummy(i):
    return InputConfiguration.deserialize({
        'id': i,
        'name': 'foo',
        'module': {'id': i // 8,
                   'device_type': 'I',
                   'address': '0.0.0.0',
                   'firmware_version': '0.0.1'}
    })


def get_core_shutter_dummy(i):
    return ShutterConfiguration.deserialize({
        'id': i,
        'name': 'foo',
        'groups': {},
        'outputs': {'output_0': 10 * i if i > 0 else 255,
                    'output_1': 10 * i + 1 if i > 0 else 255},
    })
