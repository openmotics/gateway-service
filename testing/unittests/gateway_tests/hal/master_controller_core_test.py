from __future__ import absolute_import

import time
import unittest

import mock
from six.moves import map
from six.moves.queue import Queue

import gateway.hal.master_controller_core
from gateway.config import ConfigurationController
from gateway.dto import InputDTO, OutputStateDTO
from gateway.hal.master_controller_classic import MasterClassicController
from gateway.hal.master_controller_core import MasterCoreController
from gateway.hal.master_event import MasterEvent
from ioc import Scope, SetTestMode, SetUpTestInjections
from master.classic import eeprom_models
from master.classic.eeprom_controller import EepromController
from master.classic.master_communicator import MasterCommunicator
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer, CoreCommunicator
from master.core.memory_file import MemoryFile, MemoryTypes
from master.core.memory_models import InputConfiguration, \
    OutputConfiguration, ShutterConfiguration, GlobalConfiguration
from master.core.slave_communicator import SlaveCommunicator
from master.core.ucan_communicator import UCANCommunicator


class MasterCoreControllerTest(unittest.TestCase):
    """ Tests for MasterCoreController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.memory = {}
        self.return_data = {}

        def _do_command(command, fields, timeout=None):
            _ = timeout
            if command.instruction == 'MR':
                page = fields['page']
                start = fields['start']
                length = fields['length']
                return {'data': self.memory.get(page, [255] * 256)[start:start + length]}
            elif command.instruction == 'MW':
                page = fields['page']
                start = fields['start']
                page_data = self.memory.setdefault(page, [255] * 256)
                for index, data_byte in enumerate(fields['data']):
                    page_data[start + index] = data_byte
            elif command.instruction in self.return_data:
                return self.return_data[command.instruction]
                return self.return_data[command.instruction]
            else:
                raise AssertionError('unexpected instruction "{}"'.format(command.instruction))

        self.communicator = mock.Mock(CoreCommunicator)
        self.communicator.do_command = _do_command
        SetUpTestInjections(master_communicator=self.communicator)

        eeprom_file = MemoryFile(MemoryTypes.EEPROM)
        eeprom_file._cache = self.memory
        SetUpTestInjections(configuration_controller=mock.Mock(ConfigurationController),
                            memory_files={MemoryTypes.EEPROM: eeprom_file,
                                          MemoryTypes.FRAM: MemoryFile(MemoryTypes.FRAM)},
                            ucan_communicator=UCANCommunicator(),
                            slave_communicator=SlaveCommunicator())
        self.controller = MasterCoreController()

    def test_master_output_event(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        self.controller.subscribe_event(_on_event)

        events = []
        self.controller._handle_event({'type': 0, 'device_nr': 0, 'action': 0, 'data': [None, 0, 0, 0]})
        self.controller._handle_event({'type': 0, 'device_nr': 2, 'action': 1, 'data': [100, 2, 0xff, 0xfe]})
        assert [MasterEvent('OUTPUT_STATUS', {'id': 0, 'status': False, 'dimmer': None, 'ctimer': None}),
                MasterEvent('OUTPUT_STATUS', {'id': 2, 'status': True, 'dimmer': 100, 'ctimer': 65534})] == events

    def test_master_shutter_event(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        self.controller.subscribe_event(_on_event)
        self.controller._output_states = {0: OutputStateDTO(id=0, status=False),
                                          10: OutputStateDTO(id=10, status=False),
                                          11: OutputStateDTO(id=11, status=False)}
        self.controller._output_shutter_map = {10: 1, 11: 1}
        self.controller._shutter_status = {1: (False, False)}

        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy):
            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 10, 'action': 0, 'data': [None, 0, 0, 0]})
            self.controller._handle_event({'type': 0, 'device_nr': 11, 'action': 0, 'data': [None, 0, 0, 0]})
            assert [MasterEvent('OUTPUT_STATUS', {'id': 10, 'status': False, 'dimmer': None, 'ctimer': None}),
                    MasterEvent('OUTPUT_STATUS', {'id': 11, 'status': False, 'dimmer': None, 'ctimer': None})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 10, 'action': 1, 'data': [None, 0, 0, 0]})
            assert [MasterEvent('OUTPUT_STATUS', {'id': 10, 'status': True, 'dimmer': None, 'ctimer': None}),
                    MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_up', 'location': {'room_id': 255}})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 11, 'action': 1, 'data': [None, 0, 0, 0]})
            assert [MasterEvent('OUTPUT_STATUS', {'id': 11, 'status': True, 'dimmer': None, 'ctimer': None}),
                    MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'stopped', 'location': {'room_id': 255}})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 10, 'action': 0, 'data': [None, 0, 0, 0]})
            assert [MasterEvent('OUTPUT_STATUS', {'id': 10, 'status': False, 'dimmer': None, 'ctimer': None}),
                    MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_down', 'location': {'room_id': 255}})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 11, 'action': 0, 'data': [None, 0, 0, 0]})
            assert [MasterEvent('OUTPUT_STATUS', {'id': 11, 'status': False, 'dimmer': None, 'ctimer': None}),
                    MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'stopped', 'location': {'room_id': 255}})] == events

    def test_master_shutter_refresh(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        self.controller.subscribe_event(_on_event)
        output_status = [{'device_nr': 0, 'status': False, 'dimmer': 0},
                         {'device_nr': 1, 'status': False, 'dimmer': 0},
                         {'device_nr': 10, 'status': False, 'dimmer': 0},
                         {'device_nr': 11, 'status': False, 'dimmer': 0}]
        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy), \
             mock.patch.object(self.controller, 'load_output_status', return_value=output_status):
            events = []
            self.controller._refresh_shutter_states()
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'stopped', 'location': {'room_id': 255}})] == events

        output_status = [{'device_nr': 0, 'status': False, 'dimmer': 0},
                         {'device_nr': 1, 'status': True, 'dimmer': 0},
                         {'device_nr': 10, 'status': True, 'dimmer': 0},
                         {'device_nr': 11, 'status': False, 'dimmer': 0}]
        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy), \
             mock.patch.object(self.controller, 'load_output_status', return_value=output_status):
            events = []
            self.controller._refresh_shutter_states()
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_up', 'location': {'room_id': 255}})] == events

        output_status = [{'device_nr': 0, 'status': False, 'dimmer': 0},
                         {'device_nr': 1, 'status': True, 'dimmer': 0},
                         {'device_nr': 10, 'status': False, 'dimmer': 0},
                         {'device_nr': 11, 'status': True, 'dimmer': 0}]
        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy), \
             mock.patch.object(self.controller, 'load_output_status', return_value=output_status):
            events = []
            self.controller._refresh_shutter_states()
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
        input_modules = list(map(get_core_input_dummy, range(1, 17)))
        self.return_data['GC'] = {'input': 2}
        with mock.patch.object(gateway.hal.master_controller_core, 'InputConfiguration',
                               side_effect=input_modules):
            inputs = self.controller.load_inputs()
            self.assertEqual([x.id for x in inputs], list(range(1, 17)))

    def test_save_inputs(self):
        data = [(InputDTO(id=1, name='foo', module_type='I'), ['id', 'name', 'module_type']),
                (InputDTO(id=2, name='bar', module_type='I'), ['id', 'name', 'module_type'])]
        input_mock = mock.Mock(InputConfiguration)
        with mock.patch.object(InputConfiguration, 'deserialize', return_value=input_mock) as deserialize, \
                mock.patch.object(input_mock, 'save', return_value=None) as save:
            self.controller.save_inputs(data)
            self.assertIn(mock.call({'id': 1, 'name': 'foo'}), deserialize.call_args_list)
            self.assertIn(mock.call({'id': 2, 'name': 'bar'}), deserialize.call_args_list)
            save.assert_called_with()

    def test_inputs_with_status(self):
        from gateway.hal.master_controller_core import MasterInputState
        with mock.patch.object(MasterInputState, 'get_inputs', return_value=[]) as get:
            self.controller.get_inputs_with_status()
            get.assert_called_with()

    def test_recent_inputs(self):
        from gateway.hal.master_controller_core import MasterInputState
        with mock.patch.object(MasterInputState, 'get_recent', return_value=[]) as get:
            self.controller.get_recent_inputs()
            get.assert_called_with()

    def test_event_consumer(self):
        with mock.patch.object(gateway.hal.master_controller_core, 'BackgroundConsumer',
                               return_value=None) as new_consumer:
            controller = MasterCoreController()
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
            controller = MasterCoreController()
        controller.subscribe_event(subscriber.callback)
        new_consumer.assert_called()
        event_data = {'type': 1, 'action': 1, 'device_nr': 2,
                      'data': {}}
        with mock.patch.object(Queue, 'get', return_value=event_data):
            consumer_list[0].deliver()
        expected_event = MasterEvent.deserialize({'type': 'INPUT_CHANGE',
                                                  'data': {'id': 2,
                                                           'status': True,
                                                           'location': {'room_id': 255}}})
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
        global_configuration.number_of_can_control_modules = 2
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
                             'data': {'id': 2,
                                      'status': True,
                                      'location': {'room_id': 255}}}
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
                                         data={'id': 2,
                                               'status': True,
                                               'location': {'room_id': 255}})
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


def get_core_output_dummy(i):
    return OutputConfiguration.deserialize({
        'id': i,
        'name': 'foo',
        'module': {'id': 20 + i,
                   'device_type': 'O',
                   'address': '0.0.0.0',
                   'firmware_version': '0.0.1'}
    })


def get_core_input_dummy(i):
    return InputConfiguration.deserialize({
        'id': i,
        'name': 'foo',
        'module': {'id': 20 + i,
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
