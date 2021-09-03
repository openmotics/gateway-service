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

from mock import Mock
from peewee import SqliteDatabase

import fakesleep
from gateway.dto import OutputStatusDTO, PumpGroupDTO, ScheduleDTO, \
    SensorStatusDTO, ThermostatDTO, ThermostatGroupDTO, \
    ThermostatGroupStatusDTO, ThermostatScheduleDTO, ThermostatStatusDTO
from gateway.models import DaySchedule, Output, OutputToThermostatGroup, \
    Preset, Pump, PumpToValve, Room, Sensor, Thermostat, ThermostatGroup, \
    Valve, ValveToThermostat
from gateway.output_controller import OutputController
from gateway.pubsub import PubSub
from gateway.scheduling_controller import SchedulingController
from gateway.sensor_controller import SensorController
from gateway.thermostat.gateway.thermostat_controller_gateway import \
    ThermostatControllerGateway
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs

MODELS = [Pump, Output, Valve, PumpToValve, Thermostat,
          ThermostatGroup, ValveToThermostat, Room, Sensor, Preset,
          OutputToThermostatGroup, DaySchedule]


class ThermostatControllerTest(unittest.TestCase):
    maxDiff = None

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
        output_controller = Mock(OutputController)
        output_controller.get_output_status.return_value = OutputStatusDTO(id=0, status=False)
        sensor_controller = Mock(SensorController)
        sensor_controller.get_sensor_status.side_effect = lambda x: SensorStatusDTO(id=x, value=10.0)
        self.scheduling_controller = Mock(SchedulingController)
        self.scheduling_controller.load_schedules.return_value = []
        SetUpTestInjections(pubsub=Mock(PubSub),
                            scheduling_controller=self.scheduling_controller,
                            output_controller=output_controller,
                            sensor_controller=sensor_controller)
        self._thermostat_controller = ThermostatControllerGateway()
        SetUpTestInjections(thermostat_controller=self._thermostat_controller)
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

    def test_update_thermostat(self):
        Room.create(number=2, name='Room 2')
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
        self._thermostat_controller.save_heating_thermostats([
            ThermostatDTO(id=thermostat.id, sensor=None, room=2)
        ])
        thermostats = self._thermostat_controller.load_heating_thermostats()
        self.assertEqual(len(thermostats), 1)
        self.assertEqual(thermostats[0].name, 'thermostat 1')
        self.assertEqual(thermostats[0].sensor, None)
        self.assertEqual(thermostats[0].room, 2)

    def test_update_schedules(self):
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
                                       auto_mon=None,
                                       automatic=True,
                                       start=0,
                                       valve_config='equal',
                                       thermostat_group=self._thermostat_group)
        self.scheduling_controller.load_schedules.return_value = [
            ScheduleDTO(id=10, external_id='1.0', start=0, action='LOCAL_API', name='T1 day 0 00:00'),
            ScheduleDTO(id=11, external_id='X.X', start=0, action='LOCAL_API', name='')
        ]
        self._thermostat_controller._sync_thread = Mock()
        self._thermostat_controller.save_heating_thermostats([
            ThermostatDTO(id=thermostat.id,
                          auto_mon=ThermostatScheduleDTO(temp_day_1=22.0,
                                                         start_day_1='06:30',
                                                         end_day_1='10:00',
                                                         temp_day_2=21.0,
                                                         start_day_2='16:00',
                                                         end_day_2='23:00',
                                                         temp_night=16.5))
        ])
        self._thermostat_controller._sync_thread.request_single_run.assert_called_with()
        self._thermostat_controller.refresh_thermostats_from_db()

        schedules = self.scheduling_controller.save_schedules.call_args_list[0][0][0]
        self.assertEqual(len(schedules), 2 * 5 * 7)
        self.assertIn('1.0', [x.external_id for x in schedules])   # 1..7  heating
        self.assertIn('14.4', [x.external_id for x in schedules])  # 8..14 cooling
        schedule = next(x for x in schedules if x.name == 'H1 day 0 00:00')
        self.assertEqual(schedule.arguments, {'name': 'set_setpoint_from_scheduler',
                                              'parameters': {'thermostat': 1,
                                                             'heating_temperature': 16.5}})
        self.assertEqual(schedule.repeat, '00 00 * * 0')
        schedule = next(x for x in schedules if x.name == 'H1 day 0 06:30')
        self.assertEqual(schedule.arguments, {'name': 'set_setpoint_from_scheduler',
                                              'parameters': {'thermostat': 1,
                                                             'heating_temperature': 22.0}})
        self.assertEqual(schedule.repeat, '30 06 * * 0')
        self.scheduling_controller.remove_schedules.assert_called_with([
            ScheduleDTO(id=11, external_id='X.X', start=0, action='LOCAL_API', name='')
        ])

    def test_save_pumpgroups(self):
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
        Preset.create(type=Preset.Types.AUTO,
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
                                                      [PumpGroupDTO(id=pump.id,
                                                                    pump_output_id=pump_output.id,
                                                                    valve_output_ids=[valve_1_output.id, valve_3_output.id])])
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

    def test_thermostat_group_crud(self):
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
        Output.create(number=1)
        Output.create(number=2)
        Output.create(number=3)
        valve_output = Output.create(number=4)
        valve = Valve.create(number=1,
                             name='valve 1',
                             output=valve_output)
        ValveToThermostat.create(thermostat=thermostat,
                                 valve=valve,
                                 mode=ThermostatGroup.Modes.HEATING,
                                 priority=0)
        thermostat_group = ThermostatGroup.get(number=0)  # type: ThermostatGroup
        self.assertEqual(10.0, thermostat_group.threshold_temperature)
        self.assertEqual(0, OutputToThermostatGroup.select()
                                                   .where(OutputToThermostatGroup.thermostat_group == thermostat_group)
                                                   .count())
        self._thermostat_controller.save_thermostat_group(ThermostatGroupDTO(id=0,
                                                                             outside_sensor_id=1,
                                                                             pump_delay=30,
                                                                             threshold_temperature=15,
                                                                             switch_to_heating_0=(1, 0),
                                                                             switch_to_heating_1=(2, 100),
                                                                             switch_to_cooling_0=(1, 100)))
        thermostat_group = ThermostatGroup.get(number=0)
        self.assertEqual(15.0, thermostat_group.threshold_temperature)
        links = [{'index': link.index, 'value': link.value, 'mode': link.mode, 'output': link.output_id}
                 for link in (OutputToThermostatGroup.select()
                                                     .where(OutputToThermostatGroup.thermostat_group == thermostat_group))]
        self.assertEqual(3, len(links))
        self.assertIn({'index': 0, 'value': 0, 'mode': 'heating', 'output': 1}, links)
        self.assertIn({'index': 1, 'value': 100, 'mode': 'heating', 'output': 2}, links)
        self.assertIn({'index': 0, 'value': 100, 'mode': 'cooling', 'output': 1}, links)

        new_thermostat_group_dto = ThermostatGroupDTO(id=0,
                                                      outside_sensor_id=1,
                                                      pump_delay=60,
                                                      threshold_temperature=10,
                                                      switch_to_heating_0=(1, 50),
                                                      switch_to_heating_1=None,
                                                      switch_to_cooling_0=(2, 0),
                                                      switch_to_cooling_1=None)
        self._thermostat_controller.save_thermostat_group(new_thermostat_group_dto)
        thermostat_group = ThermostatGroup.get(number=0)
        self.assertEqual(10.0, thermostat_group.threshold_temperature)
        links = [{'index': link.index, 'value': link.value, 'mode': link.mode, 'output': link.output_id}
                 for link in (OutputToThermostatGroup.select()
                                                     .where(OutputToThermostatGroup.thermostat_group == thermostat_group))]
        self.assertEqual(2, len(links))
        self.assertIn({'index': 0, 'value': 50, 'mode': 'heating', 'output': 1}, links)
        self.assertIn({'index': 0, 'value': 0, 'mode': 'cooling', 'output': 2}, links)

        self.assertEqual(new_thermostat_group_dto, self._thermostat_controller.load_thermostat_group())

    def test_thermostat_control(self):
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
        Output.create(number=1)
        Output.create(number=2)
        Output.create(number=3)
        valve_output = Output.create(number=4)
        valve = Valve.create(number=1,
                             name='valve 1',
                             output=valve_output)
        ValveToThermostat.create(thermostat=thermostat,
                                 valve=valve,
                                 mode=ThermostatGroup.Modes.HEATING,
                                 priority=0)
        self._thermostat_controller.refresh_config_from_db()

        expected = ThermostatGroupStatusDTO(id=0,
                                            on=True,
                                            setpoint=0,
                                            cooling=False,
                                            automatic=True,
                                            statusses=[ThermostatStatusDTO(id=1,
                                                                           name='thermostat 1',
                                                                           automatic=True,
                                                                           setpoint=0,
                                                                           sensor_id=sensor.id,
                                                                           actual_temperature=10.0,
                                                                           setpoint_temperature=14.0,
                                                                           outside_temperature=10.0,
                                                                           output_0_level=0,
                                                                           output_1_level=0,
                                                                           mode=0,
                                                                           airco=0)])
        self.assertEqual(expected, self._thermostat_controller.get_thermostat_status())

        self._thermostat_controller.set_current_setpoint(thermostat_number=1, heating_temperature=15.0)
        expected.statusses[0].setpoint_temperature = 15.0
        self.assertEqual(expected, self._thermostat_controller.get_thermostat_status())

        self._thermostat_controller.set_per_thermostat_mode(thermostat_number=1,
                                                            automatic=False,
                                                            setpoint=3)
        expected.statusses[0].setpoint_temperature = 16.0
        expected.statusses[0].setpoint = 3
        expected.statusses[0].automatic = False
        expected.automatic = False
        expected.setpoint = 3
        self.assertEqual(expected, self._thermostat_controller.get_thermostat_status())

        self._thermostat_controller.set_per_thermostat_mode(thermostat_number=1,
                                                            automatic=True,
                                                            setpoint=3)
        expected.statusses[0].setpoint_temperature = 15.0
        expected.statusses[0].setpoint = 0
        expected.statusses[0].automatic = True
        expected.automatic = True
        expected.setpoint = 0
        self.assertEqual(expected, self._thermostat_controller.get_thermostat_status())

        self._thermostat_controller.set_current_setpoint(thermostat_number=1,
                                                         heating_temperature=16.0)

        preset = self._thermostat_controller.get_current_preset(thermostat_number=1)
        self.assertTrue(preset.active)
        self.assertEqual(30.0, preset.cooling_setpoint)
        self.assertEqual(16.0, preset.heating_setpoint)
        self.assertEqual(Preset.Types.AUTO, preset.type)

        self._thermostat_controller.set_current_preset(thermostat_number=1, preset_type=Preset.Types.PARTY)
        expected.statusses[0].setpoint_temperature = 22.0
        expected.statusses[0].setpoint = expected.setpoint = 5  # PARTY = legacy `5` setpoint
        expected.statusses[0].automatic = expected.automatic = False
        self.assertEqual(expected, self._thermostat_controller.get_thermostat_status())

        self._thermostat_controller.set_thermostat_mode(thermostat_on=True, cooling_mode=True, cooling_on=True, automatic=False, setpoint=4)
        expected.statusses[0].setpoint_temperature = 38.0
        expected.statusses[0].setpoint = expected.setpoint = 4  # VACATION = legacy `4` setpoint
        expected.cooling = True
        self.assertEqual(expected, self._thermostat_controller.get_thermostat_status())

        self._thermostat_controller.set_thermostat_mode(thermostat_on=True, cooling_mode=False, cooling_on=True, automatic=True)
        expected.statusses[0].setpoint_temperature = 16.0
        expected.statusses[0].setpoint = expected.setpoint = 0  # AUTO = legacy `0/1/2` setpoint
        expected.statusses[0].automatic = expected.automatic = True
        expected.cooling = False
        self.assertEqual(expected, self._thermostat_controller.get_thermostat_status())
