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

import logging
import unittest

import mock
from peewee import SqliteDatabase

import fakesleep
from gateway.dto import SensorStatusDTO
from gateway.enums import ThermostatState
from gateway.models import DaySchedule, Output, Preset, Sensor, Thermostat, \
    ThermostatGroup, Valve, ValveToThermostat
from gateway.sensor_controller import SensorController
from gateway.thermostat.gateway.pump_valve_controller import \
    PumpValveController
from gateway.thermostat.gateway.thermostat_pid import PID, ThermostatPid
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs

MODELS = [Thermostat, ThermostatGroup, Sensor, Preset, ValveToThermostat, Valve, Output, DaySchedule]


class PumpValveControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fakesleep.monkey_patch()
        SetTestMode()
        Logs.setup_logger(log_level_override=logging.DEBUG)

    @classmethod
    def tearDownClass(cls):
        fakesleep.monkey_restore()

    def setUp(self):
        self.test_db = SqliteDatabase(':memory:')
        self.test_db.bind(MODELS)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        sensor_controller = mock.Mock(SensorController)
        sensor_controller.get_sensor_status.side_effect = lambda x: SensorStatusDTO(id=x, value=10.0)
        self._pump_valve_controller = mock.Mock(PumpValveController)
        SetUpTestInjections(sensor_controller=sensor_controller)
        sensor = Sensor.create(source='master', external_id='1', physical_quantity='temperature', name='')
        self._thermostat_group = ThermostatGroup.create(number=0,
                                                        name='thermostat group',
                                                        on=True,
                                                        threshold_temperature=10.0,
                                                        sensor=sensor,
                                                        mode='heating')

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def _get_thermostat_pid(self):
        sensor = Sensor.create(source='master', external_id='10', physical_quantity='temperature', name='')
        thermostat = Thermostat.create(number=1,
                                       name='thermostat 1',
                                       sensor=sensor,
                                       pid_heating_p=200,
                                       pid_heating_i=100,
                                       pid_heating_d=50,
                                       pid_cooling_p=200,
                                       pid_cooling_i=100,
                                       pid_cooling_d=50,
                                       automatic=True,
                                       room=None,
                                       start=0,
                                       valve_config='equal',
                                       thermostat_group=self._thermostat_group)
        ValveToThermostat.create(thermostat=thermostat,
                                 valve=Valve.create(number=1,
                                                    name='valve 1',
                                                    output=Output.create(number=1)),
                                 mode=ThermostatGroup.Modes.HEATING,
                                 priority=0)
        ValveToThermostat.create(thermostat=thermostat,
                                 valve=Valve.create(number=2,
                                                    name='valve 2',
                                                    output=Output.create(number=2)),
                                 mode=ThermostatGroup.Modes.COOLING,
                                 priority=0)
        Preset.create(type=Preset.Types.AUTO,
                      heating_setpoint=20.0,
                      cooling_setpoint=25.0,
                      active=True,
                      thermostat=thermostat)
        return ThermostatPid(thermostat=thermostat,
                             pump_valve_controller=self._pump_valve_controller)

    def test_basic(self):
        thermostat_pid = self._get_thermostat_pid()
        self.assertEqual([1, 2], thermostat_pid.valve_ids)
        self.assertEqual([1], thermostat_pid._heating_valve_ids)
        self.assertEqual([2], thermostat_pid._cooling_valve_ids)
        self.assertEqual(200, thermostat_pid.kp)
        self.assertEqual(100, thermostat_pid.ki)
        self.assertEqual(50, thermostat_pid.kd)

    def test_enabled(self):
        thermostat_pid = self._get_thermostat_pid()
        thermostat = thermostat_pid._thermostat
        self.assertTrue(thermostat_pid.enabled)
        # No sensor configured
        sensor = thermostat.sensor
        thermostat.sensor = None
        self.assertFalse(thermostat_pid.enabled)
        thermostat.sensor = sensor
        self.assertTrue(thermostat_pid.enabled)
        # No valves
        heating_valve_ids = thermostat_pid._heating_valve_ids
        thermostat_pid._heating_valve_ids = []
        thermostat_pid._cooling_valve_ids = []
        self.assertFalse(thermostat_pid.enabled)
        thermostat_pid._heating_valve_ids = heating_valve_ids
        self.assertTrue(thermostat_pid.enabled)
        # The group is turned off
        thermostat.state = ThermostatState.OFF
        thermostat_pid.update_thermostat(thermostat)
        self.assertFalse(thermostat_pid.enabled)
        thermostat.state = ThermostatState.ON
        thermostat_pid.update_thermostat(thermostat)
        self.assertTrue(thermostat_pid.enabled)
        # A high amount of errors
        thermostat_pid._errors = 10
        self.assertFalse(thermostat_pid.enabled)
        thermostat_pid._errors = 0
        self.assertTrue(thermostat_pid.enabled)

    def test_tick(self):
        thermostat_pid = self._get_thermostat_pid()
        thermostat_pid._pid = mock.Mock(PID)
        thermostat_pid._pid.setpoint = 0.0
        thermostat = thermostat_pid._thermostat
        self.assertTrue(thermostat_pid.enabled)

        thermostat.state = ThermostatState.OFF
        thermostat_pid.update_thermostat(thermostat)
        self._pump_valve_controller.set_valves.call_count = 0
        self._pump_valve_controller.set_valves.mock_calls = []
        self.assertFalse(thermostat_pid.tick())
        self._pump_valve_controller.steer.assert_called_once()
        self.assertEqual(sorted([mock.call(0, [1], mode='equal'),
                                 mock.call(0, [2], mode='equal')]),
                         sorted(self._pump_valve_controller.set_valves.mock_calls))
        self.assertEqual(2, self._pump_valve_controller.set_valves.call_count)
        thermostat.state = ThermostatState.ON
        thermostat_pid.update_thermostat(thermostat)

        for mode, output_power, heating_power, cooling_power in [(ThermostatGroup.Modes.HEATING, 100, 100, 0),
                                                                 (ThermostatGroup.Modes.HEATING, 50, 50, 0),
                                                                 (ThermostatGroup.Modes.HEATING, 0, 0, 0),
                                                                 (ThermostatGroup.Modes.HEATING, -50, 0, 0),
                                                                 (ThermostatGroup.Modes.COOLING, -100, 0, 100),
                                                                 (ThermostatGroup.Modes.COOLING, -50, 0, 50),
                                                                 (ThermostatGroup.Modes.COOLING, 0, 0, 0),
                                                                 (ThermostatGroup.Modes.COOLING, 50, 0, 0)]:
            thermostat_pid._mode = mode
            thermostat_pid._pid.return_value = output_power
            self._pump_valve_controller.steer.call_count = 0
            self._pump_valve_controller.set_valves.call_count = 0
            self._pump_valve_controller.set_valves.mock_calls = []
            self.assertTrue(thermostat_pid.tick())
            self._pump_valve_controller.steer.assert_called_once()
            self.assertEqual(sorted([mock.call(heating_power, [1], mode='equal'),
                                     mock.call(cooling_power, [2], mode='equal')]),
                             sorted(self._pump_valve_controller.set_valves.mock_calls))
            self.assertEqual(2, self._pump_valve_controller.set_valves.call_count)
