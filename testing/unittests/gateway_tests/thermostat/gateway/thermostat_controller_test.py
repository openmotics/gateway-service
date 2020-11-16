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
import fakesleep
import mock
import logging
from peewee import SqliteDatabase

from gateway.models import Pump, Output, Valve, PumpToValve, Thermostat, \
    ThermostatGroup, ValveToThermostat, Sensor, Preset
from gateway.thermostat.gateway.thermostat_controller_gateway import ThermostatControllerGateway
from gateway.dto import PumpGroupDTO
from gateway.output_controller import OutputController
from gateway.gateway_api import GatewayApi
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Pump, Output, Valve, PumpToValve, Thermostat,
          ThermostatGroup, ValveToThermostat, Sensor, Preset]


class ThermostatControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fakesleep.monkey_patch()
        SetTestMode()
        logger = logging.getLogger('openmotics')
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    @classmethod
    def tearDownClass(cls):
        fakesleep.monkey_restore()

    def setUp(self):
        self.test_db = SqliteDatabase(':memory:')
        self.test_db.bind(MODELS)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self._gateway_api = mock.Mock(GatewayApi)
        self._gateway_api.get_timezone.return_value = 'Europe/Brussels'
        SetUpTestInjections(gateway_api=self._gateway_api,
                            output_controller=mock.Mock(OutputController),
                            pubsub=mock.Mock())
        self._thermostat_controller = ThermostatControllerGateway()
        SetUpTestInjections(thermostat_controller=self._thermostat_controller)
        self._thermostat_group = ThermostatGroup.create(number=0,
                                                        name='thermostat group',
                                                        on=True,
                                                        threshold_temperature=10.0,
                                                        sensor=Sensor.create(number=1),
                                                        mode='heating')

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_save_pumpgroups(self):
        thermostat = Thermostat.create(number=1,
                                       name='thermostat 1',
                                       sensor=Sensor.create(number=10),
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
        valve_1_output = Output.create(number=1)
        valve_1 = Valve.create(number=1,
                               name='valve 1',
                               output=valve_1_output)
        valve_2_output = Output.create(number=2)
        valve_2 = Valve.create(number=2,
                               name='valve 2',
                               output=valve_2_output)
        valve_3_output = Output.create(number=3)
        valve_3 = Valve.create(number=3,
                               name='valve 3',
                               output=valve_3_output)
        ValveToThermostat.create(thermostat=thermostat,
                                 valve=valve_1,
                                 mode=ThermostatGroup.Modes.HEATING,
                                 priority=0)
        ValveToThermostat.create(thermostat=thermostat,
                                 valve=valve_2,
                                 mode=ThermostatGroup.Modes.COOLING,
                                 priority=0)
        ValveToThermostat.create(thermostat=thermostat,
                                 valve=valve_3,
                                 mode=ThermostatGroup.Modes.HEATING,
                                 priority=0)
        Preset.create(type=Preset.Types.SCHEDULE,
                      heating_setpoint=20.0,
                      cooling_setpoint=25.0,
                      active=True,
                      thermostat=thermostat)
        pump_output = Output.create(number=4)
        pump = Pump.create(name='pump 1',
                           output=pump_output)

        heating_pump_groups = self._thermostat_controller.load_heating_pump_groups()
        self.assertEqual([PumpGroupDTO(id=pump.id,
                                       pump_output_id=pump_output.id,
                                       valve_output_ids=[],
                                       room_id=None)], heating_pump_groups)

        PumpToValve.create(pump=pump, valve=valve_1)
        PumpToValve.create(pump=pump, valve=valve_2)

        pump_groups = self._thermostat_controller.load_heating_pump_groups()
        self.assertEqual([PumpGroupDTO(id=pump.id,
                                       pump_output_id=pump_output.id,
                                       valve_output_ids=[valve_1_output.id],
                                       room_id=None)], pump_groups)
        pump_groups = self._thermostat_controller.load_cooling_pump_groups()
        self.assertEqual([PumpGroupDTO(id=pump.id,
                                       pump_output_id=pump_output.id,
                                       valve_output_ids=[valve_2_output.id],
                                       room_id=None)], pump_groups)

        self._thermostat_controller._save_pump_groups(ThermostatGroup.Modes.HEATING,
                                                      [(PumpGroupDTO(id=pump.id,
                                                                     pump_output_id=pump_output.id,
                                                                     valve_output_ids=[valve_1_output.id, valve_3_output.id]),
                                                        ['pump_output_id', 'valve_output_ids'])])
        pump_groups = self._thermostat_controller.load_heating_pump_groups()
        self.assertEqual([PumpGroupDTO(id=pump.id,
                                       pump_output_id=pump_output.id,
                                       valve_output_ids=[valve_1_output.id, valve_3_output.id],
                                       room_id=None)], pump_groups)
        pump_groups = self._thermostat_controller.load_cooling_pump_groups()
        self.assertEqual([PumpGroupDTO(id=pump.id,
                                       pump_output_id=pump_output.id,
                                       valve_output_ids=[valve_2_output.id],
                                       room_id=None)], pump_groups)
