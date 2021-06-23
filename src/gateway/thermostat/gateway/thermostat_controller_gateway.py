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

import datetime
import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from playhouse.signals import post_save

import constants
from gateway.daemon_thread import DaemonThread
from gateway.dto import RTD10DTO, GlobalRTD10DTO, PumpGroupDTO, \
    ThermostatDTO, ThermostatGroupDTO, ThermostatGroupStatusDTO, \
    ThermostatStatusDTO
from gateway.enums import ThermostatMode
from gateway.events import GatewayEvent
from gateway.exceptions import UnsupportedException
from gateway.mappers import ThermostatMapper
from gateway.models import Output, OutputToThermostatGroup, Preset, Pump, \
    PumpToValve, Sensor, Thermostat, ThermostatGroup, Valve, \
    ValveToThermostat
from gateway.pubsub import PubSub
from gateway.thermostat.gateway.pump_valve_controller import \
    PumpValveController
from gateway.thermostat.gateway.thermostat_pid import ThermostatPid
from gateway.thermostat.thermostat_controller import ThermostatController
from ioc import INJECTED, Inject

if False:  # MYPY
    from typing import Dict, List, Literal, Tuple, Optional
    from gateway.output_controller import OutputController
    from gateway.system_controller import SystemController
    from gateway.sensor_controller import SensorController

logger = logging.getLogger(__name__)


