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

import copy
import json
import logging
import unittest
from datetime import datetime, timedelta

from mock import Mock, call
from peewee import SqliteDatabase

from gateway.dto import OutputStatusDTO, PumpGroupDTO, ScheduleDTO, \
    SensorStatusDTO, ThermostatDTO, ThermostatGroupDTO, \
    ThermostatGroupStatusDTO, ThermostatScheduleDTO, ThermostatStatusDTO
from gateway.events import GatewayEvent
from gateway.hal.master_event import MasterEvent
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

MODELS = [Pump, Output, Valve, PumpToValveAssociation, Thermostat,
          ThermostatGroup, ValveToThermostatAssociation, Room, Sensor, Preset,
          OutputToThermostatGroupAssociation, DaySchedule]


class ThermostatControllerTest(unittest.TestCase):
    maxDiff = None
    test_db = None

    @classmethod
    def setUpClass(cls):
        cls.test_db = SqliteDatabase(':memory:')
        SetTestMode()
        Logs.setup_logger(log_level_override=logging.DEBUG)

    def setUp(self):
        self.test_db.bind(MODELS)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.pubsub = PubSub()
        self.output_controller = Mock(OutputController)
        self.output_controller.get_output_status.return_value = OutputStatusDTO(id=0, status=False)
        sensor_controller = Mock(SensorController)
        sensor_controller.get_sensor_status.side_effect = lambda x: SensorStatusDTO(id=x, value=10.0)
        self.scheduling_controller = Mock(SchedulingController)
        SetUpTestInjections(pubsub=self.pubsub,
                            scheduling_controller=self.scheduling_controller,
                            output_controller=self.output_controller,
                            sensor_controller=sensor_controller)
        self.controller = ThermostatControllerGateway()
        self.controller._sync_auto_setpoints = False
        SetUpTestInjections(thermostat_controller=self.controller)
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

    def test_unconfigure(self):
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
                                       start=0,
                                       valve_config='equal',
                                       thermostat_group=self._thermostat_group)
        self.controller.save_heating_thermostats([
            ThermostatDTO(id=thermostat.id, sensor=None)
        ])
        thermostats = self.controller.load_heating_thermostats()
        self.assertEqual(len(thermostats), 0)

    def test_update_schedules(self):
        sensor = Sensor.create(source='master', external_id='10', physical_quantity='temperature', name='')
        thermostat = Thermostat.create(number=0,
                                       name='thermostat 0',
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
        self.controller._sync_thread = Mock()
        schedule_dto = ThermostatScheduleDTO(temp_day_1=22.0,
                                             start_day_1='06:30',
                                             end_day_1='10:00',
                                             temp_day_2=21.0,
                                             start_day_2='16:00',
                                             end_day_2='23:00',
                                             temp_night=16.5)
        self.controller.save_heating_thermostats([
            ThermostatDTO(id=thermostat.number,
                          auto_mon=schedule_dto,
                          auto_tue=schedule_dto,
                          auto_wed=schedule_dto,
                          auto_thu=schedule_dto,
                          auto_fri=schedule_dto,
                          auto_sat=schedule_dto,
                          auto_sun=schedule_dto)
        ])
        self.controller._sync_thread.request_single_run.assert_called_with()
        self.controller.refresh_thermostats_from_db()

        assert len(thermostat.heating_schedules) == 7
        assert call(0, 'heating', thermostat.heating_schedules) in self.scheduling_controller.update_thermostat_setpoints.call_args_list
        assert call(0, 'cooling', []) in self.scheduling_controller.update_thermostat_setpoints.call_args_list

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

        heating_pump_groups = self.controller.load_heating_pump_groups()
        self.assertEqual([], heating_pump_groups)

        self.controller.save_heating_pump_groups([PumpGroupDTO(id=0,
                                                               pump_output_id=pump_output.id,
                                                               valve_output_ids=[valve_1_output.id])])
        self.controller.save_cooling_pump_groups([PumpGroupDTO(id=0,
                                                               pump_output_id=pump_output.id,
                                                               valve_output_ids=[valve_2_output.id])])

        pump_groups = self.controller.load_heating_pump_groups()
        self.assertEqual([PumpGroupDTO(id=0,
                                       pump_output_id=pump_output.id,
                                       valve_output_ids=[valve_1_output.id])], pump_groups)
        pump_groups = self.controller.load_cooling_pump_groups()
        self.assertEqual([PumpGroupDTO(id=0,
                                       pump_output_id=pump_output.id,
                                       valve_output_ids=[valve_2_output.id])], pump_groups)

        pump_output = Output.create(number=5)
        self.controller.save_heating_pump_groups([
            PumpGroupDTO(id=0,
                         pump_output_id=pump_output.id,
                         valve_output_ids=[valve_1_output.id, valve_3_output.id])
        ])
        pump_groups = self.controller.load_heating_pump_groups()
        self.assertEqual([PumpGroupDTO(id=0,
                                       pump_output_id=pump_output.id,
                                       valve_output_ids=[valve_1_output.id, valve_3_output.id])], pump_groups)
        pump_groups = self.controller.load_cooling_pump_groups()
        self.assertEqual([PumpGroupDTO(id=0,
                                       pump_output_id=pump_output.id,
                                       valve_output_ids=[valve_2_output.id])], pump_groups)

        self.controller.save_heating_pump_groups([
            PumpGroupDTO(id=0,
                         pump_output_id=None,
                         valve_output_ids=[])
        ])
        pump_groups = self.controller.load_heating_pump_groups()
        self.assertEqual([], pump_groups)

    def test_save_thermostat_groups(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, handle_event)

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
        self.controller.save_thermostat_groups([
            ThermostatGroupDTO(id=0,
                               outside_sensor_id=1,
                               pump_delay=30,
                               threshold_temperature=15,
                               switch_to_heating_0=(1, 0),
                               switch_to_heating_1=(2, 100),
                               switch_to_cooling_0=(1, 100))
        ])
        self.pubsub._publish_all_events(blocking=False)
        self.assertIn(GatewayEvent('THERMOSTAT_GROUP_CHANGE', {'id': 0, 'status': {'mode': 'HEATING'}, 'location': {}}), events)
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
                                                      name='Default',
                                                      pump_delay=60,
                                                      outside_sensor_id=None,
                                                      threshold_temperature=None,
                                                      switch_to_heating_0=(1, 50),
                                                      switch_to_heating_1=None,
                                                      switch_to_cooling_0=(2, 0),
                                                      switch_to_cooling_1=None)
        self.controller.save_thermostat_groups([new_thermostat_group_dto])

        self.pubsub._publish_all_events(blocking=False)
        self.assertIn(GatewayEvent('THERMOSTAT_GROUP_CHANGE', {'id': 0, 'status': {'mode': 'HEATING'}, 'location': {}}), events)
        thermostat_group = ThermostatGroup.get(number=0)
        self.assertIsNone(thermostat_group.sensor)
        self.assertIsNone(thermostat_group.threshold_temperature)
        links = [{'index': link.index, 'value': link.value, 'mode': link.mode, 'output': link.output_id}
                 for link in (OutputToThermostatGroup.select()
                                                     .where(OutputToThermostatGroup.thermostat_group == thermostat_group))]
        self.assertEqual(2, len(links))
        self.assertIn({'index': 0, 'value': 50, 'mode': 'heating', 'output': 1}, links)
        self.assertIn({'index': 0, 'value': 0, 'mode': 'cooling', 'output': 2}, links)

        self.assertEqual(new_thermostat_group_dto, self.controller.load_thermostat_group(0))

    def test_thermostat_control(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, handle_event)

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
        now = datetime.now()
        self.scheduling_controller.last_thermostat_setpoint.return_value = (datetime(now.year, now.month, now.day, 0), 21.5)
        self.controller.refresh_config_from_db()

        mode_output = Output.create(number=5)
        OutputToThermostatGroup.create(thermostat_group=self._thermostat_group, output=mode_output, index=0, mode='heating', value=100)
        OutputToThermostatGroup.create(thermostat_group=self._thermostat_group, output=mode_output, index=0, mode='cooling', value=0)
        # Apply last auto scheduled setpoints
        self.controller._sync_auto_setpoints = True
        self.controller.refresh_config_from_db()
        expected = ThermostatGroupStatusDTO(id=0,
                                            setpoint=0,
                                            cooling=False,
                                            automatic=True,
                                            mode='heating',
                                            statusses=[ThermostatStatusDTO(id=1,
                                                                           automatic=True,
                                                                           setpoint=0,
                                                                           state='on',
                                                                           preset='auto',
                                                                           actual_temperature=10.0,
                                                                           setpoint_temperature=21.5,
                                                                           outside_temperature=10.0,
                                                                           output_0_level=0,  # Valve drivers are not active
                                                                           output_1_level=0,
                                                                           steering_power=100,  # PID active
                                                                           mode='heating')])
        assert [expected] == self.controller.get_thermostat_group_status()

        self.controller.set_current_setpoint(thermostat_number=1, heating_temperature=15.0)
        expected.statusses[0].setpoint_temperature = 15.0
        self.assertEqual([expected], self.controller.get_thermostat_group_status())

        self.scheduling_controller.last_thermostat_setpoint.return_value = (datetime(now.year, now.month, now.day, 0), 19.0)
        # Restore auto scheduled setpoints
        self.controller.set_thermostat(1, preset='auto')
        expected.statusses[0].setpoint_temperature = 19.0
        self.assertEqual([expected], self.controller.get_thermostat_group_status())

        self.controller.set_per_thermostat_mode(thermostat_id=1,
                                                automatic=False,
                                                setpoint=3)
        self.pubsub._publish_all_events(blocking=False)
        event_data = {'id': 1,
                      'status': {'state': 'ON',
                                 'preset': 'AWAY',
                                 'mode': 'HEATING',
                                 'current_setpoint': 16.0,
                                 'actual_temperature': 10.0,
                                 'output_0': 100,
                                 'output_1': None,
                                 'steering_power': 100},
                      'location': {}}
        self.assertIn(GatewayEvent('THERMOSTAT_CHANGE', event_data), events)
        expected.statusses[0].setpoint_temperature = 16.0
        expected.statusses[0].setpoint = 3
        expected.statusses[0].automatic = False
        expected.statusses[0].preset = 'away'
        expected.automatic = False
        expected.setpoint = 3
        self.assertEqual([expected], self.controller.get_thermostat_group_status())

        self.controller.set_per_thermostat_mode(thermostat_id=1,
                                                automatic=True,
                                                setpoint=3)  # This is conflicting with automatic = True above
        self.pubsub._publish_all_events(blocking=False)
        event_data = {'id': 1,
                      'status': {'state': 'ON',
                                 'preset': 'AUTO',
                                 'mode': 'HEATING',
                                 'current_setpoint': 15.0,
                                 'actual_temperature': 10.0,
                                 'output_0': 100,
                                 'output_1': None,
                                 'steering_power': 100},
                      'location': {}}
        self.assertIn(GatewayEvent('THERMOSTAT_CHANGE', event_data), events)
        expected.statusses[0].setpoint_temperature = 19.0
        expected.statusses[0].setpoint = 0
        expected.statusses[0].automatic = True
        expected.statusses[0].preset = 'auto'
        expected.automatic = True
        expected.setpoint = 0
        self.assertEqual([expected], self.controller.get_thermostat_group_status())

    def test_copy_schedule(self):
        sensor = Sensor.create(source='master', external_id='10', physical_quantity='temperature', name='')
        Thermostat.create(number=1,
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

        thermostat_dto = self.controller.load_heating_thermostat(thermostat_id=1)
        self.controller.save_heating_thermostats([thermostat_dto])  # Make sure all defaults are populated

        thermostat = Thermostat.get(number=1)
        default_schedule = DaySchedule.DEFAULT_SCHEDULE['heating']
        self.assertEqual(default_schedule, thermostat.heating_schedules[0].schedule_data)
        for preset, expected in {Preset.Types.AWAY: 16.0,
                                 Preset.Types.VACATION: 15.0,
                                 Preset.Types.PARTY: 22.0}.items():
            self.assertEqual(expected, thermostat.get_preset(preset).heating_setpoint)

        source_dto = ThermostatDTO(id=2)
        source_dto.auto_mon = ThermostatScheduleDTO(temp_night=1.0, temp_day_1=2.0, temp_day_2=3.0,
                                                    start_day_1='04:00', end_day_1='05:00',
                                                    start_day_2='06:00', end_day_2='07:00')
        source_dto.setp3 = 8.0
        source_dto.setp4 = 9.0
        source_dto.setp5 = 10.0
        self.controller.copy_heating_schedule(source_dto, thermostat_dto)
        self.assertEqual({0: 1.0, 4*60*60: 2.0, 5*60*60: 1.0, 6*60*60: 3.0, 7*60*60: 1.0},
                         thermostat.heating_schedules[0].schedule_data)
        for preset, expected in {Preset.Types.AWAY: 8.0,
                                 Preset.Types.VACATION: 9.0,
                                 Preset.Types.PARTY: 10.0}.items():
            self.assertEqual(expected, thermostat.get_preset(preset).heating_setpoint)

    def test_processing_master_event(self):
        now = datetime.now()
        sensor = Sensor.create(source='master', external_id='10', physical_quantity='temperature', name='')
        Thermostat.create(number=1,
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
        thermostat_dto = self.controller.load_heating_thermostat(thermostat_id=1)
        self.controller.save_heating_thermostats([thermostat_dto])  # Make sure all defaults are populated
        self.scheduling_controller.last_thermostat_setpoint.return_value = (datetime(now.year, now.month, now.day, 0), 21.5)

        self.controller._handle_master_event(MasterEvent(event_type=MasterEvent.Types.EXECUTE_GATEWAY_API,
                                                         data={'type': MasterEvent.APITypes.SET_THERMOSTAT_MODE,
                                                               'data': {'state': 'on',
                                                                        'mode': 'cooling'}}))
        thermostat = Thermostat.get(number=1)
        self.assertEqual('on', thermostat.state)
        self.assertEqual('cooling', thermostat.thermostat_group.mode)

        self.controller._handle_master_event(MasterEvent(event_type=MasterEvent.Types.EXECUTE_GATEWAY_API,
                                                         data={'type': MasterEvent.APITypes.SET_THERMOSTAT_MODE,
                                                               'data': {'state': 'off',
                                                                        'mode': 'heating'}}))
        thermostat = Thermostat.get(number=1)
        self.assertEqual('off', thermostat.state)
        self.assertEqual('heating', thermostat.thermostat_group.mode)

        self.controller._handle_master_event(MasterEvent(event_type=MasterEvent.Types.EXECUTE_GATEWAY_API,
                                                         data={'type': MasterEvent.APITypes.SET_THERMOSTAT_PRESET,
                                                               'data': {'preset': 'away'}}))
        thermostat = Thermostat.get(number=1)
        self.assertEqual('away', thermostat.active_preset.type)

        self.controller._handle_master_event(MasterEvent(event_type=MasterEvent.Types.EXECUTE_GATEWAY_API,
                                                         data={'type': MasterEvent.APITypes.SET_THERMOSTAT_PRESET,
                                                               'data': {'preset': 'party'}}))
        thermostat = Thermostat.get(number=1)
        self.assertEqual('party', thermostat.active_preset.type)
