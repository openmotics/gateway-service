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
"""
Module for communicating with the Master
"""
from __future__ import absolute_import

import logging
import json
import os
from datetime import datetime

from gateway.hal.master_controller_core import MasterCoreController
from master.core.core_communicator import CoreCommunicator
from master.core.memory_models import GlobalConfiguration, InputConfiguration
from master.core.basic_action import BasicAction
from master.core.fields import WordField, ByteField
from master.core.core_api import CoreAPI
from master.core.group_action import GroupActionController
from ioc import Inject, INJECTED, Singleton
from constants import OPENMOTICS_PREFIX

if False:  # MYPY
    from typing import List, Dict, Any, Union, Optional, TypeVar
    from master.core.memory_file import MemoryAddress
    from master.core.core_command import CoreCommandSpec
    from master.core.core_communicator import Consumer
    T_co = TypeVar('T_co', bound=None, covariant=True)

logger = logging.getLogger(__name__)


@Singleton
class DummyMemoryFile(object):
    """
    This dummy MemoryFile handles EEPROM reads and writes. It reads and writes to an in-memory buffer. This
    buffer is loaded from disk on startup, and is written to on every `commit`. This allows a service restart
    without loosing any EEPROM values. Remove the on-disk buffer for a clean start.
    """

    def __init__(self):
        self._eeprom_path = '{0}/etc/master_eeprom.json'.format(OPENMOTICS_PREFIX)
        self._memory = {}  # type: Dict[str, Dict[str, int]]
        if os.path.exists(self._eeprom_path):
            with open(self._eeprom_path, 'r') as fp:
                self._memory = json.load(fp)

    def start(self):
        pass

    def stop(self):
        pass

    def read(self, addresses, read_through=False):  # type: (List[MemoryAddress], bool) -> Dict[MemoryAddress, bytearray]
        response = {}  # type: Dict[MemoryAddress, bytearray]
        for address in addresses:
            data = bytearray()
            page_memory = self._memory.setdefault(str(address.page), {})
            for position in range(address.offset, address.offset + address.length):
                data.append(page_memory.get(str(position), 255))
            response[address] = data
        return response

    def write(self, data_map):  # type: (Dict[MemoryAddress, bytearray]) -> None
        for address, data in data_map.items():
            page_memory = self._memory.setdefault(str(address.page), {})
            for index, position in enumerate(range(address.offset, address.offset + address.length)):
                page_memory[str(position)] = data[index]

    def commit(self):
        with open(self._eeprom_path, 'w') as fp:
            json.dump(self._memory, fp, sort_keys=True, indent=4)


