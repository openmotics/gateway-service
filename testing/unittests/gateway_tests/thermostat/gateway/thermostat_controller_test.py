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

import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from gateway.dto import OutputStatusDTO, PumpGroupDTO, ScheduleDTO, \
    SensorStatusDTO, ThermostatDTO, ThermostatGroupDTO, \
    ThermostatGroupStatusDTO, ThermostatScheduleDTO, ThermostatStatusDTO
from gateway.events import GatewayEvent
from gateway.hal.master_event import MasterEvent
from gateway.models import Base, Database, DaySchedule, Output, \
    HvacOutputLink, Preset, Pump, PumpToValveAssociation, \
    Room, Sensor, Thermostat, ThermostatGroup, Valve, \
    IndoorLinkValves
from gateway.output_controller import OutputController
from gateway.pubsub import PubSub
from gateway.scheduling_controller import SchedulingController
from gateway.valve_pump.valve_pump_controller import ValvePumpController
from gateway.sensor_controller import SensorController
from gateway.thermostat.gateway.thermostat_controller_gateway import \
    ThermostatControllerGateway
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs

MODELS = [Pump, Output, Valve, PumpToValveAssociation, Thermostat,
          ThermostatGroup, IndoorLinkValves, Room, Sensor, Preset,
          HvacOutputLink, DaySchedule]



