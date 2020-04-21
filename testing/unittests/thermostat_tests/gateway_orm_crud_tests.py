# Copyright (C) 2020 OpenMotics BV
#
# This program is free software, you can redistribute it and/or modify
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

import unittest
import xmlrunner
import logging

from peewee import SqliteDatabase
from mock import Mock

from ioc import SetTestMode, SetUpTestInjections
from models import (
    Feature, Output, ThermostatGroup, OutputToThermostatGroup, Pump,
    Valve, PumpToValve, Thermostat, ValveToThermostat, Preset, DaySchedule
)
from gateway.thermostat.gateway.thermostat_controller_gateway import ThermostatControllerGateway

MODELS = [Feature, Output, ThermostatGroup, OutputToThermostatGroup, Pump,
          Valve, PumpToValve, Thermostat, ValveToThermostat, Preset, DaySchedule]


class GatewayThermostatORMCrudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        logger = logging.getLogger('openmotics')
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_load(self):
        gateway_api = Mock()
        gateway_api.get_timezone = lambda: 'Europe/Brussels'

        SetUpTestInjections(gateway_api=gateway_api,
                            message_client=Mock(),
                            observer=Mock())
        controller = ThermostatControllerGateway()

        thermostat = Thermostat(number=10,
                                sensor=0,
                                room=0,
                                start=0,
                                name='thermostat')
        thermostat.save()

        for i in range(7):
            day_schedule = DaySchedule(index=i,
                                       content='{}',
                                       mode='heating')
            day_schedule.thermostat = thermostat
            day_schedule.save()
            day_schedule = DaySchedule(index=i,
                                       content='{}',
                                       mode='cooling')
            day_schedule.thermostat = thermostat
            day_schedule.save()

        # Validate load calls
        heating_thermostats = controller.load_heating_thermostats()
        self.assertEqual(1, len(heating_thermostats))
        cooling_thermostats = controller.load_cooling_thermostats()
        self.assertEqual(1, len(cooling_thermostats))
        heating_thermostat_dto = heating_thermostats[0]
        cooling_thermostat_dto = cooling_thermostats[0]
        self.assertEqual(heating_thermostat_dto, controller.load_heating_thermostat(10))
        self.assertEqual(cooling_thermostat_dto, controller.load_cooling_thermostat(10))

        # Validate contents
        # Presets have a different default value for cooling vs heating
        heating_thermostat_dto.setp3 = cooling_thermostat_dto.setp3
        heating_thermostat_dto.setp4 = cooling_thermostat_dto.setp4
        heating_thermostat_dto.setp5 = cooling_thermostat_dto.setp5
        self.assertEqual(heating_thermostat_dto, cooling_thermostat_dto)
        self.assertEqual('thermostat', heating_thermostat_dto.name)
        self.assertEqual(thermostat.number, heating_thermostat_dto.id)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
