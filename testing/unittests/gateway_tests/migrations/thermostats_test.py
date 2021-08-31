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

import mock
from peewee import SqliteDatabase

from gateway.migrations.thermostats import CoolingConfiguration, DaySchedule, \
    GlobalThermostatConfiguration, PumpGroupConfiguration, \
    ThermostatConfiguration, ThermostatsMigrator, OutputToThermostatGroup
from gateway.models import DaySchedule, Output, Preset, Pump, PumpToValve, \
    Room, Sensor, Thermostat, ThermostatGroup, Valve, ValveToThermostat
from gateway.thermostat.thermostat_controller import ThermostatController
from ioc import SetTestMode, SetUpTestInjections
from master.classic.eeprom_controller import EepromController
from master.classic.master_communicator import MasterCommunicator

MODELS = [DaySchedule, Output, OutputToThermostatGroup, Preset, Pump,
          PumpToValve, Room, Sensor, Thermostat, ThermostatGroup,
          Valve, ValveToThermostat]


class ThermostatsMigratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

        self.master_communicator = mock.Mock(MasterCommunicator)
        self.eeprom_controller = mock.Mock(EepromController)
        self.eeprom_controller.read_all.side_effect = ([], [])
        SetUpTestInjections(master_communicator=self.master_communicator,
                            eeprom_controller=self.eeprom_controller,
                            thermostat_controller=mock.Mock(ThermostatController))

    def tearDown(self):
        self.test_db.close()

    def test_migrate(self):
        room, _ = Room.get_or_create(number=0)
        sensor_outside = Sensor.create(source='master', physical_quantity='temperature', unit='celcius', external_id='0', name='sensor_0')
        sensor_thermostat = Sensor.create(source='master', physical_quantity='temperature', unit='celcius', external_id='1', name='sensor_1')
        output_mode1 = Output.create(number=5, name='output_5')
        output_mode2 = Output.create(number=6, name='output_6')
        output_mode3 = Output.create(number=7, name='output_7')
        output_heating0 = Output.create(number=8, name='output_8')
        output_heating_pump = Output.create(number=9, name='pump_9')
        output_cooling0 = Output.create(number=16, name='output_16')
        output_cooling1 = Output.create(number=17, name='output_17')
        output_cooling_pump = Output.create(number=18, name='pump_18')
        thermostat_group = ThermostatGroup.create(number=0, name='Default')

        eeprom_data = {
            GlobalThermostatConfiguration: GlobalThermostatConfiguration.deserialize({
                'outside_sensor': 0,
                'threshold_temp': 20.0,
                'pump_delay': 120,
                'switch_to_heating_output_0': 255,
                'switch_to_heating_value_0': 255,
                'switch_to_heating_output_1': 255,
                'switch_to_heating_value_1': 255,
                'switch_to_heating_output_2': 6,
                'switch_to_heating_value_2': 0,
                'switch_to_heating_output_3': 7,
                'switch_to_heating_value_3': 100,
                'switch_to_cooling_output_0': 255,
                'switch_to_cooling_value_0': 255,
                'switch_to_cooling_output_1': 5,
                'switch_to_cooling_value_1': 100,
                'switch_to_cooling_output_2': 255,
                'switch_to_cooling_value_2': 255,
                'switch_to_cooling_output_3': 255,
                'switch_to_cooling_value_3': 255,
            }),
            ThermostatConfiguration: [ThermostatConfiguration.deserialize({
                'id': 0,
                'name': 'thermostat_0',
                'setp0': None,
                'setp1': None,
                'setp2': None,
                'setp3': 16.0,
                'setp4': 10.0,
                'setp5': 22.5,
                'room': 0,
                'sensor': 1,
                'output0': 8,
                'output1': 255,
                'pid_p': 255,
                'pid_i': 255,
                'pid_d': 255,
                'pid_int': 255,
                'permanent_manual': False,
                'auto_mon': [16.0, '07:00', '09:00', 20.0, '17:00', '22:00', 21.0],
                'auto_tue': [16.0, '07:00', '09:00', 20.0, '17:00', '22:00', 21.0],
                'auto_wed': [16.0, '07:00', '09:00', 20.0, '12:30', '22:00', 21.0],
                'auto_thu': [16.0, '07:00', '09:00', 20.0, '17:00', '22:00', 21.0],
                'auto_fri': [16.0, '07:00', '09:00', 20.0, '17:00', '22:00', 21.0],
                'auto_sat': [16.0, '07:00', '18:00', 20.0, '18:00', '22:00', 21.0],
                'auto_sun': [16.0, '07:00', '18:00', 20.0, '18:00', '22:00', 21.0],
            })],
            CoolingConfiguration: [CoolingConfiguration.deserialize({
                'id': 0,
                'name': 'thermostat_0',
                'setp0': None,
                'setp1': None,
                'setp2': None,
                'setp3': 28.0,
                'setp4': 32.0,
                'setp5': 22.5,
                'room': 0,
                'sensor': 1,
                'output0': 16,
                'output1': 17,
                'pid_p': 200,
                'pid_i': 50,
                'pid_d': 50,
                'pid_int': 255,
                'permanent_manual': False,
                'auto_mon': [16.0, '07:00', '09:00', 26.0, '17:00', '22:00', 25.0],
                'auto_tue': [16.0, '07:00', '09:00', 26.0, '17:00', '22:00', 25.0],
                'auto_wed': [16.0, '07:00', '09:00', 26.0, '12:30', '22:00', 25.0],
                'auto_thu': [16.0, '07:00', '09:00', 26.0, '17:00', '22:00', 25.0],
                'auto_fri': [16.0, '07:00', '09:00', 26.0, '17:00', '22:00', 25.0],
                'auto_sat': [16.0, '07:00', '18:00', 26.0, '18:00', '22:00', 25.0],
                'auto_sun': [16.0, '07:00', '18:00', 26.0, '18:00', '22:00', 25.0],
            })],
            PumpGroupConfiguration: [
                PumpGroupConfiguration.deserialize({
                    'id': 6,
                    'output': 9,
                    'outputs': '8',
                }),
                PumpGroupConfiguration.deserialize({
                    'id': 7,
                    'output': 18,
                    'outputs': '16,17',
                })
            ]
        }

        def _read_eeprom(model):
            return eeprom_data[model]

        self.eeprom_controller.read_all.side_effect = _read_eeprom
        self.eeprom_controller.read.side_effect = _read_eeprom

        ThermostatsMigrator._migrate()

        self.assertEqual(ThermostatGroup.select().count(), 1)
        thermostat_group = ThermostatGroup.get(number=0)
        self.assertEqual(thermostat_group.sensor, sensor_outside)
        self.assertEqual(thermostat_group.threshold_temperature, 20.0)

        self.assertEqual(OutputToThermostatGroup.select().count(), 3)
        group_output = OutputToThermostatGroup.get(mode='heating', index=2)
        self.assertEqual(group_output.output, output_mode2)
        self.assertEqual(group_output.value, 0)
        group_output = OutputToThermostatGroup.get(mode='heating', index=3)
        self.assertEqual(group_output.output, output_mode3)
        self.assertEqual(group_output.value, 100)
        group_output = OutputToThermostatGroup.get(mode='cooling', index=1)
        self.assertEqual(group_output.output, output_mode1)
        self.assertEqual(group_output.value, 100)

        self.assertEqual(Thermostat.select().count(), 1)
        thermostat = Thermostat.get(number=0)
        self.assertEqual(thermostat.name, 'thermostat_0')
        self.assertEqual(thermostat.room, room)
        self.assertEqual(thermostat.sensor, sensor_thermostat)
        self.assertEqual(thermostat.heating_valves, [Valve.get(output=output_heating0)])
        self.assertEqual(thermostat.cooling_valves, [Valve.get(output=output_cooling0),
                                                     Valve.get(output=output_cooling1)])
        valve = Valve.get(output=output_heating0)
        self.assertEqual(valve.delay, 120.0)
        valve = Valve.get(output=output_cooling0)
        self.assertEqual(valve.delay, 120.0)
        valve = Valve.get(output=output_cooling1)
        self.assertEqual(valve.delay, 120.0)

        self.assertEqual(thermostat.pid_heating_p, 120)
        self.assertEqual(thermostat.pid_heating_i, 0)
        self.assertEqual(thermostat.pid_heating_d, 0)
        self.assertEqual(thermostat.pid_cooling_p, 200)
        self.assertEqual(thermostat.pid_cooling_i, 50)
        self.assertEqual(thermostat.pid_cooling_d, 50)

        self.assertEqual(Preset.select().count(), 3)
        preset = Preset.get(type='away')
        self.assertEqual(preset.heating_setpoint, 16.0)
        self.assertEqual(preset.cooling_setpoint, 28.0)
        preset = Preset.get(type='vacation')
        self.assertEqual(preset.heating_setpoint, 10.0)
        self.assertEqual(preset.cooling_setpoint, 32.0)
        preset = Preset.get(type='party')
        self.assertEqual(preset.heating_setpoint, 22.5)
        self.assertEqual(preset.cooling_setpoint, 22.5)

        self.assertEqual(DaySchedule.select().count(), 14)
        schedules = [x.schedule_data for x in thermostat.heating_schedules]
        self.assertEqual(schedules, [
            {'0': 16.0, '25200': 20.0, '32400': 16.0, '61200': 21.0, '79200': 16.0},
            {'0': 16.0, '25200': 20.0, '32400': 16.0, '61200': 21.0, '79200': 16.0},
            {'0': 16.0, '25200': 20.0, '32400': 16.0, '45000': 21.0, '79200': 16.0},
            {'0': 16.0, '25200': 20.0, '32400': 16.0, '61200': 21.0, '79200': 16.0},
            {'0': 16.0, '25200': 20.0, '32400': 16.0, '61200': 21.0, '79200': 16.0},
            {'0': 16.0, '25200': 20.0, '64800': 21.0, '79200': 16.0},
            {'0': 16.0, '25200': 20.0, '64800': 21.0, '79200': 16.0},
        ])

        self.assertEqual(Pump.select().count(), 2)
        pump = Pump.get(output=output_heating_pump)
        self.assertEqual(pump.heating_valves, [Valve.get(output=output_heating0)])
        self.assertEqual(pump.cooling_valves, [])
        pump = Pump.get(output=output_cooling_pump)
        self.assertEqual(pump.cooling_valves, [Valve.get(output=output_cooling0),
                                               Valve.get(output=output_cooling1)])
        self.assertEqual(pump.heating_valves, [])

        self.master_communicator.do_command.assert_called()
        payload = self.master_communicator.do_command.call_args_list[0][0][1]
        self.assertEqual(payload, {'bank': 0, 'address': 40, 'data': bytearray([0x00])})