@Singleton
class DummyCommunicator(object):
    """
    This dummy Communicator handles commands to the (dummy) master. Some commands have an implementation
    where an appropriate return value is generated (based on EEPROM and/or state caches). It also generate events
    that would be the result of the executed actions. Command that are not implemented are logged.
    """

    @Inject
    def __init__(self, memory_file=INJECTED):
        self._memory_file = memory_file
        self._output_states = {}  # type: Dict[int, Dict[str, Any]]
        self._input_states = {}  # type: Dict[int, bool]
        self._consumers = []  # type: List[Consumer]
        self._event_command_spec = CoreAPI.event_information()
        self._word_helper = WordField('')
        self._byte_helper = ByteField('')

    def start(self):
        pass

    def stop(self):
        pass

    def __getattr__(self, attribute):
        if callable(getattr(CoreCommunicator, attribute)):
            def implementation(*args, **kwargs):
                logger.info('Got {0}({1}, {2})'.format(
                    attribute,
                    ', '.join(str(a) for a in args),
                    ', '.join('{0}={1}'.format(key, value) for key, value in kwargs.items()))
                )
                return {}
            return implementation

    def register_consumer(self, consumer):
        self._consumers.append(consumer)

    def get_communication_statistics(self):
        _ = self
        return {'calls_succeeded': [], 'calls_timedout': [],
                'bytes_written': 0, 'bytes_read': 0}

    def do_command(self, command, fields, timeout=2, bypass_blockers=None):
        # type: (CoreCommandSpec, Dict[str, Any], Union[T_co, int], Optional[List]) -> Union[T_co, Dict[str, Any]]
        """
        This method reads the command, executes actions and returns an appropriate response.
        """
        def _default_if_255(value, default):
            return value if value != 255 else default

        if command.instruction == b'GC':
            if command.request_fields[0]._data == bytearray([0]):  # type: ignore  # It's not a `Field` but a `LiteralBytesField`
                global_configuration = GlobalConfiguration()
                return {'type': 0,
                        'output': _default_if_255(global_configuration.number_of_output_modules, 0),
                        'input': _default_if_255(global_configuration.number_of_input_modules, 0),
                        'sensor': _default_if_255(global_configuration.number_of_sensor_modules, 0),
                        'ucan': _default_if_255(global_configuration.number_of_ucan_modules, 0),
                        'ucan_input': _default_if_255(global_configuration.number_of_can_inputs, 0),
                        'ucan_sensor': _default_if_255(global_configuration.number_of_can_sensors, 0),
                        'power_rs485': 1, 'power_can': 1}
        if command.instruction == b'BA':
            basic_action = BasicAction(action_type=fields['type'], action=fields['action'],
                                       device_nr=fields['device_nr'], extra_parameter=fields['extra_parameter'])
            self._process_basic_action(basic_action)
            return {'type': basic_action.action_type, 'action': basic_action.action,
                    'device_nr': basic_action.device_nr, 'extra_parameter': basic_action.extra_parameter}
        if command.instruction == b'PC':
            return {'series': fields['series'],
                    'counter_0': 0, 'counter_1': 0, 'counter_2': 0, 'counter_3': 0,
                    'counter_4': 0, 'counter_5': 0, 'counter_6': 0, 'counter_7': 0,
                    'crc126': 0}
        if command.instruction == b'TR':
            now = datetime.now()
            return {'info_type': 0,
                    'hours': now.hour, 'minutes': now.minute, 'seconds': now.second,
                    'weekday': now.isoweekday(),
                    'day': now.day, 'month': now.month, 'year': now.year - 2000}
        if command.instruction == b'ST':
            if command.request_fields[0]._data == bytearray([0]):  # type: ignore  # It's not a `Field` but a `LiteralBytesField`
                return {'info_type': 0,
                        'rs485_mode': 0,
                        'ba_debug_mode': 0}
            if command.request_fields[0]._data == bytearray([1]):  # type: ignore  # It's not a `Field` but a `LiteralBytesField`
                return {'info_type': 1,
                        'version': '0.1.0'}
            if command.request_fields[0]._data == bytearray([2]):  # type: ignore  # It's not a `Field` but a `LiteralBytesField`
                global_configuration = GlobalConfiguration()
                return {'info_type': 2,
                        'amount_output_modules': _default_if_255(global_configuration.number_of_output_modules, 0),
                        'amount_input_modules': _default_if_255(global_configuration.number_of_input_modules, 0),
                        'amount_sensor_modules': _default_if_255(global_configuration.number_of_sensor_modules, 0),
                        'amount_can_control_modules': _default_if_255(global_configuration.number_of_can_control_modules, 0)}
        if command.instruction == b'CD':
            if command.request_fields[0]._data == bytearray([0]):  # type: ignore  # It's not a `Field` but a `LiteralBytesField`
                return {'amount_of_ucans': 0}
        if command.instruction == b'DL':
            global_configuration = GlobalConfiguration()
            if command.request_fields[0]._data == bytearray([0]):  # type: ignore  # It's not a `Field` but a `LiteralBytesField`
                information = []
                for module_id in range(_default_if_255(global_configuration.number_of_output_modules, 0)):
                    output_byte = 0
                    for entry_id in range(8):
                        output_id = module_id * 8 + entry_id
                        state = self._output_states.get(output_id, {})
                        if state.get('state'):
                            output_byte |= (1 << entry_id)
                    information.append(output_byte)
                return {'type': 0, 'information': information}
            if command.request_fields[0]._data == bytearray([1]):  # type: ignore  # It's not a `Field` but a `LiteralBytesField`
                information = []
                for module_id in range(_default_if_255(global_configuration.number_of_input_modules, 0)):
                    input_byte = 0
                    for entry_id in range(8):
                        input_id = module_id * 8 + entry_id
                        if self._input_states.get(input_id, False):
                            input_byte |= (1 << entry_id)
                    information.append(input_byte)
                return {'type': 1, 'information': information}
        if command.instruction == b'OD':
            output_id = fields['device_nr']
            output_state = self._output_states.get(output_id, {})
            return {'device_nr': output_id,
                    'status': 1 if output_state.get('state') else 0,
                    'dimmer': output_state.get('dimmer', 0),
                    'dimmer_min': 0, 'dimmer_max': 255,
                    'timer_type': output_state.get('timer_type', 0), 'timer_type_standard': 0,
                    'timer': output_state.get('timer', 0), 'timer_standard': 0,
                    'group_action': 255, 'dali_output': 255, 'output_lock': 0}

        logger.info('Got do_command({0}, {1}, {2}, {3})'.format(command, fields, timeout, bypass_blockers))
        return {}

    def _process_basic_action(self, basic_action):  # type: (BasicAction) -> None
        """
        Executes a basic action. It will update the correct internal states and send events where needed.
        """
        if basic_action.action_type == 0:
            send_event = False
            if basic_action.action in [1, 0]:
                # Turn on/off
                output_state = self._output_states.setdefault(basic_action.device_nr, {})
                output_state.update({'state': basic_action.action == 1})
                send_event = True
            if basic_action.action == 2:
                # Turn on with dimmer
                output_state = self._output_states.setdefault(basic_action.device_nr, {})
                output_state.update({'state': 1,
                                     'dimmer': basic_action.extra_parameter})
                send_event = True
            if basic_action.action == 11:
                # Set timer
                output_state = self._output_states.setdefault(basic_action.device_nr, {})
                output_state.update({'timer': basic_action.extra_parameter,
                                     'timer_type': 2})
                send_event = True
            if basic_action.action == 16:
                # Toggle
                output_state = self._output_states.setdefault(basic_action.device_nr, {})
                output_state.update({'state': 0 if output_state.get('state') else 1})
                send_event = True
            if send_event:
                new_state = self._output_states.get(basic_action.device_nr, {})
                # Send event
                self._send_event(bytearray([0, 1 if new_state.get('state') else 0]) +  # action and type
                                 self._word_helper.encode(basic_action.device_nr) +  # device_nr
                                 bytearray([new_state.get('dimmer', 100),
                                            new_state.get('timer_type', 0)]) +  # data 0 + 1
                                 self._word_helper.encode(new_state.get('timer', 0)))  # data 2 + 3
                return
        if basic_action.action_type == 1:
            process_input = False
            if basic_action.action == 0:
                # Input pressed
                self._input_states[basic_action.device_nr] = True
                process_input = True
            if basic_action.action == 1:
                # Input released
                self._input_states[basic_action.device_nr] = False
                process_input = True
            if process_input:
                pressed = self._input_states.get(basic_action.device_nr, False)
                # Send event
                self._send_event(bytearray([1, 1 if pressed else 0]) +  # action and type
                                 self._word_helper.encode(basic_action.device_nr) +  # device_nr
                                 bytearray([0, 0, 0, 0]))  # data
                # Process press
                self._process_input_press(basic_action.device_nr, pressed)
                return
        if basic_action.action_type == 19 and basic_action.action == 0:
            # Execute the group action's individual actions
            group_action = GroupActionController.load_group_action(basic_action.device_nr)
            for action in group_action.actions:
                self._process_basic_action(action)
            return
        logger.info('Discard unimplemented {0}'.format(basic_action))

    def _process_input_press(self, input_id, pressed):  # type: (int, bool) -> None
        """
        Processes an input press. Current implementation:
        * Process direct linked output (toggle only)
        * Process "on press" action
        * Process "on release" action
        """
        input_configuration = InputConfiguration(input_id)
        if input_configuration.has_direct_output_link and pressed:
            self._process_basic_action(BasicAction(action_type=0, action=16, device_nr=input_configuration.input_link.output_id))
        elif input_configuration.input_link.enable_press_and_release:
            press_action = input_configuration.basic_action_press
            release_action = input_configuration.basic_action_release
            if pressed and press_action.in_use:
                self._process_basic_action(press_action)
            if not pressed and release_action.in_use:
                self._process_basic_action(release_action)

    def _send_event(self, event_payload):
        """
        Finds the correct consumer(s) and let them consume the event
        """
        for consumer in self._consumers:
            if consumer.command == self._event_command_spec and consumer.cid == 0:
                consumer.consume(event_payload)


