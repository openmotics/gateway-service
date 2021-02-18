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
from gateway.hal.mappers_classic import PumpGroupMapper
from master.classic.eeprom_models import PumpGroupConfiguration


class ThermostatClassicMapperTest(unittest.TestCase):

    def test_pump_group(self):
        fields = ['valve_output_ids', 'pump_output_id', 'room_id']

        raw = {'id': 0, 'outputs': '', 'output': 255, 'room': 255}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[], pump_output_id=None, room_id=None), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto, fields).serialize())

        raw = {'id': 0, 'outputs': '10', 'output': 255, 'room': 255}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[10], pump_output_id=None, room_id=None), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto, fields).serialize())

        raw = {'id': 0, 'outputs': '10,15', 'output': 255, 'room': 255}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[10, 15], pump_output_id=None, room_id=None), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto, fields).serialize())

        raw = {'id': 0, 'outputs': '', 'output': 15, 'room': 10}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[], pump_output_id=15, room_id=10), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto, fields).serialize())
