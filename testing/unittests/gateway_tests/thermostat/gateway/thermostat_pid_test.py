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
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool
from gateway.models import Base, Database, DaySchedule, Output, Preset, Sensor, Thermostat, \
    ThermostatGroup, Valve, ValveToThermostatAssociation
from gateway.sensor_controller import SensorController
from gateway.thermostat.gateway.pump_valve_controller import \
    PumpValveController
from gateway.thermostat.gateway.thermostat_pid import PID, ThermostatPid
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs


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
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        self.session = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()
        self.addCleanup(session_mock.stop)

        sensor_controller = mock.Mock(SensorController)
        sensor_controller.get_sensor_status.side_effect = lambda x: SensorStatusDTO(id=x, value=10.0)
        self._pump_valve_controller = mock.Mock(PumpValveController)
        SetUpTestInjections(sensor_controller=sensor_controller)

    def _get_thermostat_pid(self):
        with self.session as db:
            db.add_all([
                Thermostat(
                    number=0,
                    name='thermostat 0',
                    pid_heating_p=200,
                    pid_heating_i=100,
                    pid_heating_d=50,
                    pid_cooling_p=200,
                    pid_cooling_i=100,
                    pid_cooling_d=50,
                    automatic=True,
                    start=0,
                    valve_config='equal',
                    sensor=Sensor(source='master', external_id='10', physical_quantity='temperature', name=''),
                    group=ThermostatGroup(number=0, name='thermostat group', mode='heating'),
                    presets=[
                        Preset(type=Preset.Types.AUTO,
                               active=True,
                               heating_setpoint=20.0,
                               cooling_setpoint=25.0)
                    ]
                ),
                ValveToThermostatAssociation(thermostat_id=1,
                                             priority=0,
                                             mode=ThermostatGroup.Modes.HEATING,
                                             valve=Valve(name='valve 1',
                                                         output=Output(number=1))),
                ValveToThermostatAssociation(thermostat_id=1,
                                             priority=0,
                                             mode=ThermostatGroup.Modes.COOLING,
                                             valve=Valve(name='valve 2',
                                                         output=Output(number=2)))
            ])
            db.commit()
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            pid = ThermostatPid(thermostat, pump_valve_controller=self._pump_valve_controller)
            pid.update_thermostat()
            return pid

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
        self.assertTrue(thermostat_pid.enabled)

        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            thermostat.sensor = None
            db.commit()
        thermostat_pid.update_thermostat()
        self.assertFalse(thermostat_pid.enabled)

        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            thermostat.sensor = db.query(Sensor).filter_by(external_id='10').one()
            db.commit()
        thermostat_pid.update_thermostat()
        self.assertTrue(thermostat_pid.enabled)

        # No valves
        heating_valve_ids = thermostat_pid._heating_valve_ids
        thermostat_pid._heating_valve_ids = []
        thermostat_pid._cooling_valve_ids = []
        self.assertFalse(thermostat_pid.enabled)
        thermostat_pid._heating_valve_ids = heating_valve_ids
        self.assertTrue(thermostat_pid.enabled)

        # The unit is turned off
        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            thermostat.state = ThermostatState.OFF
            db.commit()
        thermostat_pid.update_thermostat()
        self.assertFalse(thermostat_pid.enabled)

        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            thermostat.state = ThermostatState.ON
            db.commit()
        thermostat_pid.update_thermostat()
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
        self.assertTrue(thermostat_pid.enabled)

        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            thermostat.state = ThermostatState.OFF
            db.commit()
        thermostat_pid.update_thermostat()
        self._pump_valve_controller.set_valves.call_count = 0
        self._pump_valve_controller.set_valves.mock_calls = []
        self.assertFalse(thermostat_pid.tick())
        self._pump_valve_controller.steer.assert_called_once()
        self.assertEqual(sorted([mock.call(0, [1], mode='equal'),
                                 mock.call(0, [2], mode='equal')]),
                         sorted(self._pump_valve_controller.set_valves.mock_calls))
        self.assertEqual(2, self._pump_valve_controller.set_valves.call_count)

        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            thermostat.state = ThermostatState.ON
            db.commit()
        thermostat_pid.update_thermostat()
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
