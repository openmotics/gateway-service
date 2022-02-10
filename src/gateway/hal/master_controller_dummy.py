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

from gateway.hal.master_controller_core import MasterCoreController
from master.core.core_communicator import CoreCommunicator
from master.core.memory_models import GlobalConfiguration
from ioc import Inject, INJECTED
from constants import OPENMOTICS_PREFIX

if False:  # MYPY
    from typing import List, Dict, Any, Union, Optional, TypeVar
    from master.core.memory_file import MemoryAddress
    from master.core.core_command import CoreCommandSpec
    T_co = TypeVar('T_co', bound=None, covariant=True)

logger = logging.getLogger(__name__)


class DummyMemoryFile(object):
    def __init__(self):
        self._memory = {}  # type: Dict[int, Dict[int, int]]

    def start(self):
        pass

    def stop(self):
        pass

    def read(self, addresses, read_through=False):  # type: (List[MemoryAddress], bool) -> Dict[MemoryAddress, bytearray]
        response = {}  # type: Dict[MemoryAddress, bytearray]
        for address in addresses:
            data = bytearray()
            page_memory = self._memory.setdefault(address.page, {})
            for position in range(address.offset, address.offset + address.length):
                data.append(page_memory.get(position, 255))
            response[address] = data
        return response

    def write(self, data_map):  # type: (Dict[MemoryAddress, bytearray]) -> None
        for address, data in data_map.items():
            page_memory = self._memory.setdefault(address.page, {})
            for index, position in enumerate(range(address.offset, address.offset + address.length)):
                page_memory[position] = data[index]

    def commit(self):
        pass


class DummyCommunicator(object):
    @Inject
    def __init__(self, memory_file=INJECTED):
        self._memory_file = memory_file

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

    def get_communication_statistics(self):
        return {'calls_succeeded': [], 'calls_timedout': [],
                'bytes_written': 0, 'bytes_read': 0}

    def do_command(self, command, fields, timeout=2, bypass_blockers=None):
        # type: (CoreCommandSpec, Dict[str, Any], Union[T_co, int], Optional[List]) -> Union[T_co, Dict[str, Any]]
        def _default_if_255(value, default):
            return value if value != 255 else default

        if command.instruction == 'GC':
            if command.request_fields[0]._data == bytearray([0]):
                global_configuration = GlobalConfiguration()
                return {'type': 0,
                        'output': _default_if_255(global_configuration.number_of_output_modules, 0),
                        'input': _default_if_255(global_configuration.number_of_input_modules, 0),
                        'sensor': _default_if_255(global_configuration.number_of_sensor_modules, 0),
                        'ucan': _default_if_255(global_configuration.number_of_ucan_modules, 0),
                        'ucan_input': _default_if_255(global_configuration.number_of_can_inputs, 0),
                        'ucan_sensor': _default_if_255(global_configuration.number_of_can_sensors, 0),
                        'power_rs485': 1, 'power_can': 1}
        if command.instruction == 'PC':
            return {'series': fields['series'],
                    'counter_0': 0, 'counter_1': 0, 'counter_2': 0, 'counter_3': 0,
                    'counter_4': 0, 'counter_5': 0, 'counter_6': 0, 'counter_7': 0,
                    'crc126': 0}
        if command.instruction == 'ST':
            if command.request_fields[0]._data == bytearray([2]):
                global_configuration = GlobalConfiguration()
                return {'info_type': 2,
                        'amount_output_modules': _default_if_255(global_configuration.number_of_output_modules, 0),
                        'amount_input_modules': _default_if_255(global_configuration.number_of_input_modules, 0),
                        'amount_sensor_modules': _default_if_255(global_configuration.number_of_sensor_modules, 0),
                        'amount_can_control_modules': _default_if_255(global_configuration.number_of_can_control_modules, 0)}
        if command.instruction == 'CD':
            if command.request_fields[0]._data == bytearray([0]):
                return {'amount_of_ucans': 0}
        if command.instruction == 'DL':
            global_configuration = GlobalConfiguration()
            if command.request_fields[0]._data == bytearray([0]):
                return {'type': 0, 'information': [0 for _ in range(_default_if_255(global_configuration.number_of_output_modules, 0))]}
            if command.request_fields[0]._data == bytearray([1]):
                return {'type': 1, 'information': [0 for _ in range(_default_if_255(global_configuration.number_of_input_modules, 0))]}
        if command.instruction == 'OD':
            return {'device_nr': fields['device_nr'],
                    'status': 0, 'dimmer': 0, 'dimmer_min': 0, 'dimmer_max': 255,
                    'timer_type': 0, 'timer_type_standard': 0, 'timer': 0, 'timer_standard': 0,
                    'group_action': 255, 'dali_output': 255, 'output_lock': 0}

        logger.info('Got do_command({0}, {1}, {2}, {3})'.format(command, fields, timeout, bypass_blockers))
        return {}


class MasterDummyController(MasterCoreController):
    @Inject
    def __init__(self):  # type: () -> None
        super(MasterDummyController, self).__init__()

    @staticmethod
    def _import_class(name):
        components = name.split('.')
        mod = __import__(components[0])
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return mod

    def start(self):
        fixtures_path = '{0}/etc/master_fixture.json'.format(OPENMOTICS_PREFIX)
        logger.info('Loading fixtures {0}'.format(fixtures_path))
        with open(fixtures_path, 'r') as fp:
            fixture = json.load(fp)
        for model_name, entries in fixture.items():
            klass = MasterDummyController._import_class('master.core.memory_models.{0}'.format(model_name))
            for entry in entries:
                logger.info('* Creating {0}.deserialize(**{1})'.format(klass.__name__, entry))
                instance = klass.deserialize(entry)
                instance.save()
        super(MasterDummyController, self).start()
