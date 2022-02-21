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

import logging
from datetime import datetime, timedelta

from gateway.daemon_thread import DaemonThread
from gateway.dto import RTD10DTO, GlobalRTD10DTO, PumpGroupDTO, ScheduleDTO, \
    ThermostatDTO, ThermostatGroupDTO, ThermostatGroupStatusDTO, \
    ThermostatStatusDTO
from gateway.enums import ThermostatMode, ThermostatState
from gateway.events import GatewayEvent
from gateway.exceptions import UnsupportedException
from gateway.mappers import ThermostatMapper
from gateway.models import DaySchedule, Output, OutputToThermostatGroup, \
    Preset, Pump, PumpToValve, Schedule, Sensor, Thermostat, ThermostatGroup, \
    Valve, ValveToThermostat
from gateway.pubsub import PubSub
from gateway.scheduling_controller import SchedulingController
from gateway.thermostat.gateway.pump_valve_controller import \
    PumpValveController
from gateway.thermostat.gateway.thermostat_pid import ThermostatPid
from gateway.thermostat.thermostat_controller import ThermostatController
from ioc import INJECTED, Inject

if False:  # MYPY
    from typing import Dict, Iterable, List, Optional, Tuple, Set
    from gateway.output_controller import OutputController
    from gateway.sensor_controller import SensorController

logger = logging.getLogger(__name__)


