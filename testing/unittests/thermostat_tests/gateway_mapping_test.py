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

import logging
import unittest

from mock import Mock
from peewee import SqliteDatabase

from gateway.dto import SensorStatusDTO, ThermostatDTO, ThermostatScheduleDTO
from gateway.models import DaySchedule, Feature, Output, \
    OutputToThermostatGroup, Preset, Pump, PumpToValve, Room, Sensor, \
    Thermostat, ThermostatGroup, Valve, ValveToThermostat
from gateway.output_controller import OutputController
from gateway.pubsub import PubSub
from gateway.sensor_controller import SensorController
from gateway.scheduling_controller import SchedulingController
from gateway.thermostat.gateway.thermostat_controller_gateway import \
    ThermostatControllerGateway
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs

MODELS = [Feature, Output, ThermostatGroup, OutputToThermostatGroup, Pump, Sensor,
          Valve, PumpToValve, Thermostat, ValveToThermostat, Preset, DaySchedule,
          Room]


class GatewayThermostatMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        Logs.setup_logger(log_level_override=logging.DEBUG)
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    @staticmethod
    def _create_controller(get_sensor_temperature_status=None):
        sensor_controller = Mock(SensorController)
        sensor_controller.get_sensor_status.side_effect = lambda x: SensorStatusDTO(x, value=10.0)

        scheduling_controller = Mock(SchedulingController)
        scheduling_controller.load_schedules.return_value = []

        SetUpTestInjections(message_client=Mock(),
                            output_controller=Mock(OutputController),
                            scheduling_controller=scheduling_controller,
                            sensor_controller=sensor_controller,
                            pubsub=Mock(PubSub))
        thermostat_controller = ThermostatControllerGateway()
        SetUpTestInjections(thermostat_controller=thermostat_controller)
        return thermostat_controller

    def test_load(self):
        controller = GatewayThermostatMappingTests._create_controller()

        group, _ = ThermostatGroup.get_or_create(number=0, name='Default', mode=ThermostatGroup.Modes.HEATING)
        thermostat = Thermostat(number=10,
                                start=0,
                                state='on',
                                name='thermostat',
                                thermostat_group=group)
        thermostat.save()

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
        # Presets & schedules have a different default value for cooling vs heating
        heating_thermostat_dto.setp3 = cooling_thermostat_dto.setp3
        heating_thermostat_dto.setp4 = cooling_thermostat_dto.setp4
        heating_thermostat_dto.setp5 = cooling_thermostat_dto.setp5
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            setattr(heating_thermostat_dto, 'auto_{0}'.format(day), getattr(cooling_thermostat_dto, 'auto_{0}'.format(day)))
        self.assertEqual(heating_thermostat_dto, cooling_thermostat_dto)
        self.assertEqual('thermostat', heating_thermostat_dto.name)
        self.assertEqual(thermostat.number, heating_thermostat_dto.id)

    def test_orm_to_dto_mapping(self):
        controller = GatewayThermostatMappingTests._create_controller()

        group, _ = ThermostatGroup.get_or_create(number=0, name='Default', mode=ThermostatGroup.Modes.HEATING)
        controller.save_heating_thermostats([ThermostatDTO(id=10, name='thermostat')])
        thermostat = Thermostat.get(number=10)

        heating_thermostats = controller.load_heating_thermostats()
        self.assertEqual(1, len(heating_thermostats))
        dto = heating_thermostats[0]  # type: ThermostatDTO

        schedule_dto = ThermostatScheduleDTO(temp_day_1=21.0,
                                             start_day_1='06:00',
                                             end_day_1='08:00',
                                             temp_day_2=21.0,
                                             start_day_2='16:00',
                                             end_day_2='22:00',
                                             temp_night=19.0)

        self.assertEqual(ThermostatDTO(id=10,
                                       name='thermostat',
                                       setp3=16.0,
                                       setp4=15.0,
                                       setp5=22.0,
                                       sensor=None,
                                       pid_p=120.0,
                                       pid_i=0.0,
                                       pid_d=0.0,
                                       room=None,
                                       thermostat_group=0,
                                       permanent_manual=True,
                                       auto_mon=schedule_dto,
                                       auto_tue=schedule_dto,
                                       auto_wed=schedule_dto,
                                       auto_thu=schedule_dto,
                                       auto_fri=schedule_dto,
                                       auto_sat=schedule_dto,
                                       auto_sun=schedule_dto), dto)

        day_schedule = next(x for x in thermostat.heating_schedules if x.index == 3)  # type: DaySchedule
        day_schedule.schedule_data = {0: 5.0,
                                      120: 5.5,   # 120 and 1200 are selected because 120 < 1200,
                                      1200: 5.0,  # but str(120) > str(1200)
                                      3600: 6.5,
                                      7500: 5.0}
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

        room = Room(number=5)
        room.save()

        thermostat_group = ThermostatGroup(number=0,
                                           name='global')
        thermostat_group.save()
        thermostat = Thermostat(number=10,
                                start=0,  # 0 is on a thursday
                                name='thermostat',
                                thermostat_group=thermostat_group)
        thermostat.save()

        heating_thermostats = controller.load_heating_thermostats()
        self.assertEqual(1, len(heating_thermostats))
        dto = heating_thermostats[0]  # type: ThermostatDTO

        default_schedule_dto = ThermostatScheduleDTO(temp_day_1=21.0,
                                                     start_day_1='06:00',
                                                     end_day_1='08:00',
                                                     temp_day_2=21.0,
                                                     start_day_2='16:00',
                                                     end_day_2='22:00',
                                                     temp_night=19.0)

        sensor = Sensor.create(id=15, source='master', external_id='0', physical_quantity='temperature', name='')

        dto.room = 5
        dto.sensor = sensor.id
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
        controller.save_heating_thermostats([dto])

        heating_thermostats = controller.load_heating_thermostats()
        self.assertEqual(1, len(heating_thermostats))
        dto = heating_thermostats[0]  # type: ThermostatDTO

        self.assertEqual(ThermostatDTO(id=10,
                                       name='changed',
                                       setp3=16.0,
                                       setp4=15.0,
                                       setp5=22.0,
                                       sensor=15,
                                       pid_p=120.0,
                                       pid_i=0.0,
                                       pid_d=0.0,
                                       room=5,
                                       thermostat_group=0,
                                       output0=5,
                                       permanent_manual=True,
                                       auto_mon=default_schedule_dto,
                                       auto_tue=default_schedule_dto,
                                       auto_wed=default_schedule_dto,
                                       auto_thu=ThermostatScheduleDTO(temp_night=10.0,
                                                                      temp_day_1=15.0,
                                                                      temp_day_2=30.0,
                                                                      start_day_1='08:00',
                                                                      end_day_1='10:30',
                                                                      start_day_2='16:00',
                                                                      end_day_2='18:45'),
                                       auto_fri=default_schedule_dto,
                                       auto_sat=default_schedule_dto,
                                       auto_sun=default_schedule_dto), dto)