class MasterCoreDummyController(MasterCoreController):
    @Inject
    def __init__(self):  # type: () -> None
        super(MasterCoreDummyController, self).__init__()

    @staticmethod
    def _import_class(name):
        components = name.split('.')
        mod = __import__(components[0])
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return mod

    def start(self):
        """
        Loads fixtures and applies them to the EEPROM.
        Note: The current implementation loads the fixtures _after_ the eeprom is loaded from
              the persistent buffer.
        """

        fixtures_path = '{0}/etc/master_fixture.json'.format(OPENMOTICS_PREFIX)
        if os.path.exists(fixtures_path):
            logger.info('Loading fixtures {0}'.format(fixtures_path))
            with open(fixtures_path, 'r') as fp:
                fixture = json.load(fp)
            for priority in [0, 1, 2]:
                # The fixtures are a dictionary. However, the order of import is important:
                # 0: GlobalConfiguration (sets for example the amount of modules)
                # 1: The module configurations (defines the module metadata)
                # 2: The rest of the configurations
                for model_name, entries in fixture.items():
                    if model_name == 'GlobalConfiguration':
                        if priority != 0:
                            continue
                    elif 'ModuleConfiguration' in model_name:
                        if priority != 1:
                            continue
                    elif priority != 2:
                        continue
                    klass = MasterCoreDummyController._import_class('master.core.memory_models.{0}'.format(model_name))
                    for field_type in klass._get_field_dict().values():
                        field_type._read_only = False
                    for entry in entries:
                        logger.info('* Creating {0}.deserialize(**{1})'.format(klass.__name__, entry))
                        instance = klass.deserialize(entry)
                        instance.save()
        super(MasterCoreDummyController, self).start()
