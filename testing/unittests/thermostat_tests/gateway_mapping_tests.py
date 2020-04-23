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
from gateway.dto import ThermostatDTO, ThermostatScheduleDTO
from gateway.thermostat.gateway.thermostat_controller_gateway import ThermostatControllerGateway

MODELS = [Feature, Output, ThermostatGroup, OutputToThermostatGroup, Pump,
          Valve, PumpToValve, Thermostat, ValveToThermostat, Preset, DaySchedule]


class GatewayThermostatMappingTests(unittest.TestCase):
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

    @staticmethod
    def _create_controller(get_sensor_temperature_status=None):
        gateway_api = Mock()
        gateway_api.get_timezone = lambda: 'Europe/Brussels'
        gateway_api.get_sensor_temperature_status = get_sensor_temperature_status

        SetUpTestInjections(gateway_api=gateway_api,
                            message_client=Mock(),
                            observer=Mock())
        thermostat_controller = ThermostatControllerGateway()
        SetUpTestInjections(thermostat_controller=thermostat_controller)
        return thermostat_controller

    def test_load(self):
        controller = GatewayThermostatMappingTests._create_controller()

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

    def test_orm_to_dto_mapping(self):
        controller = GatewayThermostatMappingTests._create_controller()

        thermostat = Thermostat(number=10,
                                sensor=1,
                                room=2,
                                start=0,  # 0 is on a thursday
                                name='thermostat')
        thermostat.save()

        for i in range(7):
            day_schedule = DaySchedule(index=i,
                                       content='{}',
                                       mode='heating')
            day_schedule.thermostat = thermostat
            day_schedule.save()

        heating_thermostats = controller.load_heating_thermostats()
        self.assertEqual(1, len(heating_thermostats))
        dto = heating_thermostats[0]  # type: ThermostatDTO

        self.assertEqual(ThermostatDTO(id=10,
                                       name='thermostat',
                                       setp3=14.0,
                                       setp4=14.0,
                                       setp5=14.0,
                                       sensor=1,
                                       pid_p=120.0,
                                       pid_i=0.0,
                                       pid_d=0.0,
                                       room=2,
                                       permanent_manual=True), dto)

        day_schedule = thermostat.heating_schedules()[0]  # type: DaySchedule
        day_schedule.schedule_data = {0: 5.0,
                                      120: 5.5,   # 120 and 1200 are selected because 120 < 1200,
                                      1200: 6.0,  # but str(120) > str(1200)
                                      3600: 6.5,
                                      7500: 7.0}
        day_schedule.save()
        heating_thermostats = controller.load_heating_thermostats()
        self.assertEqual(1, len(heating_thermostats))
        dto = heating_thermostats[0]  # type: ThermostatDTO

        self.assertEqual(ThermostatScheduleDTO(temp_night=5.0,
                                               temp_day_1=5.5,
                                               temp_day_2=6.5,
                                               start_day_1='00:02',
                                               end_day_1='00:20',
                                               start_day_2='01:00',
                                               end_day_2='02:05'), dto.auto_thu)

    def test_save(self):
        temperatures = {}

        def _get_temperature(sensor_id):
            return temperatures[sensor_id]

        controller = GatewayThermostatMappingTests._create_controller(get_sensor_temperature_status=_get_temperature)

        thermostat_group = ThermostatGroup(number=0,
                                           name='global')
        thermostat_group.save()
        thermostat = Thermostat(number=10,
                                sensor=1,
                                room=2,
                                start=0,  # 0 is on a thursday
                                name='thermostat',
                                thermostat_group=thermostat_group)
        thermostat.save()

        for i in range(7):
            day_schedule = DaySchedule(index=i,
                                       content='{}',
                                       mode='heating')
            day_schedule.thermostat = thermostat
            day_schedule.save()

        heating_thermostats = controller.load_heating_thermostats()
        self.assertEqual(1, len(heating_thermostats))
        dto = heating_thermostats[0]  # type: ThermostatDTO

        dto.room = 5  # This field won't be saved
        dto.sensor = 15
        dto.output0 = 5
        dto.name = 'changed'
        dto.auto_thu = ThermostatScheduleDTO(temp_night=10,
                                             temp_day_1=15,
                                             temp_day_2=30,
                                             start_day_1='08:00',
                                             end_day_1='10:30',
                                             start_day_2='16:00',
                                             end_day_2='18:45')

        temperatures[15] = 5.0
        controller.save_heating_thermostats([(dto, ['sensor', 'output0', 'name', 'auto_thu'])])

        heating_thermostats = controller.load_heating_thermostats()
        self.assertEqual(1, len(heating_thermostats))
        dto = heating_thermostats[0]  # type: ThermostatDTO

        self.assertEqual(ThermostatDTO(id=10,
                                       name='changed',
                                       setp3=14.0,
                                       setp4=14.0,
                                       setp5=14.0,
                                       sensor=15,
                                       pid_p=120.0,
                                       pid_i=0.0,
                                       pid_d=0.0,
                                       room=2,  # Unchanged
                                       output0=5,
                                       permanent_manual=True,
                                       auto_thu=ThermostatScheduleDTO(temp_night=10.0,
                                                                      temp_day_1=15.0,
                                                                      temp_day_2=30.0,
                                                                      start_day_1='08:00',
                                                                      end_day_1='10:30',
                                                                      start_day_2='16:00',
                                                                      end_day_2='18:45')), dto)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
