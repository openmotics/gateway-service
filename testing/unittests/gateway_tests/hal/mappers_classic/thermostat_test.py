"""
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
from __future__ import absolute_import
import unittest
from mock import Mock
from ioc import Scope, SetTestMode, SetUpTestInjections

from gateway.dto import ThermostatGroupDTO
from gateway.hal.mappers_classic.thermostat import ThermostatGroupMapper
from master.classic.eeprom_models import GlobalThermostatConfiguration

class ThermostatGroupMapperTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_mapping_basic(self):
        thermostat_group_mapper = ThermostatGroupMapper()
        thermostat_group_dto = ThermostatGroupDTO(  number=0, 
                                                    name="default", 
                                                    pump_delay=10, 
                                                    threshold_temperature=50,
                                                    switch_to_heating_0=[0, 45], 
                                                    switch_to_heating_1=[9, 255], 
                                                    switch_to_heating_2=None, 
                                                    switch_to_heating_3=None,
                                                    switch_to_cooling_0=[0, 13], 
                                                    switch_to_cooling_1=[9, 0], 
                                                    switch_to_cooling_2=None, 
                                                    switch_to_cooling_3=None,
                                                    outside_sensor_id=None
                                                )
        
        thermostat_group_orm = thermostat_group_mapper.dto_to_orm(thermostat_group_dto)

        self.assertEqual(thermostat_group_orm.switch_to_cooling_value_2, 255)
        self.assertEqual(thermostat_group_orm.switch_to_cooling_value_3, 255)
        self.assertEqual(thermostat_group_orm.switch_to_cooling_value_0, 8)
        self.assertEqual(thermostat_group_orm.switch_to_cooling_value_1, 0)
        self.assertEqual(thermostat_group_orm.pump_delay, 10)
        self.assertEqual(thermostat_group_orm.switch_to_heating_value_0, 28)
        self.assertEqual(thermostat_group_orm.switch_to_heating_value_3, 255)
        self.assertEqual(thermostat_group_orm.switch_to_heating_value_2, 255)
        self.assertEqual(thermostat_group_orm.switch_to_heating_output_2, 255)
        self.assertEqual(thermostat_group_orm.switch_to_heating_output_3, 255)
        self.assertEqual(thermostat_group_orm.switch_to_heating_output_0, 0)
        self.assertEqual(thermostat_group_orm.switch_to_heating_output_1, 9)
        self.assertEqual(thermostat_group_orm.switch_to_cooling_output_3, 255)
        self.assertEqual(thermostat_group_orm.switch_to_cooling_output_2, 255)
        self.assertEqual(thermostat_group_orm.switch_to_cooling_output_1, 9)
        self.assertEqual(thermostat_group_orm.switch_to_heating_value_1, 255)
        self.assertEqual(thermostat_group_orm.switch_to_cooling_output_0, 0)
        self.assertEqual(thermostat_group_orm.threshold_temp, 50.0)

        new_thermostat_group_dto = thermostat_group_mapper.orm_to_dto(thermostat_group_orm)

        self.assertEqual(new_thermostat_group_dto.switch_to_heating_0, [0, 44])
        self.assertEqual(new_thermostat_group_dto.outside_sensor_id, None)
        self.assertEqual(new_thermostat_group_dto.switch_to_cooling_1, [9, 0])
        self.assertEqual(new_thermostat_group_dto.threshold_temperature, 50.0)
        self.assertEqual(new_thermostat_group_dto.switch_to_cooling_0, [0, 13])
        self.assertEqual(new_thermostat_group_dto.number, 0)
        self.assertEqual(new_thermostat_group_dto.switch_to_heating_1, [9, None])
        self.assertEqual(new_thermostat_group_dto.pump_delay, 10)


