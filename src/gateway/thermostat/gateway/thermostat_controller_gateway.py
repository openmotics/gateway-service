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

from sqlalchemy import select, update

from gateway.daemon_thread import DaemonThread
from gateway.dto import RTD10DTO, GlobalRTD10DTO, PumpGroupDTO, ScheduleDTO, \
    ThermostatDTO, ThermostatGroupDTO, ThermostatGroupStatusDTO, \
    ThermostatStatusDTO
from gateway.enums import ThermostatMode, ThermostatState
from gateway.events import GatewayEvent
from gateway.exceptions import UnsupportedException
from gateway.hal.master_event import MasterEvent
from gateway.mappers import ThermostatMapper
from gateway.models import Database, DaySchedule, Output, \
    HvacOutputLink, Preset, Pump, Sensor, Thermostat, \
    ThermostatGroup, Valve
#    OutputToThermostatGroupAssociation, Preset, Pump, PumpToValveAssociation, \
#    Schedule, Sensor, Thermostat, ThermostatGroup, Valve, \
#    IndoorLinkValves

from gateway.pubsub import PubSub
from gateway.valve_pump.valve_pump_controller import ValvePumpController
from gateway.scheduling_controller import SchedulingController
from gateway.thermostat.gateway.thermostat_pid import ThermostatPid
from gateway.thermostat.thermostat_controller import ThermostatController
from gateway.thermostat.gateway.hvac_drivers import HvacContactDriver
from gateway.thermostat.gateway.setpoint_controller import SetpointController
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
    def __init__(self, output_controller=INJECTED, sensor_controller=INJECTED, setpoint_controller=INJECTED, pubsub=INJECTED, valve_pump_controller=INJECTED):
        # type: (OutputController, SensorController, SetpointController, PubSub, ValvePumpController) -> None
        super(ThermostatControllerGateway, self).__init__(output_controller)
        self._sensor_controller = sensor_controller
        self._setpoint_controller = setpoint_controller
        self._pubsub = pubsub
        self._valve_pump_controller = valve_pump_controller
        self._running = False
        self._sync_auto_setpoints = True
        self._pid_loop_thread = None  # type: Optional[DaemonThread]
        self.thermostat_pids = {}  # type: Dict[int, ThermostatPid]

        self._pubsub.subscribe_gateway_events(PubSub.GatewayTopics.SCHEDULER, self._handle_scheduler_event)
        self._pubsub.subscribe_master_events(PubSub.MasterTopics.THERMOSTAT, self._handle_master_event)

        self._drivers = {}  # type: Dict[int, HvacContactDriver]

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

            super(ThermostatControllerGateway, self).start()
            logger.info('Starting gateway thermostatcontroller... Done')
            self._valve_pump_controller.start()
        else:
            raise RuntimeError('GatewayThermostatController already running. Please stop it first.')

    def stop(self):  # type: () -> None
        if not self._running:
            logger.warning('Stopping an already stopped thermostatcontroller.')
        self._running = False
        if self._pid_loop_thread is not None:
            self._pid_loop_thread.stop()
        super(ThermostatControllerGateway, self).stop()

    def _pid_tick(self):  # type: () -> None
        for thermostat_number, pid in self.thermostat_pids.items():
            try:
                pid.tick()
            except Exception:
                logger.exception('There was a problem with calculating <Thermostat {}>'.format(thermostat_number))

    def _handle_scheduler_event(self, gateway_event):
        # type: (GatewayEvent) -> None
        logger.debug('Received scheduler event %s', gateway_event)
        if gateway_event.type == GatewayEvent.Types.THERMOSTAT_CHANGE:
            thermostat_id = gateway_event.data['id']
            with Database.get_session() as db:
                thermostat = db.query(Thermostat).filter_by(number=thermostat_id).one()  # type: Thermostat
                preset = next((x for x in thermostat.presets if x.type == Preset.Types.AUTO), None)
                if preset is None:
                    preset = Preset(thermostat=thermostat, type=Preset.Types.AUTO)
                    db.add(preset)

                field_mapping = {ThermostatGroup.Modes.HEATING: 'heating_setpoint',
                                 ThermostatGroup.Modes.COOLING: 'cooling_setpoint'}
                field = field_mapping.get(gateway_event.data['status']['mode'])
                if field:
                    setattr(preset, field, gateway_event.data['status']['current_setpoint'])
                    db.commit()
            self.tick_thermostat(thermostat_id)

    def _handle_master_event(self, master_event):  # type: (MasterEvent) -> None
        if master_event.type == MasterEvent.Types.EXECUTE_GATEWAY_API:
            if master_event.data['type'] == MasterEvent.APITypes.SET_THERMOSTAT_MODE:
                state = master_event.data['data']['state']
                mode = master_event.data['data']['mode']
                with Database.get_session() as db:
                    stmt = select(ThermostatGroup.number)  # type: ignore
                    numbers = db.execute(stmt).scalars()  # type: List[int]
                for group_nr in numbers:
                    self.set_thermostat_group(thermostat_group_id=group_nr,
                                              state=state, mode=mode)
                logger.info('Changed the state/mode for all ThermostatGroups to {0}/{1} by master event'.format(state, mode))
            elif master_event.data['type'] == MasterEvent.APITypes.SET_THERMOSTAT_PRESET:
                preset = master_event.data['data']['preset']
                if preset in Preset.ALL_TYPES:
                    with Database.get_session() as db:
                        stmt = select(Thermostat.number)  # type: ignore
                        numbers = db.execute(stmt).scalars()
                    for thermostat_nr in numbers:
                        thermostat_id = self._thermostatnr_to_thermostatid(thermostat_nr)
                        if thermostat_id is not None:
                            self._setpoint_controller.set_current_preset(thermostat_id=thermostat_id, preset_type=preset)
                    logger.info('Changed preset for all Thermostats to {0} by master event'.format(preset))


    def refresh_config_from_db(self):  # type: () -> None
        self.refresh_thermostats_from_db()
        self._valve_pump_controller.update_from_db()


        # update heating/cooling output drivers
        for key, driver in self._drivers.items():
            driver._update_from_database()

    def refresh_thermostats_from_db(self):  # type: () -> None
        self._sync_auto_presets()
        removed_thermostats = set(self.thermostat_pids.keys())
        with Database.get_session() as db:
            for thermostat in db.query(Thermostat):
                removed_thermostats.discard(thermostat.number)
                pid = self.thermostat_pids.get(thermostat.number)
                if pid is None:
                    pid = ThermostatPid(thermostat)
                    pid.subscribe_state_changes(self._thermostat_changed)
                    self.thermostat_pids[thermostat.number] = pid
            # TODO: Delete stale/removed thermostats
            for thermostat_id in removed_thermostats:
                self.thermostat_pids.pop(thermostat_id, None)
        self._sync_scheduler()
        with Database.get_session() as db:
            # Ensure changes for auto presets are published
            for thermostat in db.query(Thermostat):
                pid = self.thermostat_pids.get(thermostat.number)
                if pid:
                    pid.update_thermostat()
                    pid.tick()

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
        with Database.get_session() as db:
            for thermostat_group in db.query(ThermostatGroup):
                try:
                    self._thermostat_group_changed(thermostat_group)
                except Exception:
                    logger.exception('Could not publish thermostat group %s', thermostat_group)

        # 2. publish thermostat unit status events
        for pid in self.thermostat_pids.values():
            try:
                status = pid.get_status()
                self._thermostat_changed(*status)
            except Exception:
                logger.exception('Could not publish %s', pid)

    def _sync_auto_presets(self):
        # update preset table auto column when "_sync_auto_setpoints" is True for ?all thermostats
        # type: () -> None
        if not self._sync_auto_setpoints:
            return
        logger.info('Syncing auto setpoints from schedule')
        self._sync_auto_setpoints = False
        with Database.get_session() as db:
            for preset in db.query(Preset).filter_by(type=Preset.Types.AUTO):
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
                        _, setpoint = self._setpoint_controller.last_thermostat_setpoint(day_schedules)
                        setattr(preset, field, setpoint)
                    except StopIteration:
                        logger.warning('could not determine %s setpoint from schedule', mode)
            db.commit()

    def _sync_scheduler(self):
        # type: () -> None
        with Database.get_session() as db:
            for thermostat_id, pid in self.thermostat_pids.items():
                thermostat = db.query(Thermostat).filter_by(number=thermostat_id).one()  # type: Thermostat
                for mode, day_schedules in [(ThermostatGroup.Modes.HEATING, thermostat.heating_schedules),
                                            (ThermostatGroup.Modes.COOLING, thermostat.cooling_schedules)]:
                    self._setpoint_controller.update_thermostat_setpoints(thermostat_id, mode, day_schedules)

    def set_current_setpoint(self, thermostat_id, temperature=None, heating_temperature=None, cooling_temperature=None):
        # type: (int, Optional[float], Optional[float], Optional[float]) -> None
        with Database.get_session() as db:
            thermostat = db.query(Thermostat).filter_by(number=thermostat_id).one()
            self._setpoint_controller._overrule_current_setpoint(thermostat,
                                       temperature=temperature,
                                       heating_temperature=heating_temperature,
                                       cooling_temperature=cooling_temperature)
            db.commit()
        self.tick_thermostat(thermostat_id)

    def get_current_preset(self, thermostat_number):  # type: (int) -> str
        with Database.get_session() as db:
            thermostat = db.query(Thermostat).filter_by(number=thermostat_number).one()  # type: Thermostat
            return thermostat.active_preset.type

    def _set_current_state(self, thermostat, state):
        # type: (Thermostat, str) -> None
        thermostat.state = state

    def tick_thermostat(self, thermostat_id):  # type: (int) -> None
        pid = self.thermostat_pids.get(thermostat_id)
        if pid is not None:
            pid.update_thermostat()
            pid.tick()
        else:
            logger.warning('Can\'t update PID for <Thermostat %s>', thermostat_id)

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
        with Database.get_session() as db:
            for thermostat_group in db.query(ThermostatGroup):  # type: ThermostatGroup
                group_status = ThermostatGroupStatusDTO(id=thermostat_group.number,
                                                        automatic=True,  # Default, will be updated below
                                                        setpoint=0,  # Default, will be updated below
                                                        cooling=thermostat_group.mode == ThermostatMode.COOLING,
                                                        mode=thermostat_group.mode)

                outside_temperature = get_temperature_from_sensor(thermostat_group.sensor)

                thermostat_statusses = []
                for thermostat in thermostat_group.thermostats:
                    valves = [x.valve for x in getattr(thermostat, '{0}_valve_associations'.format(thermostat_group.mode))]
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
                    setpoint_temperature = getattr(active_preset, '{0}_setpoint'.format(thermostat_group.mode))
                    actual_temperature = thermostat_pid.current_temperature if thermostat_pid is not None else None

                    thermostat_statusses.append(ThermostatStatusDTO(id=thermostat.number,
                                                                    actual_temperature=actual_temperature,
                                                                    setpoint_temperature=setpoint_temperature,
                                                                    outside_temperature=outside_temperature,
                                                                    mode=thermostat_group.mode,
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
        with Database.get_session() as db:
            stmt = select(ThermostatGroup.number)  # type: ignore
            groups = db.execute(stmt).scalars()
        for group_nr in groups:
            self.set_thermostat_group(thermostat_group_id=group_nr,
                                      state=ThermostatState.ON if state else ThermostatState.OFF,
                                      mode=mode)

    def set_thermostat_group(self, thermostat_group_id, state=None, mode=None):
        # type: (int, Optional[str], Optional[str]) -> None

        # check if a driver already exists, create a driver if not
        if thermostat_group_id not in self._drivers:
            self._drivers[thermostat_group_id] = HvacContactDriver(thermostat_group_id)
        # fetch the driver for this thermostat group
        driver = self._drivers[thermostat_group_id]

        with Database.get_session() as db:
            thermostat_group = db.query(ThermostatGroup).filter_by(number=thermostat_group_id).one()  # type: ThermostatGroup
            changed = False
            if mode is not None and thermostat_group.mode != mode:
                thermostat_group.mode = mode
                driver.steer(mode=mode)
                self._thermostat_group_changed(thermostat_group)
                changed = True
            if changed or state is not None:
                for thermostat in thermostat_group.thermostats:
                    if state is not None:
                        self._set_current_state(thermostat,
                                                state=state)
                    self._setpoint_controller._set_current_preset(thermostat=thermostat,
                                             preset_type=Preset.Types.AUTO)
            change = bool(db.dirty)
            db.commit()
            if changed:
                for thermostat in thermostat_group.thermostats:
                    self.tick_thermostat(thermostat.number)

    def load_heating_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        mode = ThermostatMode.HEATING
        with Database.get_session() as db:
            thermostat = db.query(Thermostat).filter_by(number=thermostat_id).one()  # type: Thermostat
            return ThermostatMapper(db).orm_to_dto(thermostat, mode)

    def load_heating_thermostats(self):  # type: () -> List[ThermostatDTO]
        mode = ThermostatMode.HEATING
        with Database.get_session() as db:
            mapper = ThermostatMapper(db)
            return [mapper.orm_to_dto(thermostat, mode) for thermostat in db.query(Thermostat)]

    def save_heating_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        self._save_thermostat_configurations(thermostats, ThermostatMode.HEATING)

    def load_cooling_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        mode = ThermostatMode.COOLING
        with Database.get_session() as db:
            thermostat = db.query(Thermostat).filter_by(number=thermostat_id).one()
            return ThermostatMapper(db).orm_to_dto(thermostat, mode)

    def load_cooling_thermostats(self):  # type: () -> List[ThermostatDTO]
        mode = ThermostatMode.COOLING
        with Database.get_session() as db:
            mapper = ThermostatMapper(db)
            return [mapper.orm_to_dto(thermostat, mode)
                    for thermostat in db.query(Thermostat)]

    def save_cooling_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        self._save_thermostat_configurations(thermostats, ThermostatMode.COOLING)

    def _save_thermostat_configurations(self, thermostats, mode):  # type: (List[ThermostatDTO], str) -> None
        with Database.get_session() as db:
            for thermostat_dto in thermostats:
                mapper = ThermostatMapper(db)
                logger.debug('Updating thermostat %s', thermostat_dto)
                thermostat = mapper.dto_to_orm(thermostat_dto)
                db.add(thermostat)
                db.commit()
                update_valves, remove_valves = mapper.get_valve_links(thermostat_dto, mode)
                for valve_to_thermostat in remove_valves:
                    logger.debug('Removing %s of thermostat %s', valve_to_thermostat.valve.name, thermostat.number)
                    db.delete(valve_to_thermostat)
                for valve_to_thermostat in update_valves:
                    logger.debug('Updating %s of thermostat %s', valve_to_thermostat.valve.name, thermostat.number)
                db.commit()
                if thermostat.sensor is None and thermostat.valves == []:
                    logger.debug('Unconfigured thermostat %s', thermostat)
                    # FIXME: shouldn't be necessary
                    for preset in thermostat.presets:
                        db.delete(preset)
                    db.delete(thermostat)
                    self.thermostat_pids.pop(thermostat.id, None)
                else:
                    update_schedules, remove_schedules = mapper.get_schedule_links(thermostat_dto, mode)
                    for day_schedule in remove_schedules:
                        logger.debug('Removing schedule %s of thermostat %s', day_schedule, thermostat.number)
                        db.delete(day_schedule)
                    for day_schedule in update_schedules:
                        logger.debug('Updating schedule %s of thermostat %s', day_schedule, thermostat.number)
                    # TODO: trigger update for schedules
                    update_presets, remove_presets = mapper.get_preset_links(thermostat_dto, mode)
                    for preset in remove_presets:
                        logger.debug('Removing preset %s of thermostat %s', preset, thermostat.number)
                        db.delete(preset)
                    for preset in update_presets:
                        logger.debug('Updating preset %s of thermostat %s', preset, thermostat.number)
                db.commit()
        self._thermostat_config_changed()
        if self._sync_thread:
            self._sync_thread.request_single_run()

    def set_per_thermostat_mode(self, thermostat_id, automatic, setpoint):
        # type: (int, bool, int) -> None
        with Database.get_session() as db:
            thermostat = db.query(Thermostat).filter_by(number=thermostat_id).one()  # type: Thermostat
            thermostat.automatic = automatic
            if automatic:
                preset_type = Preset.Types.AUTO  # type: str
            else:
                preset_type = Preset.SETPOINT_TO_TYPE.get(setpoint, Preset.Types.AUTO)
            self._setpoint_controller._set_current_preset(thermostat, preset_type=preset_type)
            change = bool(db.dirty)
            db.commit()
        if change:
            self.tick_thermostat(thermostat_id)

    def set_thermostat(self, thermostat_id, preset=None, state=None, temperature=None):
        # type: (int, Optional[str], Optional[str], Optional[float]) -> None
        with Database.get_session() as db:
            thermostat = db.query(Thermostat).filter_by(number=thermostat_id).one()
            change = False
            if preset is not None:
                self._setpoint_controller._set_current_preset(thermostat,
                                         preset_type=preset)
            if state is not None:
                self._set_current_state(thermostat=thermostat,
                                        state=state)
            if temperature is not None:
                self._setpoint_controller._overrule_current_setpoint(thermostat=thermostat,
                                                               temperature=temperature)
            change = bool(db.dirty)
            db.commit()
        if change:
            self.tick_thermostat(thermostat_id)

    def load_thermostat_groups(self):
        # type: () -> List[ThermostatGroupDTO]
        config = []
        with Database.get_session() as db:
            for group in db.query(ThermostatGroup):
                pump_delay = None
                for thermostat in group.thermostats:
                    for valve in thermostat.valves:
                        pump_delay = valve.delay
                        break
                sensor_id = None if group.sensor is None else group.sensor.id
                thermostat_group_dto = ThermostatGroupDTO(id=group.number,
                                                          name=group.name,
                                                          outside_sensor_id=sensor_id,
                                                          threshold_temperature=group.threshold_temperature,
                                                          pump_delay=pump_delay)
                for mode, associations in [(ThermostatGroup.Modes.HEATING, group.heating_output_associations),
                                           (ThermostatGroup.Modes.COOLING, group.cooling_output_associations)]:
                    for output_to_thermostat_group in associations:
                        field = 'switch_to_{0}_{1}'.format(mode, output_to_thermostat_group.index)
                        setattr(thermostat_group_dto, field, (output_to_thermostat_group.output.number, output_to_thermostat_group.value))
                config.append(thermostat_group_dto)
        return config

    def load_thermostat_group(self, thermostat_group_id):
        # type: (int) -> ThermostatGroupDTO
        with Database.get_session() as db:
            group = db.query(ThermostatGroup).filter_by(number=thermostat_group_id).one()  # type: ThermostatGroup
            pump_delay = None
            for thermostat in group.thermostats:
                for valve in thermostat.valves:
                    pump_delay = valve.delay
                    break
            sensor_id = None if group.sensor is None else group.sensor.id
            thermostat_group_dto = ThermostatGroupDTO(id=group.number,
                                                      name=group.name,
                                                      outside_sensor_id=sensor_id,
                                                      threshold_temperature=group.threshold_temperature,
                                                      pump_delay=pump_delay)
            for mode, associations in [(ThermostatGroup.Modes.HEATING, group.heating_output_associations),
                                       (ThermostatGroup.Modes.COOLING, group.cooling_output_associations)]:
                index = 0
                for output_to_thermostat_group in associations:
                    field = 'switch_to_{0}_{1}'.format(mode, index)
                    setattr(thermostat_group_dto, field, (output_to_thermostat_group.output.number, output_to_thermostat_group.value))
                    index += 1
            return thermostat_group_dto



    def save_thermostat_groups(self, thermostat_groups):  # type: (List[ThermostatGroupDTO]) -> None
        # Update thermostat group configuration
        logger.debug('saving %s', thermostat_groups)
        with Database.get_session() as db:

            # get all available groups from the database as a dictionary Dict[group_number, ThermostatGroup]
            groups = {x.number: x for x in db.query(ThermostatGroup)}  # type: Dict[int, ThermostatGroup]

            # loop over all the new information from the api call
            for thermostat_group_dto in thermostat_groups:

                # get the group database object & update information
                thermostat_group = groups.get(thermostat_group_dto.id)
                if thermostat_group is None:
                    logger.info('creating <ThermostatGroup %s>', thermostat_group_dto.id)
                    thermostat_group = ThermostatGroup(number=thermostat_group_dto.id)
                    db.add(thermostat_group)
                if 'name' in thermostat_group_dto.loaded_fields:
                    thermostat_group.name = thermostat_group_dto.name
                if 'outside_sensor_id' in thermostat_group_dto.loaded_fields:
                    if thermostat_group_dto.outside_sensor_id is None:
                        thermostat_group.sensor = None
                    else:
                        sensor = db.get(Sensor, thermostat_group_dto.outside_sensor_id)  # type: Sensor
                        if sensor.physical_quantity != Sensor.PhysicalQuantities.TEMPERATURE:
                            raise ValueError('Invalid <Sensor %s %s> for ThermostatGroup' % (sensor.id, sensor.physical_quantity))
                        thermostat_group.sensor = sensor
                if 'threshold_temperature' in thermostat_group_dto.loaded_fields:
                    thermostat_group.threshold_temperature = thermostat_group_dto.threshold_temperature  # type: ignore
                if thermostat_group in db.dirty:
                    self._thermostat_group_changed(thermostat_group)

                # Link configuration outputs to global thermostat config, from here on we update the outputs linked to a group
                for mode, associations in [(ThermostatMode.HEATING, thermostat_group.heating_output_associations),
                                           (ThermostatMode.COOLING, thermostat_group.cooling_output_associations)
                                           # (thermostatMode.OFF, thermostat_group.off_output_associations)
                                           ]:

                    # we currently allow 4 connections for both heating and cooling (8 total)
                    for i in range(4):
                        field = 'switch_to_{0}_{1}'.format(mode, i)

                        # check if this field is provided in the api call / dto object
                        if field not in thermostat_group_dto.loaded_fields:
                            continue

                        # check if an association exists
                        try:
                            hvac_output_link = associations[i]  # type: Optional[HvacOutputLink]
                        except IndexError:
                            hvac_output_link = None

                        data = getattr(thermostat_group_dto, field)  # type: Tuple[int, int]
                        if data is None:
                            if hvac_output_link is not None:
                                db.delete(hvac_output_link)
                        else:
                            output_number, value = data
                            output = db.query(Output).filter_by(number=output_number).one()  # type: Output

                            # create new output entry if none exists
                            if hvac_output_link is None:
                                db.add(
                                    HvacOutputLink(
                                        hvac=thermostat_group,
                                        mode=mode,
                                        output=output,
                                        value=value
                                    )
                                )

                            # update output entry if one exists
                            else:
                                hvac_output_link.output = output
                                hvac_output_link.value = value

                if 'pump_delay' in thermostat_group_dto.loaded_fields:
                    # Set valve delay for all valves in this group
                    for thermostat in thermostat_group.thermostats:
                        for valve in thermostat.valves:
                            valve.delay = thermostat_group_dto.pump_delay
            if db.dirty:
                self._thermostat_config_changed()
            db.commit()
        if self._sync_thread:
            self._sync_thread.request_single_run()



    def remove_thermostat_groups(self, thermostat_group_ids):  # type: (List[int]) -> None
        with Database.get_session() as db:
            for group_id in thermostat_group_ids:
                group = db.query(ThermostatGroup).join(Thermostat).filter_by(number=group_id).one_or_none()  # type: Optional[ThermostatGroup]
                if group is None:
                    continue
                if group.thermostats:
                    raise ValueError('Refusing to delete a group that contains configured units: %s' % [x.number for x in group.thermostats])
                db.delete(group)
            db.commit()

    def load_heating_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        with Database.get_session() as db:
            pump = db.get(Pump, pump_group_id)  # type: Pump

            # FIXME: Workaround for mode filtering
            heating_valves = []
            for valve in pump.valves:
                for link in valve.thermostat_associations:
                    if link.mode == ThermostatGroup.Modes.HEATING:
                        heating_valves.append(valve)
                        break

            return PumpGroupDTO(id=pump_group_id,
                                pump_output_id=pump.output.number,
                                valve_output_ids=[valve.output.number for valve in heating_valves])

    def load_heating_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        pump_groups = []
        with Database.get_session() as db:
            for pump in db.query(Pump):  # type: Pump

                # FIXME: Workaround for mode filtering
                heating_valves = []
                for valve in pump.valves:
                    for link in valve.thermostat_associations:
                        if link.mode == ThermostatGroup.Modes.HEATING:
                            heating_valves.append(valve)
                            break

                pump_groups.append(PumpGroupDTO(id=pump.id,
                                                pump_output_id=pump.output.number,
                                                valve_output_ids=[valve.output.number for valve in heating_valves]))
            return pump_groups

    def save_heating_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        return self._save_pump_groups(ThermostatGroup.Modes.HEATING, pump_groups)

    def load_cooling_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        with Database.get_session() as db:
            pump = db.get(Pump, pump_group_id)  # type: Pump

            cooling_valves = []
            for valve in pump.valves:
                for link in valve.thermostat_associations:
                    if link.mode == ThermostatGroup.Modes.COOLING:
                        cooling_valves.append(valve)
                        break

            return PumpGroupDTO(id=pump_group_id,
                                pump_output_id=pump.output.number,
                                valve_output_ids=[valve.output.number for valve in cooling_valves])

    def load_cooling_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        pump_groups = []
        with Database.get_session() as db:
            for pump in db.query(Pump):  # type: Pump

                # FIXME: Workaround for mode filtering
                cooling_valves = []
                for valve in pump.valves:
                    for link in valve.thermostat_associations:
                        if link.mode == ThermostatGroup.Modes.COOLING:
                            cooling_valves.append(valve)
                            break

                pump_groups.append(PumpGroupDTO(id=pump.id,
                                                pump_output_id=pump.output.number,
                                                valve_output_ids=[valve.output.number for valve in cooling_valves]))
        return pump_groups

    def save_cooling_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        return self._save_pump_groups(ThermostatGroup.Modes.COOLING, pump_groups)

    def _save_pump_groups(self, mode, pump_groups):  # type: (str, List[PumpGroupDTO]) -> None
        with Database.get_session() as db:
            pumps = {x.id: x for x in db.query(Pump).all()}  # type: Dict[int, Pump]
            for pump_group_dto in pump_groups:
                pump = pumps.pop(pump_group_dto.id, None)  # type: Optional[Pump]
                if pump is None:
                    pump = Pump(id=pump_group_dto.id, name='Pump (output {0})'.format(pump_group_dto.pump_output_id))
                    db.add(pump)
                if 'pump_output_id' in pump_group_dto.loaded_fields:
                    if pump_group_dto.pump_output_id is None:
                        db.delete(pump)
                        continue
                    else:
                        pump.output = db.query(Output).filter_by(number=pump_group_dto.pump_output_id).one()
                if 'valve_output_ids' in pump_group_dto.loaded_fields:

                    # FIXME: Workaround for mode on association
                    current_valves = {}
                    valves = []
                    for valve_p in pump.valves:
                        for link in valve_p.thermostat_associations:
                            if link.mode == mode:
                                current_valves[valve_p.output.number] = valve_p
                                break
                        if valve_p.output.number not in current_valves:
                            valves.append(valve_p)

                    for output_nr in pump_group_dto.valve_output_ids:
                        if output_nr in current_valves:
                            valve = current_valves.pop(output_nr)  # type: Valve
                            valves.append(valve)
                        else:
                            valve = db.query(Valve) \
                                .join(Output) \
                                .where(Output.number == output_nr) \
                                .one()
                            current_valves[output_nr] = valve
                            valves.append(valve)
                    pump.valves = valves
            db.commit()
        self._thermostat_config_changed()

    def load_global_rtd10(self):  # type: () -> GlobalRTD10DTO
        raise UnsupportedException()

    def _thermostat_config_changed(self):
        gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'thermostats'})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def _thermostat_changed(self, thermostat_number, active_preset, current_setpoint, actual_temperature, percentages, steering_power, state, mode):
        # type: (int, str, float, Optional[float], List[int], int, str, str) -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE,
                                     {'id': thermostat_number,
                                      'status': {'state': state.upper(),
                                                 'preset': active_preset.upper(),
                                                 'mode': mode.upper(),
                                                 'current_setpoint': current_setpoint,
                                                 'actual_temperature': actual_temperature,
                                                 'output_0': percentages[0] if len(percentages) >= 1 else None,
                                                 'output_1': percentages[1] if len(percentages) >= 2 else None,
                                                 'steering_power': steering_power}})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _thermostat_group_changed(self, thermostat_group):
        # type: (ThermostatGroup) -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_GROUP_CHANGE,
                                     {'id': thermostat_group.number,
                                      'status': {'mode': thermostat_group.mode.upper()}})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _thermostatnr_to_thermostatid(self, thermostat_nr):  # type: (int) -> Optional[int]
        with Database.get_session() as db:
            thermostat = db.query(Thermostat).filter_by(number=thermostat_nr).one_or_none()  # type: Optional[ThermostatGroup]
        if thermostat is not None:
            return thermostat.id
        return None


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
