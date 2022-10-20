


import logging
from datetime import datetime, timedelta
from ioc import INJECTED, Inject, Injectable, Singleton
from gateway.dto import ScheduleDTO, ScheduleSetpointDTO
from gateway.scheduling_controller import SchedulingController
from gateway.models import Database, DaySchedule, Preset, Thermostat, ThermostatGroup


if False:  # MYPY
    from typing import Dict, List, Optional, Set, Tuple, Iterable
    from gateway.output_controller import OutputController
    from gateway.sensor_controller import SensorController


logger = logging.getLogger(__name__)


@Injectable.named('setpoint_controller')
class SetpointController(object):
    @Inject
    def __init__(self, scheduling_controller=INJECTED):
        self._thermostat_setpoints = {} # type: Dict[Tuple[int,str],List[ScheduleSetpointDTO]]
        self._scheduling_controller = scheduling_controller




    '''
    Set a manual setpoint and activate manual mode
    '''
    def overrule_current_setpoint(self, thermostat_id, temperature=None, heating_temperature=None, cooling_temperature=None):
        # type: (int, Optional[float], Optional[float], Optional[float]) -> None
        with Database.get_session() as db:
            thermostat = db.query(Thermostat).filter_by(number=thermostat_id).one()
            self._overrule_current_setpoint(thermostat,
                                       temperature=temperature,
                                       heating_temperature=heating_temperature,
                                       cooling_temperature=cooling_temperature)
            db.commit()




    '''
    Activate a specific preset type
    '''
    def set_current_preset(self, thermostat_id, preset_type):  # type: (int, str) -> None
        with Database.get_session() as db:
            thermostat = db.query(Thermostat).filter_by(id=thermostat_id).one()  # type: Thermostat
            self._set_current_preset(thermostat, preset_type=preset_type)
            change = bool(db.dirty)
            db.commit()
        if change:
            # self.tick_thermostat(thermostat_id)
            pass




    def get_current_setpoint(self, thermostat_id):  # type: (int) -> Dict
        with Database.get_session() as db:
            active_preset = db.query(Preset).filter_by(thermostat_id=thermostat_id).filter_by(active=True).one()

        heating_setpoint = active_preset.heating_setpoint
        cooling_setpoint = active_preset.cooling_setpoint
        setpoint = (heating_setpoint + cooling_setpoint)/2
        margin = abs(setpoint - heating_setpoint)

        setpoint = {
        "heating_setpoint" : heating_setpoint,  # minimum room temperature
        "cooling_setpoint" : cooling_setpoint,  # maximum room temperature
        "setpoint"         : setpoint,          # desired temperature
        "margin"           : margin             # deviation on the desired temperature
        }

        return setpoint




    '''
    Here we check the current dayschedule of the thermostat and if there are changes we update the schedule.
    The background schedule will then update the preset table for auto values and change the temperature on the saved triggers.
    This allows implementing the dayschedule in presets.
    '''
    def update_thermostat_setpoints(self, thermostat_id, mode, day_schedules):
        # type: (int, str, List[DaySchedule]) -> None
        key = (thermostat_id, mode)
        setpoints = []
        for t, setpoint in self._calculate_transitions(day_schedules, datetime.now()):
            setpoints.append(ScheduleSetpointDTO(thermostat=thermostat_id,
                                                 mode=mode,
                                                 temperature=setpoint,
                                                 weekday=t.weekday(),
                                                 hour=t.hour,
                                                 minute=t.minute))
        current_setpoints = self._thermostat_setpoints.get(key, [])
        if current_setpoints != setpoints:
            # remove the old triggers of the schedule
            for setpoint_dto in current_setpoints:
                self._scheduling_controller._abort(setpoint_dto)
            # add the new triggers to the schedule
            for setpoint_dto in setpoints:
                self._scheduling_controller._submit_setpoint(setpoint_dto)
            self._thermostat_setpoints[key] = setpoints




    '''
    This function solely acts as a manual overwrite of the setpoint:
    1. if current mode = automatic      ->      simply overwrite the setpoints in the Preset table of type automatic
                                                when there is a new transition, this manual setpoint will be overwritten
                                                and follow the day schedule again
    2. if current mode != automatic     ->      set manual mode active in preset table and other modes inactive
                                                set manual mode temperatures accordingly
    '''
    def _overrule_current_setpoint(self, thermostat, temperature=None, heating_temperature=None, cooling_temperature=None):
        # type: (Thermostat, Optional[float], Optional[float], Optional[float]) -> bool
        if not any([temperature, heating_temperature, cooling_temperature]):
            return False

        active_preset = thermostat.active_preset  # type: Optional[Preset]

        # check if the active preset is automatic or manual, if not, fetch/create a manual preset
        if active_preset is None or active_preset.type not in [Preset.Types.AUTO, Preset.Types.MANUAL]:
            # loop over all the presets and get the preset of manual type if exists, alse None
            active_preset = next((x for x in thermostat.presets if x.type == Preset.Types.MANUAL), None)
            # if no preset was found, create a manual preset
            if active_preset is None:
                active_preset = Preset(type=Preset.Types.MANUAL)
                thermostat.presets.append(active_preset)

            self._set_preset_active(thermostat, active_preset)

        if heating_temperature is None:
            heating_temperature = temperature
        if heating_temperature is not None:
            logger.debug("Setting heating setpoint to: {0}".format(heating_temperature))
            active_preset.heating_setpoint = float(heating_temperature)  # type: ignore

        if cooling_temperature is None:
            cooling_temperature = temperature
        if cooling_temperature is not None:
            logger.debug("Setting cooling setpoint to: {0}".format(cooling_temperature))
            active_preset.cooling_setpoint = float(cooling_temperature)  # type: ignore
        return True




    '''
    Activate a specific preset type
    '''
    def _set_current_preset(self, thermostat, preset_type):  # type: (Thermostat, str) -> None
        preset = next((x for x in thermostat.presets if x.type == preset_type), None)  # type: Optional[Preset]
        if preset is None:
            preset = Preset(thermostat=thermostat, type=preset_type,
                            heating_setpoint=Preset.DEFAULT_PRESETS['heating'].get(preset_type, 14.0),
                            cooling_setpoint=Preset.DEFAULT_PRESETS['cooling'].get(preset_type, 30.0))  # type: ignore

        if preset.type == Preset.Types.AUTO:
            self._update_auto_preset(thermostat)

        logger.debug("Changing Preset from {0} to {1}".format(thermostat.active_preset, preset))
        self._set_preset_active(thermostat, preset)




    '''
    Fetch the thermostat schedule from the Dayschedule table
    Determine if a transition needs to be made in the schedule?
    If yes, update the temperature for the auto preset of said thermostat
    This does not mean that the thermostat is in auto mode, we simply update the preset values
    '''
    def _update_auto_preset(self, thermostat):  #type: (Thermostat) -> None
        # fetch or create auto preset
        preset = next((x for x in thermostat.presets if x.type == Preset.Types.AUTO), None)
        if preset is None:
            preset = Preset(type=Preset.Types.AUTO)
            thermostat.presets.append(preset)

        items = [(ThermostatGroup.Modes.HEATING, 'heating_setpoint', thermostat.heating_schedules),
                 (ThermostatGroup.Modes.COOLING, 'cooling_setpoint', thermostat.cooling_schedules)]
        for mode, field, day_schedules in items:
            try:
                if not day_schedules:
                    for i in range(7):
                        schedule = DaySchedule(index=i, thermostat=thermostat, mode=mode)
                        schedule.schedule_data = DaySchedule.DEFAULT_SCHEDULE[mode]
                        day_schedules.append(schedule)
                _, setpoint = self.last_thermostat_setpoint(day_schedules)
                setattr(preset, field, setpoint)
            except StopIteration:
                logger.warning('could not determine %s setpoint from schedule', mode)




    '''
    extract setpoint from dayschedule
    '''
    def last_thermostat_setpoint(self, day_schedules):
        # type: (List[DaySchedule]) -> Tuple[datetime, float]
        now = datetime.now()
        transitions = sorted(self._calculate_transitions(day_schedules, now), reverse=True)
        last_setpoint = next((t, v) for t, v in transitions if t <= now)
        logger.debug("Last setpoint from schedule: {0}".format(last_setpoint))
        return last_setpoint




    """
    Calculate the setpoint transitions relative to a timestamp based on the
    given day schedules.
    """
    def _calculate_transitions(self, day_schedules, at):
        # type: (List[DaySchedule], datetime) -> Iterable[Tuple[datetime, float]]
        index = at.weekday()
        start_of_day = datetime(at.year, at.month, at.day)

        data = {}
        for day_schedule in day_schedules:
            offset = max(day_schedule.index, index) - min(day_schedule.index, index)
            # Shift last day schedule when at start of the week.
            if index == 0 and day_schedule.index == 6:
                offset -= 7
            if day_schedule.index < index:
                offset = -offset
            d = start_of_day + timedelta(days=offset)
            data.update({d + timedelta(seconds=int(k)): v
                         for k, v in day_schedule.schedule_data.items()})
        return sorted(data.items())




    def _set_preset_active(self, thermostat, preset):  #type: (Thermostat, Preset) -> None
        if thermostat.active_preset != preset:
            for p in thermostat.presets:
                p.active = False
            preset.active = True






 