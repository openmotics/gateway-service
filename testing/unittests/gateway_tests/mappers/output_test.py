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
from mock import Mock
from ioc import SetTestMode, SetUpTestInjections
from gateway.dto import OutputDTO
from gateway.hal.mappers_core import OutputMapper
from master.core.memory_models import OutputConfiguration, OutputModuleConfiguration
from master.core.memory_file import MemoryTypes, MemoryFile


class OutputMapperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.memory_map = {i: bytearray([255] * 256) for i in range(512)}
        self.memory_map[0][0] = 0
        self.memory_map[0][1] = 1

        def _read(addresses, read_through=False):
            _ = read_through
            data_ = {}
            for address in addresses:
                data_[address] = self.memory_map[address.page][address.offset:address.offset + address.length]
            return data_

        def _write(data_map):
            for address, data_ in data_map.items():
                for index, data_byte in enumerate(data_):
                    self.memory_map[address.page][address.offset + index] = data_byte

        memory_file_mock = Mock(MemoryFile)
        memory_file_mock.read = _read
        memory_file_mock.write = _write

        SetUpTestInjections(memory_file=memory_file_mock)

        # Remove read-only flags from device_type for testing purposes below
        if hasattr(OutputModuleConfiguration, '_device_type'):
            OutputModuleConfiguration._device_type._read_only = False
        else:
            OutputModuleConfiguration.device_type._read_only = False

    def test_output_mapper_timer(self):
        # Inactive
        orm = OutputMapper.dto_to_orm(OutputDTO(id=0,
                                                timer=0))
        self.assertEqual(OutputConfiguration.TimerType.INACTIVE, orm.timer_type)
        self.assertEqual(0, orm.timer_value)
        dto = OutputMapper.orm_to_dto(OutputConfiguration.deserialize({'id': 0,
                                                                       'timer_type': OutputConfiguration.TimerType.INACTIVE,
                                                                       'timer_value': 123,
                                                                       'name': 'test',
                                                                       'output_type': 0,
                                                                       'module': {'id': 0,
                                                                                  'device_type': 'O'}}))
        self.assertEqual(OutputDTO(id=0,
                                   timer=None,
                                   name='test',
                                   output_type=0,
                                   module_type='O'), dto)
        dto = OutputMapper.orm_to_dto(OutputConfiguration.deserialize({'id': 0,
                                                                       'timer_type': OutputConfiguration.TimerType.ABSOLUTE,
                                                                       'timer_value': 123,
                                                                       'name': 'test',
                                                                       'output_type': 0,
                                                                       'module': {'id': 0,
                                                                                  'device_type': 'O'}}))
        self.assertEqual(OutputDTO(id=0,
                                   timer=None,
                                   name='test',
                                   output_type=0,
                                   module_type='O'), dto)
        # In seconds
        orm = OutputMapper.dto_to_orm(OutputDTO(id=0,
                                                timer=123))
        self.assertEqual(OutputConfiguration.TimerType.PER_1_S, orm.timer_type)
        self.assertEqual(123, orm.timer_value)
        dto = OutputMapper.orm_to_dto(OutputConfiguration.deserialize({'id': 0,
                                                                       'timer_type': OutputConfiguration.TimerType.PER_1_S,
                                                                       'timer_value': 123,
                                                                       'name': 'test',
                                                                       'output_type': 0,
                                                                       'module': {'id': 0,
                                                                                  'device_type': 'O'}}))
        self.assertEqual(OutputDTO(id=0,
                                   timer=123,
                                   name='test',
                                   output_type=0,
                                   module_type='O'), dto)
        config = OutputMapper.dto_to_orm(dto)
        self.assertEqual({'id': 0,
                          'locking': {'locked': True},
                          'dali_mapping': {'dali_group_id': None, 'dali_output_id': None},
                          'max_output_level': 255,
                          'min_output_level': 255,
                          'name': 'test',
                          'output_groupaction_follow': 65535,
                          'output_type': 0,
                          'timer_type': OutputConfiguration.TimerType.PER_1_S,
                          'timer_value': 123,
                          'status': {'state': True}}, config.serialize())

        # In milliseconds
        dto = OutputMapper.orm_to_dto(OutputConfiguration.deserialize({'id': 0,
                                                                       'timer_type': OutputConfiguration.TimerType.PER_100_MS,
                                                                       'timer_value': 20,
                                                                       'name': 'test',
                                                                       'output_type': 0,
                                                                       'module': {'id': 0,
                                                                                  'device_type': 'O'}}))
        self.assertEqual(OutputDTO(id=0,
                                   timer=2,
                                   name='test',
                                   output_type=0,
                                   module_type='O'), dto)
        config = OutputMapper.dto_to_orm(dto)
        self.assertEqual({'id': 0,
                          'locking': {'locked': True},
                          'dali_mapping': {'dali_group_id': None, 'dali_output_id': None},
                          'max_output_level': 255,
                          'min_output_level': 255,
                          'name': 'test',
                          'output_groupaction_follow': 65535,
                          'output_type': 0,
                          'timer_type': OutputConfiguration.TimerType.PER_100_MS,
                          'timer_value': 20,
                          'status': {'state': True}}, config.serialize())
