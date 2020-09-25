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
from master.core.memory_file import MemoryTypes


class OutputMapperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        SetUpTestInjections(memory_files={MemoryTypes.EEPROM: Mock()})

        # Remove read-only flags from device_type for testing purposes below
        if hasattr(OutputModuleConfiguration, '_device_type'):
            OutputModuleConfiguration._device_type._read_only = False
        else:
            OutputModuleConfiguration.device_type._read_only = False

    def test_output_mapper_timer(self):
        # Inactive
        orm = OutputMapper.dto_to_orm(OutputDTO(id=0,
                                                timer=0),
                                      fields=['timer'])
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
                                                timer=123),
                                      fields=['timer'])
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
        # In milliseconds
        dto = OutputMapper.orm_to_dto(OutputConfiguration.deserialize({'id': 0,
                                                                       'timer_type': OutputConfiguration.TimerType.PER_100_MS,
                                                                       'timer_value': 123,
                                                                       'name': 'test',
                                                                       'output_type': 0,
                                                                       'module': {'id': 0,
                                                                                  'device_type': 'O'}}))
        self.assertEqual(OutputDTO(id=0,
                                   timer=12,
                                   name='test',
                                   output_type=0,
                                   module_type='O'), dto)
