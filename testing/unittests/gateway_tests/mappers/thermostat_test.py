# Copyright (C) 2021 OpenMotics BV
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

from gateway.dto.thermostat import PumpGroupDTO
from gateway.dto.thermostat_schedule import ThermostatScheduleDTO
from gateway.hal.mappers_classic import PumpGroupMapper
from gateway.mappers.thermostat import ThermostatMapper
from master.classic.eeprom_models import PumpGroupConfiguration


class ThermostatGatewayMapperTest(unittest.TestCase):
    def test_simple_schedule(self):
        schedule_dto = ThermostatScheduleDTO(temp_night=10.0,
                                             temp_day_1=26.0,
                                             start_day_1='07:00',
                                             end_day_1='09:00',
                                             temp_day_2=25.0,
                                             start_day_2='17:00',
                                             end_day_2='22:00')
        data = ThermostatMapper._schedule_dto_to_orm(schedule_dto, 'heating')
        expected_data = {0: 10.0, 25200: 26.0, 32400: 10.0, 61200: 25.0, 79200: 10.0}
        self.assertEqual(data, expected_data)
        schedule_dto = ThermostatMapper._schedule_to_dto(data, 'heating')
        self.assertEqual(schedule_dto.temp_night, 10.0)
        self.assertEqual(schedule_dto.temp_day_1, 26.0)
        self.assertEqual(schedule_dto.start_day_1, '07:00')
        self.assertEqual(schedule_dto.end_day_1, '09:00')
        self.assertEqual(schedule_dto.temp_day_2, 25.0)
        self.assertEqual(schedule_dto.start_day_2, '17:00')
        self.assertEqual(schedule_dto.end_day_2, '22:00')

    def test_from_overlapping_schedule(self):
        schedule_dto = ThermostatScheduleDTO(temp_night=10.0,
                                             temp_day_1=26.0,
                                             start_day_1='00:00',
                                             end_day_1='12:00',
                                             temp_day_2=25.0,
                                             start_day_2='12:00',
                                             end_day_2='24:00')
        data = ThermostatMapper._schedule_dto_to_orm(schedule_dto, 'heating')
        expected_data = {0: 10.0, 600: 26.0, 43200: 10.0, 43800: 25.0, 85800: 10.0}
        self.assertEqual(len(data), 5)
        self.assertEqual(data, expected_data)
        schedule_dto = ThermostatMapper._schedule_to_dto(data, 'heating')
        self.assertEqual(schedule_dto.temp_night, 10.0)
        self.assertEqual(schedule_dto.temp_day_1, 26.0)
        self.assertEqual(schedule_dto.start_day_1, '00:10')
        self.assertEqual(schedule_dto.end_day_1, '12:00')
        self.assertEqual(schedule_dto.temp_day_2, 25.0)
        self.assertEqual(schedule_dto.start_day_2, '12:10')
        self.assertEqual(schedule_dto.end_day_2, '23:50')

    def test_to_partial_schedule(self):
        data = {'0': 10.0, '21600': 26.0}
        schedule_dto = ThermostatMapper._schedule_to_dto(data, 'heating')
        self.assertEqual(schedule_dto.temp_night, 10.0)
        self.assertEqual(schedule_dto.temp_day_1, 26.0)
        self.assertEqual(schedule_dto.start_day_1, '06:00')
        self.assertEqual(schedule_dto.end_day_1, '08:00')  # from default schedule
        self.assertEqual(schedule_dto.temp_day_2, 21.0)
        self.assertEqual(schedule_dto.start_day_2, '16:00')
        self.assertEqual(schedule_dto.end_day_2, '22:00')

    def test_to_invalid_schedule(self):
        data = {'0': 10.0, '25200': 26.0, '32400': 11.0, '61200': 25.0, '79200': 12.0}
        schedule_dto = ThermostatMapper._schedule_to_dto(data, 'heating')
        self.assertEqual(schedule_dto.temp_day_1, 21.0)  # from default schedule
        self.assertEqual(schedule_dto.temp_day_2, 21.0)



class ThermostatClassicMapperTest(unittest.TestCase):

    def test_pump_group(self):
        raw = {'id': 0, 'outputs': '', 'output': 255, 'room': 255}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[], pump_output_id=None, room_id=None), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto).serialize())

        raw = {'id': 0, 'outputs': '10', 'output': 255, 'room': 255}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[10], pump_output_id=None, room_id=None), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto).serialize())

        raw = {'id': 0, 'outputs': '10,15', 'output': 255, 'room': 255}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[10, 15], pump_output_id=None, room_id=None), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto).serialize())

        raw = {'id': 0, 'outputs': '', 'output': 15, 'room': 10}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[], pump_output_id=15, room_id=10), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto).serialize())
