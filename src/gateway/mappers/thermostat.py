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

"""
Thermostat Mapper
"""
import datetime
import logging
import time

from sqlalchemy import func, select

from gateway.dto import ThermostatDTO, ThermostatScheduleDTO
from gateway.models import DaySchedule, Output, Preset, Room, Sensor, \
    Thermostat, ThermostatGroup, Valve, IndoorLinkValves

if False:  # MYPY
    from typing import Any, Dict, Iterator, List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)


class ThermostatMapper(object):
    def __init__(self, db):
        self._db = db

    def orm_to_dto(self, orm_object, mode):  # type: (Thermostat, Literal['cooling', 'heating']) -> ThermostatDTO
        sensor_id = None if orm_object.sensor is None else orm_object.sensor.id
        dto = ThermostatDTO(id=orm_object.number,
                            name=orm_object.name,
                            sensor=sensor_id,
                            pid_p=getattr(orm_object, 'pid_{0}_p'.format(mode)),
                            pid_i=getattr(orm_object, 'pid_{0}_i'.format(mode)),
                            pid_d=getattr(orm_object, 'pid_{0}_d'.format(mode)),
                            permanent_manual=orm_object.automatic,
                            room=orm_object.room.number if orm_object.room is not None else None,
                            thermostat_group=orm_object.group.number)

        # Outputs
        output_nrs = [x.valve.output.number for x in getattr(orm_object, '{0}_valve_associations'.format(mode))]
        if len(output_nrs) > 0:
            dto.output0 = output_nrs[0]
        if len(output_nrs) > 1:
            dto.output1 = output_nrs[1]
        if len(output_nrs) > 2:
            logger.warning('Only 2 outputs are supported in the old format. Total: {0} outputs.'.format(len(output_nrs)))

        # Presets
        dto.setp3 = Preset.DEFAULT_PRESETS[mode][Preset.Types.AWAY]
        dto.setp4 = Preset.DEFAULT_PRESETS[mode][Preset.Types.VACATION]
        dto.setp5 = Preset.DEFAULT_PRESETS[mode][Preset.Types.PARTY]
        for preset in orm_object.presets:
            setpoint = getattr(preset, '{0}_setpoint'.format(mode))
            if preset.type == Preset.Types.AWAY:
                dto.setp3 = setpoint
            elif preset.type == Preset.Types.VACATION:
                dto.setp4 = setpoint
            elif preset.type == Preset.Types.PARTY:
                dto.setp5 = setpoint

        # Schedules
        day_schedules = {schedule.index: schedule
                         for schedule in getattr(orm_object, '{0}_schedules'.format(mode))}
        for day_index, key in [(0, 'auto_mon'),
                               (1, 'auto_tue'),
                               (2, 'auto_wed'),
                               (3, 'auto_thu'),
                               (4, 'auto_fri'),
                               (5, 'auto_sat'),
                               (6, 'auto_sun')]:
            schedule = day_schedules[day_index].schedule_data if day_index in day_schedules else {}
            setattr(dto, key, ThermostatScheduleMapper.schedule_to_dto(schedule, mode))

        # TODO: Map missing [pid_int, setp0, setp1, setp2]
        return dto

    def dto_to_orm(self, thermostat_dto):  # type: (ThermostatDTO) -> Thermostat
        thermostat = self._db.query(Thermostat) \
            .where(Thermostat.number == thermostat_dto.id) \
            .join(ThermostatGroup, isouter=True) \
            .one_or_none()  # type: Optional[Thermostat]
        if thermostat is None:
            thermostat = Thermostat(number=thermostat_dto.id,
                                    start=0)
        if thermostat.group is None:
            thermostat.group = self._db.query(ThermostatGroup).limit(1).one()
        if 'name' in thermostat_dto.loaded_fields:
            thermostat.name = thermostat_dto.name
        if 'thermostat_group' in thermostat_dto.loaded_fields:
            thermostat.group = self._db.query(ThermostatGroup) \
                .filter_by(number=thermostat_dto.thermostat_group) \
                .one()
        if 'room' in thermostat_dto.loaded_fields:
            if thermostat_dto.room in (255, None):
                thermostat.room = None
            else:
                thermostat.room = self._db.query(Room).filter_by(number=thermostat_dto.room).one()
        if 'sensor' in thermostat_dto.loaded_fields:
            if thermostat_dto.sensor in (255, None):
                thermostat.sensor = None  # type: ignore
            else:
                thermostat.sensor = self._db.get(Sensor, thermostat_dto.sensor)
        if thermostat.sensor and thermostat.sensor.physical_quantity != Sensor.PhysicalQuantities.TEMPERATURE:
            raise ValueError('Invalid <Sensor {}> {} for thermostats'.format(thermostat.sensor.id, thermostat.sensor.physical_quantity))
        return thermostat

    def get_valve_links(self, thermostat_dto, mode):  # type: (ThermostatDTO, str) -> Tuple[List[IndoorLinkValves], List[IndoorLinkValves]]
        # in the return tuple, the first List contains updated IndoorLinkValves and the second List contains removed IndoorLinkValves
        thermostat = self._db.query(Thermostat) \
            .where(Thermostat.number == thermostat_dto.id) \
            .one()  # type: Thermostat

        outputs = {x.number: x for x in self._db.query(Output).join(Valve, isouter=True)}  # type: Dict[int,Output]
        valve_associations = iter(getattr(thermostat, '{0}_valve_associations'.format(mode))) # type: Iterator[IndoorLinkValves]

        links = []
        for field, priority in [('output0', 0),
                                ('output1', 1)]:
            if field in thermostat_dto.loaded_fields:
                if getattr(thermostat_dto, field) not in (255, None):
                    output = outputs[getattr(thermostat_dto, field)]
                    valve = output.valve
                    if valve is None:
                        valve = Valve(output=output, name='Valve (output {0})'.format(output.number))
                    association = next(valve_associations, None)
                    if association is None:
                        links.append(IndoorLinkValves(
                            thermostat_link_id=thermostat.id,
                            valve=valve,
                            mode=mode,
                        ))
                    else:
                        # if association.valve_id != valve.id or association.priority != priority: (this is the old if)
                        if association.valve_id != valve.id:
                            association.valve = valve
                            links.append(association)
        return links, list(valve_associations)

    def get_schedule_links(self, thermostat_dto, mode):  # type: (ThermostatDTO, str) -> Tuple[List[DaySchedule],List[DaySchedule]]
        thermostat = self._db.query(Thermostat) \
            .join(DaySchedule, isouter=True) \
            .where(Thermostat.number == thermostat_dto.id) \
            .one()  # type: Thermostat
        day_schedules = {x.index: x for x in thermostat.schedules if x.mode == mode}

        links = []
        for field, day_index in [('auto_mon', 0),
                                 ('auto_tue', 1),
                                 ('auto_wed', 2),
                                 ('auto_thu', 3),
                                 ('auto_fri', 4),
                                 ('auto_sat', 5),
                                 ('auto_sun', 6)]:
            if field in thermostat_dto.loaded_fields:
                schedule_dto = getattr(thermostat_dto, field)
                day_schedule = day_schedules.pop(day_index, None)
                if day_schedule is None:
                    day_schedule = DaySchedule(thermostat=thermostat, mode=mode, content='{}')
                if schedule_dto:
                    data = ThermostatScheduleMapper.dto_to_schedule(schedule_dto)
                else:
                    data = DaySchedule.DEFAULT_SCHEDULE[mode]
                if day_schedule.index != day_index or day_schedule.schedule_data != data:
                    day_schedule.index = day_index
                    day_schedule.schedule_data = data
                    links.append(day_schedule)
        return links, []

    def get_preset_links(self, thermostat_dto, mode):  # type: (ThermostatDTO, str) -> Tuple[List[Preset], List[Preset]]
        thermostat = self._db.query(Thermostat) \
            .join(Preset, isouter=True) \
            .where(Thermostat.number == thermostat_dto.id) \
            .one()  # type: Thermostat
        if not thermostat.presets:
            thermostat.presets = [
                Preset(type=Preset.Types.AUTO, heating_setpoint=14.0, cooling_setpoint=30.0)  # type: ignore
            ]
        if thermostat.active_preset is None:
            thermostat.presets[0].active = True
        presets = {preset.type: preset for preset in thermostat.presets}

        links = []
        for field, preset_type in [('setp3', Preset.Types.AWAY),
                                   ('setp4', Preset.Types.VACATION),
                                   ('setp5', Preset.Types.PARTY)]:
            if field in thermostat_dto.loaded_fields:
                setpoint = getattr(thermostat_dto, field)
                preset = presets.pop(preset_type, None)
                if preset is None:
                    preset = Preset(type=preset_type, active=False, thermostat=thermostat)
                    preset.heating_setpoint = Preset.DEFAULT_PRESETS[ThermostatGroup.Modes.HEATING].get(preset_type, 14.0)  # type: ignore
                    preset.cooling_setpoint = Preset.DEFAULT_PRESETS[ThermostatGroup.Modes.COOLING].get(preset_type, 30.0)  # type: ignore
                setpoint_field = '{0}_setpoint'.format(mode)
                if getattr(preset, setpoint_field) != setpoint:
                    setattr(preset, setpoint_field, setpoint)
                    links.append(preset)
        return links, []

    @staticmethod
    def get_default_dto(thermostat_id, mode):  # type: (int, Literal['cooling', 'heating']) -> ThermostatDTO
        dto = ThermostatDTO(id=thermostat_id)

        # Presets
        dto.setp3 = Preset.DEFAULT_PRESETS[mode][Preset.Types.AWAY]
        dto.setp4 = Preset.DEFAULT_PRESETS[mode][Preset.Types.VACATION]
        dto.setp5 = Preset.DEFAULT_PRESETS[mode][Preset.Types.PARTY]

        # Schedules
        for day_index, key in [(0, 'auto_mon'),
                               (1, 'auto_tue'),
                               (2, 'auto_wed'),
                               (3, 'auto_thu'),
                               (4, 'auto_fri'),
                               (5, 'auto_sat'),
                               (6, 'auto_sun')]:
            setattr(dto, key, ThermostatScheduleMapper.schedule_to_dto({}, mode=mode))

        return dto