class ThermostatControllerTest(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        # Logs.set_loglevel(logging.DEBUG, namespace='sqlalchemy.engine')
        SetTestMode()

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

        self.pubsub = PubSub()
        self.output_controller = mock.Mock(OutputController)
        self.output_controller.get_output_status.return_value = OutputStatusDTO(id=0, status=False)
        sensor_controller = mock.Mock(SensorController)
        sensor_controller.get_sensor_status.side_effect = lambda x: SensorStatusDTO(id=x, value=10.0)
        self.scheduling_controller = mock.Mock(SchedulingController)
        valve_pump_controller = ValvePumpController()
        SetUpTestInjections(pubsub=self.pubsub,
                            scheduling_controller=self.scheduling_controller,
                            output_controller=self.output_controller,
                            sensor_controller=sensor_controller,
                            valve_pump_controller=valve_pump_controller)
        self.controller = ThermostatControllerGateway()
        self.controller._sync_auto_setpoints = False
        SetUpTestInjections(thermostat_controller=self.controller)

        # sensor = Sensor.create(source='master', external_id='1', physical_quantity='temperature', name='')
        # self._thermostat_group = ThermostatGroup.create(number=0,
        #                                                 name='thermostat group',
        #                                                 on=True,
        #                                                 threshold_temperature=10.0,
        #                                                 sensor=sensor,
        #                                                 mode='heating')

    def test_unconfigure(self):
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
                    room=None,
                    start=0,
                    valve_config='equal',
                    sensor=Sensor(source='master', external_id='10', physical_quantity='temperature', name=''),
                    group=ThermostatGroup(number=0, name='thermostat group', threshold_temperature=10.0, mode='heating'),
                    presets=[
                        Preset(type='auto',
                               active=True,
                               heating_setpoint=20.0,
                               cooling_setpoint=25.0)
                    ]
                ),
                IndoorLinkValves(mode='heating',
                                thermostat_link_id=1,
                                valve=Valve(name='Valve (output 8)',
                                            output=Output(number=8))),
            ])
            db.commit()

        self.controller.save_heating_thermostats([
            ThermostatDTO(id=0, sensor=None, output0=None)
        ])
        thermostats = self.controller.load_heating_thermostats()
        self.assertEqual(len(thermostats), 0)

    def test_update_schedules(self):
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
                    room=None,
                    start=0,
                    valve_config='equal',
                    sensor=Sensor(source='master', external_id='10', physical_quantity='temperature', name=''),
                    group=ThermostatGroup(number=0, name='thermostat group', threshold_temperature=10.0, mode='heating'),
                    presets=[
                        Preset(type='auto',
                               active=True,
                               heating_setpoint=20.0,
                               cooling_setpoint=25.0)
                    ]
                ),
                IndoorLinkValves(mode='heating',
                                thermostat_link_id=1,
                                valve=Valve(name='Valve (output 8)',
                                            output=Output(number=8))),
            ])
            db.commit()

        self.controller._sync_thread = mock.Mock()
        schedule_dto = ThermostatScheduleDTO(temp_day_1=22.0,
                                             start_day_1='06:30',
                                             end_day_1='10:00',
                                             temp_day_2=21.0,
                                             start_day_2='16:00',
                                             end_day_2='23:00',
                                             temp_night=16.5)
        self.controller.save_heating_thermostats([
            ThermostatDTO(id=0,
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

        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            assert len(thermostat.heating_schedules) == 7
            # FIXME
            # assert mock.call(0, 'heating', thermostat.heating_schedules) in self.scheduling_controller.update_thermostat_setpoints.call_args_list
            # assert mock.call(0, 'cooling', []) in self.scheduling_controller.update_thermostat_setpoints.call_args_list

    def test_save_pumpgroups(self):
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
                    room=None,
                    start=0,
                    valve_config='equal',
                    sensor=Sensor(source='master', external_id='10', physical_quantity='temperature', name=''),
                    group=ThermostatGroup(number=0, name='thermostat group', threshold_temperature=10.0, mode='heating'),
                    presets=[
                        Preset(type='auto',
                               active=True,
                               heating_setpoint=20.0,
                               cooling_setpoint=25.0)
                    ]
                ),
                IndoorLinkValves(mode='heating',
                                thermostat_link_id=1,
                                valve=Valve(name='Valve (output 8)',
                                            output=Output(number=8))),
                IndoorLinkValves(mode='cooling',
                                 thermostat_link_id=1,
                                 valve=Valve(name='Valve (output 9)',
                                             output=Output(number=9))),
                IndoorLinkValves(mode='heating',
                                 thermostat_link_id=1,
                                 valve=Valve(name='Valve (output 10)',
                                             output=Output(number=10))),
            ])
            db.commit()

        heating_pump_groups = self.controller.load_heating_pump_groups()
        self.assertEqual([], heating_pump_groups)

        with self.session as db:
            db.add(Output(number=1))
            db.commit()
        self.controller.save_heating_pump_groups([PumpGroupDTO(id=0,
                                                               pump_output_id=1,
                                                               valve_output_ids=[8])])
        self.controller.save_cooling_pump_groups([PumpGroupDTO(id=0,
                                                               pump_output_id=1,
                                                               valve_output_ids=[9])])

        pump_groups = self.controller.load_heating_pump_groups()
        self.assertEqual([PumpGroupDTO(id=0,
                                       pump_output_id=1,
                                       valve_output_ids=[8])], pump_groups)
        pump_groups = self.controller.load_cooling_pump_groups()
        self.assertEqual([PumpGroupDTO(id=0,
                                       pump_output_id=1,
                                       valve_output_ids=[9])], pump_groups)

        with self.session as db:
            db.add(Output(number=2))
            db.commit()
        self.controller.save_heating_pump_groups([
            PumpGroupDTO(id=0,
                         pump_output_id=2,
                         valve_output_ids=[8, 10])
        ])
        pump_groups = self.controller.load_heating_pump_groups()
        self.assertEqual([PumpGroupDTO(id=0,
                                       pump_output_id=2,
                                       valve_output_ids=[8, 10])], pump_groups)
        pump_groups = self.controller.load_cooling_pump_groups()
        self.assertEqual([PumpGroupDTO(id=0,
                                       pump_output_id=2,
                                       valve_output_ids=[9])], pump_groups)

        self.controller.save_heating_pump_groups([
            PumpGroupDTO(id=0,
                         pump_output_id=None,
                         valve_output_ids=[])
        ])
        pump_groups = self.controller.load_heating_pump_groups()
        self.assertEqual([], pump_groups)

    def test_save_thermostat_groups(self):
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
                    room=None,
                    start=0,
                    valve_config='equal',
                    sensor=Sensor(source='master', external_id='10', physical_quantity='temperature', name=''),
                    group=ThermostatGroup(number=0, name='thermostat group', threshold_temperature=10.0, mode='heating'),
                    presets=[
                        Preset(type='auto',
                               active=True,
                               heating_setpoint=20.0,
                               cooling_setpoint=25.0)
                    ]
                ),
                IndoorLinkValves(mode='heating',
                                thermostat_link_id=1,
                                valve=Valve(name='Valve (output 8)',
                                            output=Output(number=8))),
                Sensor(source='master', external_id='11', physical_quantity='temperature', name=''),
                Output(number=0),
                Output(number=1),
                Output(number=2),
            ])
            db.commit()

        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, handle_event)

        with self.session as db:
            group = db.query(ThermostatGroup).filter_by(number=0).one()
            self.assertEqual(10.0, group.threshold_temperature)
            self.assertEqual(0, len(group.outputs))

        self.controller.save_thermostat_groups([
            ThermostatGroupDTO(id=0,
                               outside_sensor_id=1,
                               pump_delay=30,
                               threshold_temperature=15,
                               switch_to_heating_0=(0, 0),
                               switch_to_heating_1=(1, 100),
                               switch_to_cooling_0=(2, 100))
        ])
        self.pubsub._publish_all_events(blocking=False)
        self.assertIn(GatewayEvent('THERMOSTAT_GROUP_CHANGE', {'id': 0, 'status': {'mode': 'HEATING'}}), events)
        with self.session as db:
            group = db.query(ThermostatGroup).filter_by(number=0).one()
            self.assertEqual(15.0, group.threshold_temperature)
            associations = [{'value': x.value, 'mode': x.mode, 'output': x.output.number}
                            for x in group.heating_output_associations]
            self.assertEqual(2, len(associations), associations)
            self.assertIn({'value': 0, 'mode': 'heating', 'output': 0}, associations)
            self.assertIn({'value': 100, 'mode': 'heating', 'output': 1}, associations)
            associations = [{'value': x.value, 'mode': x.mode, 'output': x.output.number}
                            for x in group.cooling_output_associations]
            self.assertEqual(1, len(associations), associations)
            self.assertIn({'value': 100, 'mode': 'cooling', 'output': 2}, associations)

        new_thermostat_group_dto = ThermostatGroupDTO(id=0,
                                                      name='Default',
                                                      pump_delay=60,
                                                      outside_sensor_id=None,
                                                      threshold_temperature=None,
                                                      switch_to_heating_0=(0, 50),
                                                      switch_to_heating_1=None,
                                                      switch_to_cooling_0=(2, 0),
                                                      switch_to_cooling_1=None)
        self.controller.save_thermostat_groups([new_thermostat_group_dto])

        self.pubsub._publish_all_events(blocking=False)
        self.assertIn(GatewayEvent('THERMOSTAT_GROUP_CHANGE', {'id': 0, 'status': {'mode': 'HEATING'}}), events)
        with self.session as db:
            group = db.query(ThermostatGroup).filter_by(number=0).one()
            self.assertIsNone(group.sensor)
            self.assertIsNone(group.threshold_temperature)
            associations = [{'value': x.value, 'mode': x.mode, 'output': x.output.number}
                            for x in group.heating_output_associations]
            self.assertEqual(1, len(associations), associations)
            self.assertIn({'value': 50, 'mode': 'heating', 'output': 0}, associations)
            associations = [{'value': x.value, 'mode': x.mode, 'output': x.output.number}
                            for x in group.cooling_output_associations]
            self.assertEqual(1, len(associations), associations)
            self.assertIn({'value': 0, 'mode': 'cooling', 'output': 2}, associations)

        self.assertEqual(new_thermostat_group_dto, self.controller.load_thermostat_group(0))

    def test_thermostat_control(self):
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
                    room=None,
                    start=0,
                    valve_config='equal',
                    sensor=Sensor(source='master', external_id='10', physical_quantity='temperature', name=''),
                    group=ThermostatGroup(number=0, name='thermostat group', threshold_temperature=10.0, mode='heating',
                                          sensor=Sensor(source='master', external_id='11', physical_quantity='temperature', name='')),
                    presets=[
                        Preset(type='auto',
                               active=True,
                               heating_setpoint=20.0,
                               cooling_setpoint=25.0)
                    ]
                ),
                IndoorLinkValves(mode='heating',
                                thermostat_link_id=1,
                                valve=Valve(name='Valve (output 8)',
                                            output=Output(number=8))),
                HvacOutputLink(hvac_id=1,
                               mode='heating',
                               value=100,
                               output=Output(number=0)),
                HvacOutputLink(hvac_id=1,
                               mode='cooling',
                               value=0,
                               output=Output(number=1)),
            ])
            db.commit()

        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, handle_event)

        now = datetime.now()
        self.scheduling_controller.last_thermostat_setpoint.return_value = (datetime(now.year, now.month, now.day, 0), 21.5)
        self.controller.refresh_config_from_db()

        # Apply last auto scheduled setpoints
        self.controller._sync_auto_setpoints = True
        self.controller.refresh_config_from_db()
        expected = ThermostatGroupStatusDTO(id=0,
                                            setpoint=0,
                                            cooling=False,
                                            automatic=True,
                                            mode='heating',
                                            statusses=[ThermostatStatusDTO(id=0,
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
        assert expected.statusses[0] == self.controller.get_thermostat_group_status()[0].statusses[0]
        assert expected == self.controller.get_thermostat_group_status()[0]

        self.controller.set_current_setpoint(0, heating_temperature=15.0)
        expected.statusses[0].setpoint_temperature = 15.0
        assert expected == self.controller.get_thermostat_group_status()[0]

        self.scheduling_controller.last_thermostat_setpoint.return_value = (datetime(now.year, now.month, now.day, 0), 19.0)
        # Restore auto scheduled setpoints
        self.controller.set_thermostat(0, preset='auto')
        expected.statusses[0].setpoint_temperature = 19.0
        assert expected == self.controller.get_thermostat_group_status()[0]

        self.controller.set_per_thermostat_mode(0,
                                                automatic=False,
                                                setpoint=3)
        self.pubsub._publish_all_events(blocking=False)
        event_data = {'id': 0,
                      'status': {'state': 'ON',
                                 'preset': 'AWAY',
                                 'mode': 'HEATING',
                                 'current_setpoint': 16.0,
                                 'actual_temperature': 10.0,
                                 'output_0': 100,
                                 'output_1': None,
                                 'steering_power': 100}}
        self.assertIn(GatewayEvent('THERMOSTAT_CHANGE', event_data), events)
        expected.statusses[0].setpoint_temperature = 16.0
        expected.statusses[0].setpoint = 3
        expected.statusses[0].automatic = False
        expected.statusses[0].preset = 'away'
        expected.automatic = False
        expected.setpoint = 3
        self.assertEqual([expected], self.controller.get_thermostat_group_status())

        self.controller.set_per_thermostat_mode(0,
                                                automatic=True,
                                                setpoint=3)  # This is conflicting with automatic = True above
        self.pubsub._publish_all_events(blocking=False)
        event_data = {'id': 0,
                      'status': {'state': 'ON',
                                 'preset': 'AUTO',
                                 'mode': 'HEATING',
                                 'current_setpoint': 15.0,
                                 'actual_temperature': 10.0,
                                 'output_0': 100,
                                 'output_1': None,
                                 'steering_power': 100}}
        self.assertIn(GatewayEvent('THERMOSTAT_CHANGE', event_data), events)
        expected.statusses[0].setpoint_temperature = 19.0
        expected.statusses[0].setpoint = 0
        expected.statusses[0].automatic = True
        expected.statusses[0].preset = 'auto'
        expected.automatic = True
        expected.setpoint = 0
        self.assertEqual([expected], self.controller.get_thermostat_group_status())

    def test_copy_schedule(self):
        with self.session as db:
            db.add_all([
                Thermostat(number=0,
                           name='thermostat 0',
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
                           sensor=Sensor(source='master', external_id='10', physical_quantity='temperature', name=''),
                           group=ThermostatGroup(number=0, name='thermostat group', threshold_temperature=10.0, mode='heating')),
                IndoorLinkValves(mode='heating',
                                thermostat_link_id=1,
                                valve=Valve(name='Valve (output 8)',
                                            output=Output(number=8))),
            ])
            db.commit()

        thermostat_dto = self.controller.load_heating_thermostat(thermostat_id=0)
        self.controller.save_heating_thermostats([thermostat_dto])  # Make sure all defaults are populated

        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            default_schedule = DaySchedule.DEFAULT_SCHEDULE['heating']
            self.assertEqual(default_schedule, thermostat.heating_schedules[0].schedule_data)
            expected = {Preset.Types.AUTO: 14.0,
                        Preset.Types.AWAY: 16.0,
                        Preset.Types.VACATION: 15.0,
                        Preset.Types.PARTY: 22.0}
            self.assertEqual(expected, {x.type: x.heating_setpoint for x in thermostat.presets})

        source_dto = ThermostatDTO(id=8)
        source_dto.auto_mon = ThermostatScheduleDTO(temp_night=1.0, temp_day_1=2.0, temp_day_2=3.0,
                                                    start_day_1='04:00', end_day_1='05:00',
                                                    start_day_2='06:00', end_day_2='07:00')
        source_dto.setp3 = 8.0
        source_dto.setp4 = 9.0
        source_dto.setp5 = 10.0
        self.controller.copy_heating_schedule(source_dto, thermostat_dto)

        with self.session as db:
            thermostat = db.get(Thermostat, 1)
            self.assertEqual({0: 1.0, 4*60*60: 2.0, 5*60*60: 1.0, 6*60*60: 3.0, 7*60*60: 1.0},
                             thermostat.heating_schedules[0].schedule_data)
            expected = {Preset.Types.AUTO: 14.0,
                        Preset.Types.AWAY: 8.0,
                        Preset.Types.VACATION: 9.0,
                        Preset.Types.PARTY: 10.0}
            self.assertEqual(expected, {x.type: x.heating_setpoint for x in thermostat.presets})

    def test_processing_master_event(self):
        with self.session as db:
            db.add_all([
                Thermostat(number=0,
                           name='thermostat 0',
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
                           sensor=Sensor(source='master', external_id='10', physical_quantity='temperature', name=''),
                           group=ThermostatGroup(number=0, name='thermostat group', threshold_temperature=10.0, mode='heating')),
                IndoorLinkValves(mode='heating',
                                thermostat_link_id=1,
                                valve=Valve(name='Valve (output 8)',
                                            output=Output(number=8))),
            ])
            db.commit()

        thermostat_dto = self.controller.load_heating_thermostat(thermostat_id=0)
        self.controller.save_heating_thermostats([thermostat_dto])  # Make sure all defaults are populated

        now = datetime.now()
        self.scheduling_controller.last_thermostat_setpoint.return_value = (datetime(now.year, now.month, now.day, 0), 21.5)

        self.controller._handle_master_event(MasterEvent(event_type=MasterEvent.Types.EXECUTE_GATEWAY_API,
                                                         data={'type': MasterEvent.APITypes.SET_THERMOSTAT_MODE,
                                                               'data': {'state': 'on',
                                                                        'mode': 'cooling'}}))
        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            self.assertEqual('on', thermostat.state)
            self.assertEqual('cooling', thermostat.group.mode)

        self.controller._handle_master_event(MasterEvent(event_type=MasterEvent.Types.EXECUTE_GATEWAY_API,
                                                         data={'type': MasterEvent.APITypes.SET_THERMOSTAT_MODE,
                                                               'data': {'state': 'off',
                                                                        'mode': 'heating'}}))
        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            self.assertEqual('off', thermostat.state)
            self.assertEqual('heating', thermostat.group.mode)

            self.controller._handle_master_event(MasterEvent(event_type=MasterEvent.Types.EXECUTE_GATEWAY_API,
                                                             data={'type': MasterEvent.APITypes.SET_THERMOSTAT_PRESET,
                                                                   'data': {'preset': 'away'}}))

        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            self.assertEqual('away', thermostat.active_preset.type)

            self.controller._handle_master_event(MasterEvent(event_type=MasterEvent.Types.EXECUTE_GATEWAY_API,
                                                             data={'type': MasterEvent.APITypes.SET_THERMOSTAT_PRESET,
                                                                   'data': {'preset': 'party'}}))

        with self.session as db:
            thermostat = db.query(Thermostat).filter_by(number=0).one()
            self.assertEqual('party', thermostat.active_preset.type)