class ThermostatControllerGateway(ThermostatController):

    # TODO: At this moment, a pump group strictly speaking is not related to any thermostat,
    #  nor to cooling/heating. Yet in the `classic` implementation there is. This means that
    #  changing a pump group could influence another pump group, since their `number` is shared.

    THERMOSTAT_PID_UPDATE_INTERVAL = 60
    PUMP_UPDATE_INTERVAL = 30

    @Inject
    def __init__(self, output_controller=INJECTED, sensor_controller=INJECTED, scheduling_controller=INJECTED, pubsub=INJECTED):
        # type: (OutputController, SensorController, SchedulingController, PubSub) -> None
        super(ThermostatControllerGateway, self).__init__(output_controller)
        self._sensor_controller = sensor_controller
        self._scheduling_controller = scheduling_controller
        self._pubsub = pubsub
        self._running = False
        self._sync_auto_setpoints = True
        self._pid_loop_thread = None  # type: Optional[DaemonThread]
        self._update_pumps_thread = None  # type: Optional[DaemonThread]
        self.thermostat_pids = {}  # type: Dict[int, ThermostatPid]
        self._pump_valve_controller = PumpValveController()

        self._pubsub.subscribe_gateway_events(PubSub.GatewayTopics.SCHEDULER, self._handle_scheduler_event)

    def get_features(self):
        # type: () -> Set[str]
        return {'thermostats_gateway',
                'thermostat_groups'}

    def start(self):  # type: () -> None
        logger.info('Starting gateway thermostatcontroller...')
        if not self._running:
            self._running = True
            self._pid_loop_thread = DaemonThread(name='thermostatpid',
                                                 target=self._pid_tick,
                                                 interval=self.THERMOSTAT_PID_UPDATE_INTERVAL)
            self._pid_loop_thread.start()

            self._update_pumps_thread = DaemonThread(name='thermostatpumps',
                                                     target=self._update_pumps,
                                                     interval=self.PUMP_UPDATE_INTERVAL)
            self._update_pumps_thread.start()
            super(ThermostatControllerGateway, self).start()
            logger.info('Starting gateway thermostatcontroller... Done')
        else:
            raise RuntimeError('GatewayThermostatController already running. Please stop it first.')

    def stop(self):  # type: () -> None
        if not self._running:
            logger.warning('Stopping an already stopped thermostatcontroller.')
        self._running = False
        if self._pid_loop_thread is not None:
            self._pid_loop_thread.stop()
        if self._update_pumps_thread is not None:
            self._update_pumps_thread.stop()
        super(ThermostatControllerGateway, self).stop()

    def _pid_tick(self):  # type: () -> None
        for thermostat_number, thermostat_pid in self.thermostat_pids.items():
            try:
                thermostat_pid.tick()
            except Exception:
                logger.exception('There was a problem with calculating thermostat PID {}'.format(thermostat_pid))

    def _handle_scheduler_event(self, gateway_event):
        # type: (GatewayEvent) -> None
        logger.debug('Received scheduler event %s', gateway_event)
        if gateway_event.type == GatewayEvent.Types.THERMOSTAT_CHANGE:
            thermostat = Thermostat.get(number=gateway_event.data['id'])
            preset = thermostat.get_preset(Preset.Types.AUTO)

            field_mapping = {ThermostatGroup.Modes.HEATING: 'heating_setpoint',
                             ThermostatGroup.Modes.COOLING: 'cooling_setpoint'}
            field = field_mapping.get(gateway_event.data['status']['mode'])
            if field:
                setattr(preset, field, gateway_event.data['status']['current_setpoint'])
                preset.save()
                self.tick_thermostat(thermostat=thermostat)

    def refresh_config_from_db(self):  # type: () -> None
        self.refresh_thermostats_from_db()
        self._pump_valve_controller.refresh_from_db()

    def refresh_thermostats_from_db(self):  # type: () -> None
        self._sync_auto_presets()
        for thermostat in list(Thermostat.select()):
            thermostat_pid = self.thermostat_pids.get(thermostat.number)
            if thermostat_pid is None:
                thermostat_pid = ThermostatPid(thermostat, self._pump_valve_controller)
                thermostat_pid.subscribe_state_changes(self._thermostat_changed)
                self.thermostat_pids[thermostat.number] = thermostat_pid
            thermostat_pid.update_thermostat(thermostat)
            thermostat_pid.tick()
            # TODO: Delete stale/removed thermostats
        # FIXME: remove invalid pumps, database should cascade instead.
        Pump.delete().where(Pump.output.is_null()) \
            .execute()
        self._sync_scheduler()
        # Ensure changes for auto presets are published
        for thermostat in list(Thermostat.select()):
            thermostat_pid = self.thermostat_pids.get(thermostat.number)
            if thermostat_pid:
                thermostat_pid.update_thermostat(thermostat)
                thermostat_pid.tick()

    def _update_pumps(self):  # type: () -> None
        try:
            self._pump_valve_controller.steer()
        except Exception:
            logger.exception('Could not update pumps.')

    def _sync(self):  # type: () -> None
        # refresh the config from the database
        try:
            self.refresh_config_from_db()
        except Exception:
            logger.exception('Could not get thermostat config.')

        # use the same sync thread for periodically pushing out thermostat status events
        self._publish_states()

    def _publish_states(self):
        # 1. publish thermostat group status events
        for thermostat_group in ThermostatGroup.select():
            try:
                self._thermostat_group_changed(thermostat_group)
            except Exception:
                logger.exception('Could not publish thermostat group %s', thermostat_group)

        # 2. publish thermostat unit status events
        for thermostat_pid in self.thermostat_pids.values():
            try:
                status = thermostat_pid.get_status()
                self._thermostat_changed(*status)
            except Exception:
                logger.exception('Could not publish %s', thermostat_pid)

    def _sync_auto_presets(self):
        # type: () -> None
        if not self._sync_auto_setpoints:
            return
        logger.info('Syncing auto setpoints from schedule')
        self._sync_auto_setpoints = False
        for preset in list(Preset.select().where(Preset.type == Preset.Types.AUTO)):
            # Restore setpoint from auto schedule.
            now = datetime.now()
            items = [(ThermostatGroup.Modes.HEATING, 'heating_setpoint', preset.thermostat.heating_schedules),
                     (ThermostatGroup.Modes.COOLING, 'cooling_setpoint', preset.thermostat.cooling_schedules)]
            for mode, field, day_schedules in items:
                try:
                    if not day_schedules:
                        for i in range(7):
                            schedule = DaySchedule(index=i, thermostat=preset.thermostat, mode=mode)
                            schedule.schedule_data = DaySchedule.DEFAULT_SCHEDULE[mode]
                            day_schedules.append(schedule)
                    _, setpoint = self._scheduling_controller.last_thermostat_setpoint(day_schedules)
                    setattr(preset, field, setpoint)
                except StopIteration:
                    logger.warning('could not determine %s setpoint from schedule', mode)
            preset.save()

    def _sync_scheduler(self):
        # type: () -> None
        for thermostat_id, pid in self.thermostat_pids.items():
            for mode, day_schedules in [(ThermostatGroup.Modes.HEATING, pid.thermostat.heating_schedules),
                                        (ThermostatGroup.Modes.COOLING, pid.thermostat.cooling_schedules)]:
                self._scheduling_controller.update_thermostat_setpoints(thermostat_id, mode, day_schedules)

    def set_current_setpoint(self, thermostat_number, temperature=None, heating_temperature=None, cooling_temperature=None):
        # type: (int, Optional[float], Optional[float], Optional[float]) -> None
        self._set_current_setpoint(thermostat_number=thermostat_number,
                                   temperature=temperature,
                                   heating_temperature=heating_temperature,
                                   cooling_temperature=cooling_temperature)

    def _set_current_setpoint(self, thermostat_number=None, thermostat=None, temperature=None, heating_temperature=None, cooling_temperature=None, postpone_tick=False):
        # type: (Optional[int], Optional[Thermostat], Optional[float], Optional[float], Optional[float], bool) -> bool
        if temperature is None and heating_temperature is None and cooling_temperature is None:
            return False

        if thermostat is None:
            thermostat = Thermostat.get(number=thermostat_number)

        # When setting a setpoint manually, switch to manual preset except for when we are in scheduled mode
        # scheduled mode will override the setpoint when the next edge in the schedule is triggered
        active_preset = thermostat.active_preset
        if active_preset.type not in [Preset.Types.AUTO, Preset.Types.MANUAL]:
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

        if not postpone_tick:
            self.tick_thermostat(thermostat=thermostat)
        return True

    def get_current_preset(self, thermostat_number):  # type: (int) -> Preset
        thermostat = Thermostat.get(number=thermostat_number)
        return thermostat.active_preset

    def set_current_preset(self, preset_type, thermostat_number):
        self._set_current_preset(preset_type=preset_type,
                                 thermostat_number=thermostat_number)

    def _set_current_preset(self, preset_type, thermostat_number=None, thermostat=None, postpone_tick=False):
        # type: (str, Optional[int], Optional[Thermostat], bool) -> bool
        if thermostat is None:
            thermostat = Thermostat.get(number=thermostat_number)

        preset = thermostat.get_preset(preset_type)
        if preset.type == Preset.Types.AUTO:
            # Restore setpoint from auto schedule.
            now = datetime.now()
            items = [(ThermostatGroup.Modes.HEATING, 'heating_setpoint', thermostat.heating_schedules),
                     (ThermostatGroup.Modes.COOLING, 'cooling_setpoint', thermostat.cooling_schedules)]
            for mode, field, day_schedules in items:
                try:
                    if not day_schedules:
                        for i in range(7):
                            schedule = DaySchedule(index=i, thermostat=thermostat, mode=mode)
                            schedule.schedule_data = DaySchedule.DEFAULT_SCHEDULE[mode]
                            day_schedules.append(schedule)
                    _, setpoint = self._scheduling_controller.last_thermostat_setpoint(day_schedules)
                    setattr(preset, field, setpoint)
                except StopIteration:
                    logger.warning('could not determine %s setpoint from schedule', mode)
            preset.save()
            self.tick_thermostat(thermostat=thermostat)

        if thermostat.active_preset == preset:
            return False

        thermostat.active_preset = preset
        thermostat.save()
        if not postpone_tick:
            self.tick_thermostat(thermostat=thermostat)
        return True

    def set_current_state(self, state, thermostat_number=None, thermostat=None, postpone_tick=False):
        # type: (str, Optional[int], Optional[Thermostat], bool) -> bool
        if thermostat is None:
            thermostat = Thermostat.get(number=thermostat_number)

        if thermostat.state == state:
            return False
        thermostat.state = state
        thermostat.save()

        if not postpone_tick:
            self.tick_thermostat(thermostat=thermostat)
        return True

    def tick_thermostat(self, thermostat_number=None, thermostat=None):  # type: (Optional[int], Optional[Thermostat]) -> None
        if thermostat is None:
            thermostat = Thermostat.get(number=thermostat_number)

        thermostat_pid = self.thermostat_pids.get(thermostat.number)
        if thermostat_pid is not None:
            thermostat_pid.update_thermostat(thermostat=thermostat)
            thermostat_pid.tick()

    def get_thermostat_group_status(self):  # type: () -> List[ThermostatGroupStatusDTO]
        def get_output_level(output_number):
            if output_number is None:
                return 0  # we are returning 0 if outputs are not configured
            try:
                output = self._output_controller.get_output_status(output_number)
            except ValueError:
                logger.info('Output {0} state not yet available'.format(output_number))
                return 0  # Output state is not yet cached (during startup)
            if output.status is False or output.dimmer is None:
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

        statuses = []
        for thermostat_group in list(ThermostatGroup.select()):  # type: ThermostatGroup
            group_status = ThermostatGroupStatusDTO(id=thermostat_group.number,
                                                    automatic=True,  # Default, will be updated below
                                                    setpoint=0,  # Default, will be updated below
                                                    cooling=thermostat_group.mode == ThermostatMode.COOLING,
                                                    mode=thermostat_group.mode)

            outside_temperature = get_temperature_from_sensor(thermostat_group.sensor)

            thermostat_statusses = []
            for thermostat in thermostat_group.thermostats:
                valves = thermostat.cooling_valves if thermostat_group.mode == ThermostatMode.COOLING else thermostat.heating_valves
                db_outputs = [valve.output.number for valve in valves]
                thermostat_pid = self.thermostat_pids.get(thermostat.number)

                number_of_outputs = len(db_outputs)
                if number_of_outputs > 2:
                    logger.warning('Only 2 outputs are supported in the old format. Total: {0} outputs.'.format(number_of_outputs))

                output0_level = get_output_level(db_outputs[0] if number_of_outputs > 0 else None)
                output1_level = get_output_level(db_outputs[1] if number_of_outputs > 1 else None)
                if thermostat_pid is None:
                    steering_power = (output0_level + output1_level) // 2  # type: Optional[int]
                else:
                    steering_power = thermostat_pid.steering_power

                active_preset = thermostat.active_preset
                if thermostat_group.mode == ThermostatMode.COOLING:
                    setpoint_temperature = active_preset.cooling_setpoint
                else:
                    setpoint_temperature = active_preset.heating_setpoint

                actual_temperature = thermostat_pid.current_temperature if thermostat_pid is not None else None

                thermostat_statusses.append(ThermostatStatusDTO(id=thermostat.number,
                                                                actual_temperature=actual_temperature,
                                                                setpoint_temperature=setpoint_temperature,
                                                                outside_temperature=outside_temperature,
                                                                mode=0,  # TODO: Need to be fixed
                                                                state=thermostat.state,
                                                                automatic=active_preset.type == Preset.Types.AUTO,
                                                                setpoint=Preset.TYPE_TO_SETPOINT.get(active_preset.type, 0),
                                                                output_0_level=output0_level,
                                                                output_1_level=output1_level,
                                                                steering_power=steering_power,
                                                                preset=thermostat.active_preset.type))

            group_status.statusses = thermostat_statusses

            # Update global references
            group_status.automatic = all(status.automatic for status in group_status.statusses)
            used_setpoints = set(status.setpoint for status in group_status.statusses)
            group_status.setpoint = next(iter(used_setpoints)) if len(used_setpoints) == 1 else 0  # 0 is a fallback
            statuses.append(group_status)
        return statuses

    def set_thermostat_mode(self, thermostat_on, cooling_mode=False, cooling_on=False, automatic=None, setpoint=None):
        mode = ThermostatMode.COOLING if cooling_mode else ThermostatMode.HEATING
        state = thermostat_on
        if mode == ThermostatMode.COOLING:
            state = state and cooling_on
        for thermostat_group in ThermostatGroup.select():
            self.set_thermostat_group(thermostat_group_id=thermostat_group.number,
                                      state=ThermostatState.ON if state else ThermostatState.OFF,
                                      mode=mode)

    def set_thermostat_group(self, thermostat_group_id, state=None, mode=None):
        # type: (int, Optional[str], Optional[str]) -> None
        thermostat_group = ThermostatGroup.get(number=thermostat_group_id)
        changed = False
        if mode is not None and thermostat_group.mode != mode:
            thermostat_group.mode = mode
            thermostat_group.save()
            self._set_mode_outputs(thermostat_group)
            self._thermostat_group_changed(thermostat_group)
            changed = True
        if changed or state is not None:
            for thermostat in thermostat_group.thermostats:
                if state is not None:
                    changed |= self.set_current_state(thermostat=thermostat,
                                                      state=state,
                                                      postpone_tick=True)
                changed |= self._set_current_preset(thermostat=thermostat,
                                                    preset_type=Preset.Types.AUTO,
                                                    postpone_tick=True)
                if changed:
                    self.tick_thermostat(thermostat=thermostat)

    def _set_mode_outputs(self, thermostat_group):  # type: (ThermostatGroup) -> None
        link_set = OutputToThermostatGroup.select() \
            .where((OutputToThermostatGroup.thermostat_group == thermostat_group) &
                   (OutputToThermostatGroup.mode == thermostat_group.mode))
        for link in list(link_set):
            self._output_controller.set_output_status(output_id=link.output.number,
                                                      is_on=link.value > 0,
                                                      dimmer=link.value)

    def load_heating_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        mode = ThermostatMode.HEATING
        thermostat = Thermostat.get(number=thermostat_id)
        return ThermostatMapper.orm_to_dto(thermostat, mode)

    def load_heating_thermostats(self):  # type: () -> List[ThermostatDTO]
        mode = ThermostatMode.HEATING
        return [ThermostatMapper.orm_to_dto(thermostat, mode)
                for thermostat in Thermostat.select()]

    def save_heating_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        self._save_thermostat_configurations(thermostats, ThermostatMode.HEATING)

    def load_cooling_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        mode = ThermostatMode.COOLING
        thermostat = Thermostat.get(number=thermostat_id)
        return ThermostatMapper.orm_to_dto(thermostat, mode)

    def load_cooling_thermostats(self):  # type: () -> List[ThermostatDTO]
        mode = ThermostatMode.COOLING
        return [ThermostatMapper.orm_to_dto(thermostat, mode)
                for thermostat in Thermostat.select()]

    def save_cooling_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        self._save_thermostat_configurations(thermostats, ThermostatMode.COOLING)

    def _save_thermostat_configurations(self, thermostats, mode):  # type: (List[ThermostatDTO], str) -> None
        for thermostat_dto in thermostats:
            logger.debug('Updating thermostat %s', thermostat_dto)
            thermostat = ThermostatMapper.dto_to_orm(thermostat_dto)
            thermostat.save()
            update, remove = ThermostatMapper.get_valve_links(thermostat_dto, mode)
            for valve_to_thermostat in remove:
                logger.debug('Removing valve %s of %s', valve_to_thermostat.valve, thermostat)
                valve_to_thermostat.valve.delete().execute()
            for valve_to_thermostat in update:
                logger.debug('Updating valve %s of %s', valve_to_thermostat.valve, thermostat)
                valve_to_thermostat.valve.save()
                valve_to_thermostat.save()
            if thermostat.sensor is None and thermostat.valves == []:
                logger.debug('Unconfigured thermostat %s', thermostat)
                thermostat.delete().execute()
            else:
                update, remove = ThermostatMapper.get_schedule_links(thermostat_dto, mode)
                for day_schedule in remove:
                    logger.debug('Removing schedule %s of %s', day_schedule, thermostat)
                    day_schedule.delete().execute()
                for day_schedule in update:
                    logger.debug('Updating schedule %s of %s', day_schedule, thermostat)
                    day_schedule.save()
                # TODO: trigger update for schedules
                update, remove = ThermostatMapper.get_preset_links(thermostat_dto, mode)
                for preset in remove:
                    logger.debug('Removing preset %s of %s', preset, thermostat)
                    preset.delete().execute()
                for preset in update:
                    logger.debug('Updating preset %s of %s', preset, thermostat)
                    preset.save()
        self._thermostat_config_changed()
        if self._sync_thread:
            self._sync_thread.request_single_run()

    def set_per_thermostat_mode(self, thermostat_id, automatic, setpoint):
        # type: (int, bool, int) -> None
        thermostat = Thermostat.get(number=thermostat_id)
        thermostat.automatic = automatic
        thermostat.save()

        if automatic:
            preset_type = Preset.Types.AUTO  # type: str
        else:
            preset_type = Preset.SETPOINT_TO_TYPE.get(setpoint, Preset.Types.AUTO)
        self._set_current_preset(preset_type=preset_type, thermostat=thermostat)

    def set_thermostat(self, thermostat_id, preset=None, state=None, temperature=None):
        # type: (int, Optional[str], Optional[str], Optional[float]) -> None
        thermostat = Thermostat.get(number=thermostat_id)
        change = False
        if preset is not None:
            change |= self._set_current_preset(thermostat=thermostat,
                                               preset_type=preset,
                                               postpone_tick=True)
        if state is not None:
            change |= self.set_current_state(thermostat=thermostat,
                                             state=state,
                                             postpone_tick=True)
        if temperature is not None:
            change |= self._set_current_setpoint(thermostat=thermostat,
                                                 temperature=temperature,
                                                 postpone_tick=True)
        if change:
            self.tick_thermostat(thermostat=thermostat)

    def load_thermostat_groups(self):
        # type: () -> List[ThermostatGroupDTO]
        config = []
        for thermostat_group in ThermostatGroup.select():
            pump_delay = None
            for thermostat in thermostat_group.thermostats:
                for valve in thermostat.valves:
                    pump_delay = valve.delay
                    break
            sensor_id = None if thermostat_group.sensor is None else thermostat_group.sensor.id
            thermostat_group_dto = ThermostatGroupDTO(id=thermostat_group.number,
                                                      name=thermostat_group.name,
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
            config.append(thermostat_group_dto)
        return config

    def load_thermostat_group(self, thermostat_group_id):
        # type: (int) -> ThermostatGroupDTO
        thermostat_group = ThermostatGroup.get(number=thermostat_group_id)
        pump_delay = None
        for thermostat in thermostat_group.thermostats:
            for valve in thermostat.valves:
                pump_delay = valve.delay
                break
        sensor_id = None if thermostat_group.sensor is None else thermostat_group.sensor.id
        thermostat_group_dto = ThermostatGroupDTO(id=thermostat_group.number,
                                                  name=thermostat_group.name,
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

    def save_thermostat_groups(self, thermostat_groups):  # type: (List[ThermostatGroupDTO]) -> None
        # Update thermostat group configuration
        logger.info('Groups %s', thermostat_groups)
        for thermostat_group_dto in thermostat_groups:
            thermostat_group = ThermostatGroup.get_or_none(number=thermostat_group_dto.id)  # type: ThermostatGroup
            if thermostat_group is None:
                thermostat_group = ThermostatGroup(number=thermostat_group_dto.id)
                logger.info('Creating new ThermostatGroup %s', thermostat_group.number)
            changed = False
            if 'name' in thermostat_group_dto.loaded_fields:
                thermostat_group.name = thermostat_group_dto.name
                changed = True
            if 'outside_sensor_id' in thermostat_group_dto.loaded_fields:
                sensor = None if thermostat_group_dto.outside_sensor_id is None else \
                    Sensor.get(id=thermostat_group_dto.outside_sensor_id)
                thermostat_group.sensor = sensor
                changed = True
            if 'threshold_temperature' in thermostat_group_dto.loaded_fields:
                thermostat_group.threshold_temperature = thermostat_group_dto.threshold_temperature
                changed = True
            if changed:
                thermostat_group.save()
                self._thermostat_group_changed(thermostat_group)

            # Link configuration outputs to global thermostat config
            for mode in [ThermostatMode.COOLING, ThermostatMode.HEATING]:
                links = {link.index: link
                         for link in OutputToThermostatGroup
                             .select()
                             .where((OutputToThermostatGroup.thermostat_group == thermostat_group) &
                                    (OutputToThermostatGroup.mode == mode))}
                for i in range(4):
                    field = 'switch_to_{0}_{1}'.format(mode, i)
                    if field not in thermostat_group_dto.loaded_fields:
                        continue

                    link = links.get(i)
                    data = getattr(thermostat_group_dto, field)
                    if data is None:
                        if link is not None:
                            link.delete_instance()
                    else:
                        output_number, value = data
                        output = Output.get(number=output_number)
                        if link is None:
                            OutputToThermostatGroup.create(output=output,
                                                           thermostat_group=thermostat_group,
                                                           mode=mode,
                                                           index=i,
                                                           value=value)
                        else:
                            link.output = output
                            link.value = value
                            link.save()

            if 'pump_delay' in thermostat_group_dto.loaded_fields:
                # Set valve delay for all valves in this group
                for thermostat in thermostat_group.thermostats:
                    for valve in thermostat.valves:
                        valve.delay = thermostat_group_dto.pump_delay
                        valve.save()
        self._thermostat_config_changed()

    def remove_thermostat_groups(self, thermostat_group_ids):  # type: (List[int]) -> None
        ThermostatGroup.delete().where(ThermostatGroup.number << thermostat_group_ids) \
            .execute()

    def load_heating_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        pump = Pump.get(number=pump_group_id) # type: Pump
        return PumpGroupDTO(id=pump_group_id,
                            pump_output_id=pump.output.number,
                            valve_output_ids=[valve.output.number for valve in pump.heating_valves])

    def load_heating_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        pump_groups = []
        for pump in Pump.select():
            pump_groups.append(PumpGroupDTO(id=pump.id,
                                            pump_output_id=pump.output.number,
                                            valve_output_ids=[valve.output.number for valve in pump.heating_valves]))
        return pump_groups

    def save_heating_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        return self._save_pump_groups(ThermostatGroup.Modes.HEATING, pump_groups)

    def load_cooling_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        pump = Pump.get(number=pump_group_id)
        return PumpGroupDTO(id=pump_group_id,
                            pump_output_id=pump.output.number,
                            valve_output_ids=[valve.output.number for valve in pump.cooling_valves])

    def load_cooling_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        pump_groups = []
        for pump in Pump.select():
            pump_groups.append(PumpGroupDTO(id=pump.id,
                                            pump_output_id=pump.output.number,
                                            valve_output_ids=[valve.output.number for valve in pump.cooling_valves]))
        return pump_groups

    def save_cooling_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        return self._save_pump_groups(ThermostatGroup.Modes.COOLING, pump_groups)

    def _save_pump_groups(self, mode, pump_groups):  # type: (str, List[PumpGroupDTO]) -> None
        for pump_group_dto in pump_groups:
            if 'pump_output_id' not in pump_group_dto.loaded_fields:
                pump = Pump.get(id=pump_group_dto.id)  # type: Pump
            if pump_group_dto.pump_output_id is None:
                Pump.delete().where(Pump.id == pump_group_dto.id).execute()
                continue
            output = None if pump_group_dto.pump_output_id is None else \
                Output.get(number=pump_group_dto.pump_output_id)
            pump, _ = Pump.get_or_create(id=pump_group_dto.id,
                                         defaults={'name': ''})
            pump.output = output
            pump.save()

            if 'valve_output_ids' not in pump_group_dto.loaded_fields:
                continue
            links = {pump_to_valve.valve.output.number: pump_to_valve
                     for pump_to_valve
                     in PumpToValve.select(PumpToValve, Pump, Valve, Output)
                                   .join_from(PumpToValve, Valve)
                                   .join_from(PumpToValve, Pump)
                                   .join_from(Valve, Output)
                                   .join_from(Valve, ValveToThermostat)
                                   .where((Pump.id == pump.id) &
                                          (ValveToThermostat.mode == mode))}
            for output_id in list(links.keys()):
                if output_id not in pump_group_dto.valve_output_ids:
                    pump_to_valve = links.pop(output_id)  # type: PumpToValve
                    pump_to_valve.delete_instance()
                else:
                    pump_group_dto.valve_output_ids.remove(output_id)
            for output_id in pump_group_dto.valve_output_ids:
                output = Output.get(number=output_id)
                valve = Valve.get_or_none(output=output)
                if valve is None:
                    valve = Valve(name='Output {0}'.format(output.number),
                                  output=output)
                    valve.save()
                PumpToValve.create(pump=pump,
                                   valve=valve)
        self._thermostat_config_changed()

    def load_global_rtd10(self):  # type: () -> GlobalRTD10DTO
        raise UnsupportedException()

    def _thermostat_config_changed(self):
        gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'thermostats'})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def _thermostat_changed(self, thermostat_number, active_preset, current_setpoint, actual_temperature, percentages, steering_power, room, state, mode):
        # type: (int, str, float, Optional[float], List[int], int, int, str, str) -> None
        location = {'room_id': room} if room not in (None, 255) else {}
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE,
                                     {'id': thermostat_number,
                                      'status': {'state': state.upper(),
                                                 'preset': active_preset.upper(),
                                                 'mode': mode.upper(),
                                                 'current_setpoint': current_setpoint,
                                                 'actual_temperature': actual_temperature,
                                                 'output_0': percentages[0] if len(percentages) >= 1 else None,
                                                 'output_1': percentages[1] if len(percentages) >= 2 else None,
                                                 'steering_power': steering_power},
                                      'location': location})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _thermostat_group_changed(self, thermostat_group):
        # type: (ThermostatGroup) -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_GROUP_CHANGE,
                                     {'id': thermostat_group.number,
                                      'status': {'mode': thermostat_group.mode.upper()},
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