class ThermostatScheduleMapper(object):
    @staticmethod
    def schedule_to_dto(schedule, mode):  # type: (Dict[int,float], Literal['cooling','heating']) -> Optional[ThermostatScheduleDTO]
        if not schedule:
            schedule = DaySchedule.DEFAULT_SCHEDULE[mode]

        amount_of_entries = len(schedule)
        if amount_of_entries < 5:
            logger.warning('Not enough data to map day schedule, returning default')
            return ThermostatScheduleMapper.schedule_to_dto(DaySchedule.DEFAULT_SCHEDULE[mode], mode)

        default_schedule = DaySchedule.DEFAULT_SCHEDULE[mode]
        # Parsing day/night, assuming following (classic) schedule:
        #      ______     ______
        #      |    |     |    |
        # _____|    |_____|    |_____
        # ^    ^    ^     ^    ^
        # So to parse a classic format out of it, at least 5 of the markers are required
        setpoints = list(sorted((int(k), v) for k, v in schedule.items()))
        temps_night = set(setpoints[i][1] for i  in (0, 2, 4) if i < len(setpoints))
        if len(temps_night) > 1:
            logger.warning('Unsupported day schedule, contains multiple temp_night values: %s', temps_night)
            return ThermostatScheduleMapper.schedule_to_dto(DaySchedule.DEFAULT_SCHEDULE[mode], mode)

        kwargs = {}  # type: Dict[str, Any]
        for index, (timestamp, temperature) in enumerate(setpoints):
            if index == 0:
                kwargs['temp_night'] = temperature
            elif index == 1:
                kwargs['temp_day_1'] = temperature
                kwargs['start_day_1'] = '{0:02d}:{1:02d}'.format(timestamp // 3600, (timestamp % 3600) // 60)
            elif index == 2:
                kwargs['end_day_1'] = '{0:02d}:{1:02d}'.format(timestamp // 3600, (timestamp % 3600) // 60)
            elif index == 3:
                kwargs['temp_day_2'] = temperature
                kwargs['start_day_2'] = '{0:02d}:{1:02d}'.format(timestamp // 3600, (timestamp % 3600) // 60)
            elif index == 4:
                kwargs['end_day_2'] = '{0:02d}:{1:02d}'.format(timestamp // 3600, (timestamp % 3600) // 60)
        return ThermostatScheduleDTO(**kwargs)

    @staticmethod
    def dto_to_schedule(schedule_dto):  # type: (ThermostatScheduleDTO) -> Dict[int, float]
        start_night = 0
        night_end = int(datetime.timedelta(hours=24, minutes=0, seconds=0).total_seconds())

        def get_seconds(hour_timestamp):
            # type: (str) -> int
            if hour_timestamp == '24:00':
                return night_end
            else:
                t = time.strptime(hour_timestamp, '%H:%M')
                return int(datetime.timedelta(hours=t.tm_hour, minutes=t.tm_min, seconds=t.tm_sec).total_seconds())

        start_day_1 = get_seconds(schedule_dto.start_day_1)
        end_day_1 = get_seconds(schedule_dto.end_day_1)
        start_day_2 = get_seconds(schedule_dto.start_day_2)
        end_day_2 = get_seconds(schedule_dto.end_day_2)

        # Attempt to resolve overlapping transitions in the schedule
        offset = 600
        if start_day_1 <= start_night:
            start_day_1 = start_night + offset
        if end_day_1 <= start_day_1:
            end_day_1 = start_day_1 + offset
        if start_day_2 <= end_day_1:
            start_day_2 = end_day_1 + offset
        if end_day_2 <= start_day_2:
            end_day_2 = start_day_2 + offset
        if end_day_2 >= night_end:
            end_day_2 = night_end - offset
        if start_day_2 >= end_day_2:
            start_day_2 = end_day_2 - offset
        if end_day_1 >= start_day_2:
            end_day_1 = start_day_2 - offset
        if start_day_1 >= end_day_1:
            start_day_1 = end_day_1 - offset
        if start_day_1 <= start_night:
            raise ValueError('Invalid schedule')

        return {start_night: schedule_dto.temp_night,
                start_day_1: schedule_dto.temp_day_1,
                end_day_1: schedule_dto.temp_night,
                start_day_2: schedule_dto.temp_day_2,
                end_day_2: schedule_dto.temp_night}
