from __future__ import absolute_import
import time
import unittest
from six.moves.queue import Queue

import gateway.hal.master_controller_core
import mock
import xmlrunner
from gateway.hal.master_event import MasterEvent
from ioc import Scope, SetTestMode, SetUpTestInjections
from gateway.dto import InputDTO
from master.classic import eeprom_models
from master.classic.eeprom_controller import EepromController
from master.core.core_api import CoreAPI
from master.core.memory_file import MemoryTypes, MemoryFile
from master.core.core_communicator import BackgroundConsumer
from master.core.memory_models import InputConfiguration
from master.core.ucan_communicator import UCANCommunicator
from master.core.rs485_communicator import RS485Communicator
from six.moves import map


class MasterCoreControllerTest(unittest.TestCase):
    """ Tests for MasterCoreController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_input_module_type(self):
        with mock.patch.object(gateway.hal.master_controller_core, 'InputConfiguration',
                               return_value=get_core_input_dummy(1)):
            controller = get_core_controller_dummy()
            data = controller.get_input_module_type(1)
            self.assertEqual('I', data)

    def test_load_input(self):
        controller = get_core_controller_dummy()
        with mock.patch.object(gateway.hal.master_controller_core, 'InputConfiguration',
                               return_value=get_core_input_dummy(1)):
            data = controller.load_input(1)
            self.assertEqual(data.id, 1)

    def test_load_inputs(self):
        input_modules = list(map(get_core_input_dummy, range(1, 17)))
        controller = get_core_controller_dummy({'output': 0, 'input': 2})
        with mock.patch.object(gateway.hal.master_controller_core, 'InputConfiguration',
                               side_effect=input_modules):
            inputs = controller.load_inputs()
            self.assertEqual([x.id for x in inputs], list(range(1, 17)))

    def test_save_inputs(self):
        controller = get_core_controller_dummy()
        data = [(InputDTO(id=1, name='foo', module_type='I'), ['id', 'name', 'module_type']),
                (InputDTO(id=2, name='bar', module_type='I'), ['id', 'name', 'module_type'])]
        input_mock = mock.Mock(InputConfiguration)
        with mock.patch.object(InputConfiguration, 'deserialize', return_value=input_mock) as deserialize, \
                mock.patch.object(input_mock, 'save', return_value=None) as save:
            controller.save_inputs(data)
            self.assertIn(mock.call({'id': 1, 'name': 'foo'}), deserialize.call_args_list)
            self.assertIn(mock.call({'id': 2, 'name': 'bar'}), deserialize.call_args_list)
            save.assert_called_with()

    def test_inputs_with_status(self):
        controller = get_core_controller_dummy()
        from gateway.hal.master_controller_core import MasterInputState
        with mock.patch.object(MasterInputState, 'get_inputs', return_value=[]) as get:
            controller.get_inputs_with_status()
            get.assert_called_with()

    def test_recent_inputs(self):
        controller = get_core_controller_dummy()
        from gateway.hal.master_controller_core import MasterInputState
        with mock.patch.object(MasterInputState, 'get_recent', return_value=[]) as get:
            controller.get_recent_inputs()
            get.assert_called_with()

    def test_event_consumer(self):
        with mock.patch.object(gateway.hal.master_controller_core, 'BackgroundConsumer',
                               return_value=None) as new_consumer:
            get_core_controller_dummy()
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
            controller = get_core_controller_dummy()
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
        memory = {}

        def _do_command(command, fields, timeout=None):
            _ = timeout
            if command.instruction == 'MR':
                page = fields['page']
                start = fields['start']
                length = fields['length']
                return {'data': memory.get(page, [255] * 256)[start:start + length]}
            if command.instruction == 'MW':
                page = fields['page']
                start = fields['start']
                page_data = memory.setdefault(page, [255] * 256)
                for index, data_byte in enumerate(fields['data']):
                    page_data[start + index] = data_byte

        controller = get_core_controller_dummy()
        controller._master_communicator.do_command = _do_command

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
                          'shutters': []}, controller.get_modules())


class MasterCoreControllerCompatibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_load_input(self):
        SetUpTestInjections(memory_files={MemoryTypes.EEPROM: mock.Mock()})
        core = get_core_controller_dummy()
        core_input_orm = get_core_input_dummy(1)
        with mock.patch.object(gateway.hal.master_controller_core, 'InputConfiguration',
                               return_value=core_input_orm):
            core_data = core.load_input(1)
        classic_input_orm = eeprom_models.InputConfiguration.deserialize({'id': 1,
                                                                          'name': 'foo',
                                                                          'module_type': 'I',
                                                                          'action': 255,
                                                                          'basic_actions': '',
                                                                          'invert': 255,
                                                                          'can': ' ',
                                                                          'event_enabled': False})
        classic = get_classic_controller_dummy([classic_input_orm])
        classic_data = classic.load_input(1)
        self.assertEqual(classic_data, core_data)


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


@Scope
def get_core_controller_dummy(command_data=None):
    from gateway.hal.master_controller_core import MasterCoreController
    from master.core.core_communicator import CoreCommunicator
    communicator_mock = mock.Mock(CoreCommunicator)
    communicator_mock.do_command.return_value = command_data or {}
    SetUpTestInjections(configuration_controller=mock.Mock(),
                        master_communicator=communicator_mock)
    SetUpTestInjections(memory_files={MemoryTypes.EEPROM: MemoryFile(MemoryTypes.EEPROM)},
                        ucan_communicator=UCANCommunicator(),
                        rs485_communicator=RS485Communicator())
    return MasterCoreController()


@Scope
def get_classic_controller_dummy(inputs):
    from gateway.hal.master_controller_classic import MasterClassicController
    eeprom_mock = mock.Mock(EepromController)
    eeprom_mock.read.return_value = inputs[0]
    eeprom_mock.read_all.return_value = inputs
    SetUpTestInjections(configuration_controller=mock.Mock(),
                        master_communicator=mock.Mock(),
                        eeprom_controller=eeprom_mock)
    return MasterClassicController()


def get_core_input_dummy(i):
    return InputConfiguration.deserialize({
        'id': i,
        'name': 'foo',
        'module': {'id': 20 + i,
                   'device_type': 'I',
                   'address': '0.0.0.0',
                   'firmware_version': '0.0.1'}
    })


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