class ThermostatControllerGateway(ThermostatController):

    # TODO: At this moment, a pump group strictly speaking is not related to any thermostat,
    #  nor to cooling/heating. Yet in the `classic` implementation there is. This means that
    #  changing a pump group could influence another pump group, since their `number` is shared.

    THERMOSTAT_PID_UPDATE_INTERVAL = 60
    PUMP_UPDATE_INTERVAL = 30
    SYNC_CONFIG_INTERVAL = 900

    @Inject
    def __init__(self, output_controller=INJECTED, sensor_controller=INJECTED, pubsub=INJECTED, system_controller=INJECTED):
        # type: (OutputController, SensorController, PubSub, SystemController) -> None
        super(ThermostatControllerGateway, self).__init__(output_controller)
        self._sensor_controller = sensor_controller
        self._pubsub = pubsub
        self._running = False
        self._pid_loop_thread = None  # type: Optional[DaemonThread]
        self._update_pumps_thread = None  # type: Optional[DaemonThread]
        self._periodic_sync_thread = None  # type: Optional[DaemonThread]
        self.thermostat_pids = {}  # type: Dict[int, ThermostatPid]
        self._pump_valve_controller = PumpValveController()

        timezone = system_controller.get_timezone()

        # we could also use an in-memory store, but this allows us to detect 'missed' transitions
        # e.g. in case when gateway was rebooting during a scheduled transition
        db_filename = constants.get_thermostats_scheduler_database_file()
        jobstores = {'default': SQLAlchemyJobStore(url='sqlite:///{}'.format(db_filename))}
        self._scheduler = BackgroundScheduler(jobstores=jobstores, timezone=timezone)

    def start(self):  # type: () -> None
        logger.info('Starting gateway thermostatcontroller...')
        if not self._running:
            self._running = True

            self.refresh_config_from_db()
            self._pid_loop_thread = DaemonThread(name='thermostatpid',
                                                 target=self._pid_tick,
                                                 interval=self.THERMOSTAT_PID_UPDATE_INTERVAL)
            self._pid_loop_thread.start()

            self._update_pumps_thread = DaemonThread(name='thermostatpumps',
                                                     target=self._update_pumps,
                                                     interval=self.PUMP_UPDATE_INTERVAL)
            self._update_pumps_thread.start()

            self._periodic_sync_thread = DaemonThread(name='thermostatsync',
                                                      target=self._periodic_sync,
                                                      interval=self.SYNC_CONFIG_INTERVAL)
            self._periodic_sync_thread.start()

            self._scheduler.start()
            logger.info('Starting gateway thermostatcontroller... Done')
        else:
            raise RuntimeError('GatewayThermostatController already running. Please stop it first.')

    def stop(self):  # type: () -> None
        if not self._running:
            logger.warning('Stopping an already stopped GatewayThermostatController.')
        self._running = False
        self._scheduler.shutdown(wait=False)
        if self._pid_loop_thread is not None:
            self._pid_loop_thread.stop()
        if self._update_pumps_thread is not None:
            self._update_pumps_thread.stop()
        if self._periodic_sync_thread is not None:
            self._periodic_sync_thread.stop()

    def _pid_tick(self):  # type: () -> None
        for thermostat_number, thermostat_pid in self.thermostat_pids.items():
            try:
                thermostat_pid.tick()
            except Exception:
                logger.exception('There was a problem with calculating thermostat PID {}'.format(thermostat_pid))

    def refresh_config_from_db(self):  # type: () -> None
        self.refresh_thermostats_from_db()
        self._pump_valve_controller.refresh_from_db()

    def refresh_thermostats_from_db(self):  # type: () -> None
        for thermostat in Thermostat.select():
            thermostat_pid = self.thermostat_pids.get(thermostat.number)
            if thermostat_pid is None:
                thermostat_pid = ThermostatPid(thermostat, self._pump_valve_controller)
                thermostat_pid.subscribe_state_changes(self._thermostat_changed)
                self.thermostat_pids[thermostat.number] = thermostat_pid
            thermostat_pid.update_thermostat(thermostat)
            thermostat_pid.tick()
            # TODO: Delete stale/removed thermostats

    def _update_pumps(self):  # type: () -> None
        try:
            self._pump_valve_controller.steer()
        except Exception:
            logger.exception('Could not update pumps.')

    def _periodic_sync(self):  # type: () -> None
        try:
            self.refresh_config_from_db()
        except Exception:
            logger.exception('Could not get thermostat config.')

    def _sync_scheduler(self):  # type: () -> None
        self._scheduler.remove_all_jobs()  # TODO: This might have to be more efficient, as this generates I/O
        for thermostat_number, thermostat_pid in self.thermostat_pids.items():
            start_date = datetime.datetime.utcfromtimestamp(float(thermostat_pid.thermostat.start))
            day_schedules = thermostat_pid.thermostat.day_schedules
            schedule_length = len(day_schedules)
            for schedule in day_schedules:
                for seconds_of_day, new_setpoint in schedule.schedule_data.items():
                    m, s = divmod(int(seconds_of_day), 60)
                    h, m = divmod(m, 60)
                    if schedule.mode == 'heating':
                        args = [thermostat_number, new_setpoint, None]
                    else:
                        args = [thermostat_number, None, new_setpoint]
                    if schedule_length % 7 == 0:
                        self._scheduler.add_job(ThermostatControllerGateway.set_setpoint_from_scheduler, 'cron',
                                                start_date=start_date,
                                                day_of_week=schedule.index,
                                                hour=h, minute=m, second=s,
                                                args=args,
                                                name='T{}: {} ({}) {}'.format(thermostat_number, new_setpoint, schedule.mode, seconds_of_day))
                    else:
                        # calendarinterval trigger is only supported in a future release of apscheduler
                        # https://apscheduler.readthedocs.io/en/latest/modules/triggers/calendarinterval.html#module-apscheduler.triggers.calendarinterval
                        day_start_date = start_date + datetime.timedelta(days=schedule.index)
                        self._scheduler.add_job(ThermostatControllerGateway.set_setpoint_from_scheduler, 'calendarinterval',
                                                start_date=day_start_date,
                                                days=schedule_length,
                                                hour=h, minute=m, second=s,
                                                args=args,
                                                name='T{}: {} ({}) {}'.format(thermostat_number, new_setpoint, schedule.mode, seconds_of_day))

    def set_current_setpoint(self, thermostat_number, temperature=None, heating_temperature=None, cooling_temperature=None):
        # type: (int, Optional[float], Optional[float], Optional[float]) -> None
        if temperature is None and heating_temperature is None and cooling_temperature is None:
            return

        thermostat = Thermostat.get(number=thermostat_number)
        # When setting a setpoint manually, switch to manual preset except for when we are in scheduled mode
        # scheduled mode will override the setpoint when the next edge in the schedule is triggered
        active_preset = thermostat.active_preset
        if active_preset.type not in [Preset.Types.SCHEDULE, Preset.Types.MANUAL]:
            active_preset = thermostat.get_preset(Preset.Types.MANUAL)
            thermostat.active_preset = active_preset

        if heating_temperature is None:
            heating_temperature = temperature
        if heating_temperature is not None:
            active_preset.heating_setpoint = float(heating_temperature)

        if cooling_temperature is None:
            cooling_temperature = temperature
        if cooling_temperature is not None:
            active_preset.cooling_setpoint = float(cooling_temperature)
        active_preset.save()

        thermostat_pid = self.thermostat_pids[thermostat_number]
        thermostat_pid.update_thermostat(thermostat)
        thermostat_pid.tick()

    def get_current_preset(self, thermostat_number):  # type: (int) -> Preset
        thermostat = Thermostat.get(number=thermostat_number)
        return thermostat.active_preset

    def set_current_preset(self, thermostat_number, preset_type):  # type: (int, str) -> None
        thermostat = Thermostat.get(number=thermostat_number)  # type: Thermostat
        preset = thermostat.get_preset(preset_type)
        thermostat.active_preset = preset
        thermostat.save()

        thermostat_pid = self.thermostat_pids[thermostat_number]
        thermostat_pid.update_thermostat(thermostat)
        thermostat_pid.tick()

    @classmethod
    @Inject
    def set_setpoint_from_scheduler(cls, thermostat_number, heating_temperature=None, cooling_temperature=None, thermostat_controller=INJECTED):
        # type: (int, Optional[float], Optional[float], ThermostatControllerGateway) -> None
        logger.info('Setting setpoint from scheduler for thermostat {}: H{} C{}'.format(thermostat_number, heating_temperature, cooling_temperature))
        thermostat = Thermostat.get(number=thermostat_number)
        active_preset = thermostat.active_preset

        # Only update when not in preset mode like away, party, ...
        if active_preset.type == Preset.Types.SCHEDULE:
            thermostat_controller.set_current_setpoint(thermostat_number=thermostat_number,
                                                       heating_temperature=heating_temperature,
                                                       cooling_temperature=cooling_temperature)
        else:
            logger.info('Thermostat is currently in preset mode, skipping update setpoint from scheduler.')

    def get_thermostat_status(self):  # type: () -> ThermostatGroupStatusDTO
        def get_output_level(output_number):
            if output_number is None:
                return 0  # we are returning 0 if outputs are not configured
            try:
                output = self._output_controller.get_output_status(output_number)
            except ValueError:
                logger.info('Output {0} state not yet available'.format(output_number))
                return 0  # Output state is not yet cached (during startup)
            if output.dimmer is None:
                status_ = output.status
                output_level = 0 if status_ is None else int(status_) * 100
            else:
                output_level = output.dimmer
            return output_level

        def get_temperature_from_sensor(sensor):  # type: (Optional[Sensor]) -> Optional[float]
            if sensor:
                status = self._sensor_controller.get_sensor_status(sensor.id)
                if status:
                    return status.value
            return None

        global_thermostat = ThermostatGroup.get(number=0)
        if global_thermostat is None:
            raise RuntimeError('Global thermostat not found!')
        group_status = ThermostatGroupStatusDTO(id=0,
                                                on=global_thermostat.on,
                                                automatic=True,  # Default, will be updated below
                                                setpoint=0,  # Default, will be updated below
                                                cooling=global_thermostat.mode == ThermostatMode.COOLING)

        for thermostat in global_thermostat.thermostats:
            valves = thermostat.cooling_valves if global_thermostat.mode == 'cooling' else thermostat.heating_valves
            db_outputs = [valve.output.number for valve in valves]

            number_of_outputs = len(db_outputs)
            if number_of_outputs > 2:
                logger.warning('Only 2 outputs are supported in the old format. Total: {0} outputs.'.format(number_of_outputs))

            output0 = db_outputs[0] if number_of_outputs > 0 else None
            output1 = db_outputs[1] if number_of_outputs > 1 else None

            active_preset = thermostat.active_preset
            if global_thermostat.mode == ThermostatMode.COOLING:
                setpoint_temperature = active_preset.cooling_setpoint
            else:
                setpoint_temperature = active_preset.heating_setpoint

            group_status.statusses.append(ThermostatStatusDTO(id=thermostat.number,
                                                              actual_temperature=get_temperature_from_sensor(thermostat.sensor),
                                                              setpoint_temperature=setpoint_temperature,
                                                              outside_temperature=get_temperature_from_sensor(global_thermostat.sensor),
                                                              mode=0,  # TODO: Need to be fixed
                                                              automatic=active_preset.type == Preset.Types.SCHEDULE,
                                                              setpoint=Preset.TYPE_TO_SETPOINT.get(active_preset.type, 0),
                                                              name=thermostat.name,
                                                              sensor_id=255 if thermostat.sensor is None else thermostat.sensor.id,
                                                              airco=0,  # TODO: Check if still used
                                                              output_0_level=get_output_level(output0),
                                                              output_1_level=get_output_level(output1)))

        # Update global references
        group_status.automatic = all(status.automatic for status in group_status.statusses)
        used_setpoints = set(status.setpoint for status in group_status.statusses)
        group_status.setpoint = next(iter(used_setpoints)) if len(used_setpoints) == 1 else 0  # 0 is a fallback

        return group_status

    def set_thermostat_mode(self, thermostat_on, cooling_mode=False, cooling_on=False, automatic=None, setpoint=None):
        # type: (bool, bool, bool, Optional[bool], Optional[int]) -> None
        mode = ThermostatMode.COOLING if cooling_mode else ThermostatMode.HEATING  # type: Literal['cooling', 'heating']
        global_thermosat = ThermostatGroup.get(number=0)
        global_thermosat.on = thermostat_on
        global_thermosat.mode = mode
        global_thermosat.save()

        for thermostat_number, thermostat_pid in self.thermostat_pids.items():
            thermostat = Thermostat.get(number=thermostat_number)
            if thermostat is not None:
                if automatic is False and setpoint is not None and 3 <= setpoint <= 5:
                    preset = thermostat.get_preset(preset_type=Preset.SETPOINT_TO_TYPE.get(setpoint, Preset.Types.SCHEDULE))
                    thermostat.active_preset = preset
                else:
                    thermostat.active_preset = thermostat.get_preset(preset_type=Preset.Types.SCHEDULE)
                thermostat_pid.update_thermostat(thermostat)
                thermostat_pid.tick()

    def load_heating_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        mode = 'heating'  # type: Literal['heating']
        thermostat = Thermostat.get(number=thermostat_id)
        return ThermostatMapper.orm_to_dto(thermostat, mode)

    def load_heating_thermostats(self):  # type: () -> List[ThermostatDTO]
        mode = 'heating'  # type: Literal['heating']
        return [ThermostatMapper.orm_to_dto(thermostat, mode)
                for thermostat in Thermostat.select()]

    def save_heating_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        mode = 'heating'  # type: Literal['heating']
        for thermostat_dto in thermostats:
            thermostat = ThermostatMapper.dto_to_orm(thermostat_dto, mode)
            self.refresh_set_configuration(thermostat)
        self._thermostat_config_changed()

    def load_cooling_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        mode = 'cooling'  # type: Literal['cooling']
        thermostat = Thermostat.get(number=thermostat_id)
        return ThermostatMapper.orm_to_dto(thermostat, mode)

    def load_cooling_thermostats(self):  # type: () -> List[ThermostatDTO]
        mode = 'cooling'  # type: Literal['cooling']
        return [ThermostatMapper.orm_to_dto(thermostat, mode)
                for thermostat in Thermostat.select()]

    def save_cooling_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        mode = 'cooling'  # type: Literal['cooling']
        for thermostat_dto in thermostats:
            thermostat = ThermostatMapper.dto_to_orm(thermostat_dto, mode)
            self.refresh_set_configuration(thermostat)
        self._thermostat_config_changed()

    def set_per_thermostat_mode(self, thermostat_number, automatic, setpoint):
        # type: (int, bool, int) -> None
        thermostat_pid = self.thermostat_pids.get(thermostat_number)
        if thermostat_pid is not None:
            thermostat = thermostat_pid.thermostat
            thermostat.automatic = automatic
            if automatic is False and setpoint is not None and 3 <= setpoint <= 5:
                preset = thermostat.get_preset(preset_type=Preset.SETPOINT_TO_TYPE.get(setpoint, Preset.Types.SCHEDULE))
                thermostat.active_preset = preset
            else:
                thermostat.active_preset = thermostat.get_preset(preset_type=Preset.Types.SCHEDULE)
            thermostat.save()
            thermostat_pid.update_thermostat(thermostat)
            thermostat_pid.tick()

    def load_thermostat_group(self):
        # type: () -> ThermostatGroupDTO
        thermostat_group = ThermostatGroup.get(number=0)
        pump_delay = None
        for thermostat in thermostat_group.thermostats:
            for valve in thermostat.valves:
                pump_delay = valve.delay
                break
        sensor_id = None if thermostat_group.sensor is None else thermostat_group.sensor.id
        thermostat_group_dto = ThermostatGroupDTO(id=0,
                                                  outside_sensor_id=sensor_id,
                                                  threshold_temperature=thermostat_group.threshold_temperature,
                                                  pump_delay=pump_delay)
        for link in OutputToThermostatGroup.select(OutputToThermostatGroup, Output) \
                                           .join_from(OutputToThermostatGroup, Output) \
                                           .where(OutputToThermostatGroup.thermostat_group == thermostat_group):
            if link.index > 3 or link.output is None:
                continue
            field = 'switch_to_{0}_{1}'.format(link.mode, link.index)
            setattr(thermostat_group_dto, field, (link.output.number, link.value))
        return thermostat_group_dto

    def save_thermostat_group(self, thermostat_group):  # type: (ThermostatGroupDTO) -> None
        # Update thermostat group configuration
        orm_object = ThermostatGroup.get(number=0)  # type: ThermostatGroup
        if 'outside_sensor_id' in thermostat_group.loaded_fields:
            orm_object.sensor = Sensor.get(id=thermostat_group.outside_sensor_id)
        if 'threshold_temperature' in thermostat_group.loaded_fields:
            orm_object.threshold_temperature = thermostat_group.threshold_temperature  # type: ignore
        orm_object.save()

        # Link configuration outputs to global thermostat config
        for mode in ['cooling', 'heating']:
            links = {link.index: link
                     for link in OutputToThermostatGroup
                         .select()
                         .where((OutputToThermostatGroup.thermostat_group == orm_object) &
                                (OutputToThermostatGroup.mode == mode))}
            for i in range(4):
                field = 'switch_to_{0}_{1}'.format(mode, i)
                if field not in thermostat_group.loaded_fields:
                    continue

                link = links.get(i)
                data = getattr(thermostat_group, field)
                if data is None:
                    if link is not None:
                        link.delete_instance()
                else:
                    output_number, value = data
                    output = Output.get(number=output_number)
                    if link is None:
                        OutputToThermostatGroup.create(output=output,
                                                       thermostat_group=orm_object,
                                                       mode=mode,
                                                       index=i,
                                                       value=value)
                    else:
                        link.output = output
                        link.value = value
                        link.save()

        if 'pump_delay' in thermostat_group.loaded_fields:
            # Set valve delay for all valves in this group
            for thermostat in orm_object.thermostats:
                for valve in thermostat.valves:
                    valve.delay = thermostat_group.pump_delay  # type: ignore
                    valve.save()

        self._thermostat_config_changed()

    def load_heating_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        pump = Pump.get(number=pump_group_id)
        return PumpGroupDTO(id=pump_group_id,
                            pump_output_id=pump.output.number,
                            valve_output_ids=[valve.output.number for valve in pump.heating_valves],
                            room_id=None)

    def load_heating_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        pump_groups = []
        for pump in Pump.select():
            pump_groups.append(PumpGroupDTO(id=pump.id,
                                            pump_output_id=pump.output.number,
                                            valve_output_ids=[valve.output.number for valve in pump.heating_valves],
                                            room_id=None))
        return pump_groups

    def save_heating_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        return self._save_pump_groups(ThermostatGroup.Modes.HEATING, pump_groups)

    def load_cooling_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        pump = Pump.get(number=pump_group_id)
        return PumpGroupDTO(id=pump_group_id,
                            pump_output_id=pump.output.number,
                            valve_output_ids=[valve.output.number for valve in pump.cooling_valves],
                            room_id=None)

    def load_cooling_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        pump_groups = []
        for pump in Pump.select():
            pump_groups.append(PumpGroupDTO(id=pump.id,
                                            pump_output_id=pump.output.number,
                                            valve_output_ids=[valve.output.number for valve in pump.cooling_valves],
                                            room_id=None))
        return pump_groups

    def save_cooling_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        return self._save_pump_groups(ThermostatGroup.Modes.COOLING, pump_groups)

    def _save_pump_groups(self, mode, pump_groups):  # type: (str, List[PumpGroupDTO]) -> None
        for pump_group_dto in pump_groups:
            if 'pump_output_id' in pump_group_dto.loaded_fields and 'valve_output_ids' in pump_group_dto.loaded_fields:
                valve_output_ids = pump_group_dto.valve_output_ids
                pump = Pump.get(id=pump_group_dto.id)  # type: Pump
                pump.output = Output.get(number=pump_group_dto.pump_output_id)

                links = {pump_to_valve.valve.output.number: pump_to_valve
                         for pump_to_valve
                         in PumpToValve.select(PumpToValve, Pump, Valve, Output)
                                       .join_from(PumpToValve, Valve)
                                       .join_from(PumpToValve, Pump)
                                       .join_from(Valve, Output)
                                       .join_from(Valve, ValveToThermostat)
                                       .where((ValveToThermostat.mode == mode) &
                                              (Pump.id == pump.id))}
                for output_id in list(links.keys()):
                    if output_id not in valve_output_ids:
                        pump_to_valve = links.pop(output_id)  # type: PumpToValve
                        pump_to_valve.delete_instance()
                    else:
                        valve_output_ids.remove(output_id)
                for output_id in valve_output_ids:
                    output = Output.get(number=output_id)
                    valve = Valve.get_or_none(output=output)
                    if valve is None:
                        valve = Valve(name=output.name,
                                      output=output)
                        valve.save()
                    PumpToValve.create(pump=pump,
                                       valve=valve)
        self._thermostat_config_changed()

    def load_global_rtd10(self):  # type: () -> GlobalRTD10DTO
        raise UnsupportedException()

    def refresh_set_configuration(self, thermostat):  # type: (Thermostat) -> None
        thermostat_pid = self.thermostat_pids.get(thermostat.number)
        if thermostat_pid is not None:
            thermostat_pid.update_thermostat(thermostat)
        else:
            thermostat_pid = ThermostatPid(thermostat, self._pump_valve_controller)
            self.thermostat_pids[thermostat.number] = thermostat_pid
        self._sync_scheduler()
        thermostat_pid.tick()

    def _thermostat_config_changed(self):
        gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'thermostats'})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def _thermostat_changed(self, thermostat_number, active_preset, current_setpoint, actual_temperature, percentages, room):
        # type: (int, str, float, Optional[float], List[float], int) -> None
        location = {'room_id': room}
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE,
                                     {'id': thermostat_number,
                                      'status': {'preset': active_preset,
                                                 'current_setpoint': current_setpoint,
                                                 'actual_temperature': actual_temperature,
                                                 'output_0': percentages[0] if len(percentages) >= 1 else None,
                                                 'output_1': percentages[1] if len(percentages) >= 2 else None},
                                      'location': location})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _thermostat_group_changed(self, thermostat_group):
        # type: (ThermostatGroup) -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_GROUP_CHANGE,
                                     {'id': 0,
                                      'status': {'state': 'ON' if thermostat_group.on else 'OFF',
                                                 'mode': 'COOLING' if thermostat_group.mode == 'cooling' else 'HEATING'},
                                      'location': {}})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    # Obsolete unsupported calls

    def save_global_rtd10(self, rtd10):  # type: (GlobalRTD10DTO) -> None
        raise UnsupportedException()

    def load_heating_rtd10(self, rtd10_id):  # type: (int) -> RTD10DTO
        raise UnsupportedException()

    def load_heating_rtd10s(self):  # type: () -> List[RTD10DTO]
        raise UnsupportedException()

    def save_heating_rtd10s(self, rtd10s):  # type: (List[RTD10DTO]) -> None
        raise UnsupportedException()

    def load_cooling_rtd10(self, rtd10_id):  # type: (int) -> RTD10DTO
        raise UnsupportedException()

    def load_cooling_rtd10s(self):  # type: () -> List[RTD10DTO]
        raise UnsupportedException()

    def save_cooling_rtd10s(self, rtd10s):  # type: (List[RTD10DTO]) -> None
        raise UnsupportedException()

    def set_airco_status(self, thermostat_id, airco_on):
        raise UnsupportedException()

    def load_airco_status(self):
        raise UnsupportedException()


@post_save(sender=ThermostatGroup)
@Inject
def on_thermostat_group_change_handler(model_class, instance, created, thermostat_controller=INJECTED):
    _ = model_class
    if not created:
        thermostat_controller._thermostat_group_changed(instance)
