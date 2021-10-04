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
import logging
import time
import datetime
from peewee import DoesNotExist
from gateway.dto import ThermostatDTO, ThermostatScheduleDTO
from gateway.models import Thermostat, DaySchedule, ValveToThermostat, \
    Output, Valve, Preset, Sensor, Room, ThermostatGroup

if False:  # MYPY
    from typing import List, Optional, Dict, Any, Literal

logger = logging.getLogger(__name__)


class ThermostatMapper(object):
    @staticmethod
    def orm_to_dto(orm_object, mode):  # type: (Thermostat, Literal['cooling', 'heating']) -> ThermostatDTO
        sensor_id = None if orm_object.sensor is None else orm_object.sensor.id
        dto = ThermostatDTO(id=orm_object.number,
                            name=orm_object.name,
                            sensor=sensor_id,
                            pid_p=getattr(orm_object, 'pid_{0}_p'.format(mode)),
                            pid_i=getattr(orm_object, 'pid_{0}_i'.format(mode)),
                            pid_d=getattr(orm_object, 'pid_{0}_d'.format(mode)),
                            permanent_manual=orm_object.automatic,
                            room=orm_object.room.number if orm_object.room is not None else None,
                            thermostat_group=orm_object.thermostat_group.number)

        # Outputs
        db_outputs = [valve.output.number for valve in getattr(orm_object, '{0}_valves'.format(mode))]
        number_of_outputs = len(db_outputs)
        if number_of_outputs > 0:
            dto.output0 = db_outputs[0]
        if number_of_outputs > 1:
            dto.output1 = db_outputs[1]
        if number_of_outputs > 2:
            logger.warning('Only 2 outputs are supported in the old format. Total: {0} outputs.'.format(number_of_outputs))

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
        start_day_of_week = (orm_object.start / 86400 - 4) % 7  # 0: Monday, 1: Tuesday, ...
        for day_index, key in [(0, 'auto_mon'),
                               (1, 'auto_tue'),
                               (2, 'auto_wed'),
                               (3, 'auto_thu'),
                               (4, 'auto_fri'),
                               (5, 'auto_sat'),
                               (6, 'auto_sun')]:
            index = int((7 - start_day_of_week + day_index) % 7)
            schedule = day_schedules[index].schedule_data if index in day_schedules else {}
            setattr(dto, key, ThermostatMapper._schedule_to_dto(schedule, mode))

        # TODO: Map missing [pid_int, setp0, setp1, setp2]
        return dto

    @staticmethod
    def _schedule_to_dto(schedule, mode, log_warnings=True):  # type: (Dict[str,Any], Literal['cooling', 'heating'], bool) -> Optional[ThermostatScheduleDTO]
        amount_of_entries = len(schedule)
        if amount_of_entries == 0:
            if log_warnings:
                logger.warning('Mapping an empty temperature day schedule.')
            schedule = DaySchedule.DEFAULT_SCHEDULE[mode]
        elif amount_of_entries < 5:
            if log_warnings:
                logger.warning('Not enough data to map day schedule. Returning best effort data.')
            schedule = DaySchedule.DEFAULT_SCHEDULE[mode]

        # Parsing day/night, assuming following (classic) schedule:
        #      ______     ______
        #      |    |     |    |
        # _____|    |_____|    |_____
        # ^    ^    ^     ^    ^
        # So to parse a classic format out of it, at least 5 of the markers are required
        index = 0
        kwargs = {}  # type: Dict[str, Any]
        for timestamp in sorted(schedule.keys(), key=lambda t: int(t)):
            temperature = schedule[timestamp]
            timestamp_int = int(timestamp)
            if index == 0:
                kwargs['temp_night'] = temperature
            elif index == 1:
                kwargs['temp_day_1'] = temperature
                kwargs['start_day_1'] = '{0:02d}:{1:02d}'.format(timestamp_int // 3600, (timestamp_int % 3600) // 60)
            elif index == 2:
                kwargs['end_day_1'] = '{0:02d}:{1:02d}'.format(timestamp_int // 3600, (timestamp_int % 3600) // 60)
            elif index == 3:
                kwargs['temp_day_2'] = temperature
                kwargs['start_day_2'] = '{0:02d}:{1:02d}'.format(timestamp_int // 3600, (timestamp_int % 3600) // 60)
            elif index == 4:
                kwargs['end_day_2'] = '{0:02d}:{1:02d}'.format(timestamp_int // 3600, (timestamp_int % 3600) // 60)
            index += 1
        return ThermostatScheduleDTO(**kwargs)

    @staticmethod
    def dto_to_orm(thermostat_dto, mode):  # type: (ThermostatDTO, Literal['cooling', 'heating']) -> Thermostat
        # TODO: A mapper should not alter the database, but instead give an in-memory
        #       structure back to the caller to process

        objects = {}  # type: Dict[str, Dict[int, Any]]

        def _load_sensor(pk):
            if pk is None:
                return
            else:
                sensor = Sensor.get(id=pk)
                if sensor and sensor.physical_quantity != Sensor.PhysicalQuantities.TEMPERATURE:
                    raise ValueError('Invalid <Sensor {}> {} for thermostats'.format(sensor.id, sensor.physical_quantity))
                return sensor

        def _load_object(orm_type, number):
            if number is None:
                return None
            return objects.setdefault(orm_type.__name__, {}).setdefault(number, orm_type.get(number=number))

        # We don't get a start date, calculate last monday night to map the schedules
        now = int(time.time())
        day_of_week = (now / 86400 - 4) % 7  # 0: Monday, 1: Tuesday, ...
        last_monday_night = now - now % 86400 - day_of_week * 86400

        # Update/save thermostat configuration
        try:
            thermostat = Thermostat.get(number=thermostat_dto.id)
        except Thermostat.DoesNotExist:
            thermostat_group = ThermostatGroup.get(number=0)
            thermostat = Thermostat(number=thermostat_dto.id)
            thermostat.thermostat_group = thermostat_group
        for orm_field, (dto_field, mapping) in {'name': ('name', None),
                                                'sensor': ('sensor', _load_sensor),
                                                'room': ('room', lambda n: _load_object(Room, n)),
                                                'thermostat_group': ('thermostat_group', lambda n: _load_object(ThermostatGroup, n)),
                                                'pid_{0}_p'.format(mode): ('pid_p', float),
                                                'pid_{0}_i'.format(mode): ('pid_i', float),
                                                'pid_{0}_d'.format(mode): ('pid_d', float)}.items():
            if dto_field not in thermostat_dto.loaded_fields:
                continue
            value = getattr(thermostat_dto, dto_field)
            if mapping is not None:
                value = mapping(value)
            setattr(thermostat, orm_field, value)

        thermostat.start = last_monday_night
        thermostat.save()

        # Update/save output configuration
        output_config_present = 'output0' in thermostat_dto.loaded_fields or 'output1' in thermostat_dto.loaded_fields
        if output_config_present:
            # Unlink all previously linked valve_ids, we are resetting this with the new outputs we got from the API
            deleted = ValveToThermostat \
                .delete() \
                .where(ValveToThermostat.thermostat == thermostat) \
                .where(ValveToThermostat.mode == mode) \
                .execute()
            logger.info('Unlinked {0} valve_ids from thermostat {1}'.format(deleted, thermostat.name))

            for field in ['output0', 'output1']:
                dto_data = getattr(thermostat_dto, field)
                if dto_data is None:
                    continue

                # 1. Get or create output, creation also saves to db
                output_number = int(dto_data)
                output, output_created = Output.get_or_create(number=output_number)

                # 2. Get or create the valve and link to this output
                try:
                    valve = Valve.get(output=output)
                except DoesNotExist:
                    valve = Valve(output=output)
                valve.name = 'Valve (output {0})'.format(output_number)
                valve.save()

                # 3. Link the valve to the thermostat, set properties
                try:
                    valve_to_thermostat = ValveToThermostat.get(valve=valve, thermostat=thermostat, mode=mode)
                except DoesNotExist:
                    valve_to_thermostat = ValveToThermostat(valve=valve, thermostat=thermostat, mode=mode)

                # TODO: Decide if this is a cooling thermostat or heating thermostat
                valve_to_thermostat.priority = 0 if field == 'output0' else 1
                valve_to_thermostat.save()

        # Update/save scheduling configuration
        day_schedules = {schedule.index: schedule for schedule in
                         DaySchedule.select().where((DaySchedule.thermostat == thermostat) &
                                                    (DaySchedule.mode == mode))}
        for day_index, key in [(0, 'auto_mon'),
                               (1, 'auto_tue'),
                               (2, 'auto_wed'),
                               (3, 'auto_thu'),
                               (4, 'auto_fri'),
                               (5, 'auto_sat'),
                               (6, 'auto_sun')]:
            if day_index in day_schedules:
                day_schedule = day_schedules[day_index]
            else:
                # Default schedules
                day_schedule = DaySchedule(thermostat=thermostat, index=day_index, mode=mode)
                day_schedule.schedule_data = DaySchedule.DEFAULT_SCHEDULE[mode]
            if key in thermostat_dto.loaded_fields:
                dto_data = getattr(thermostat_dto, key)
                day_schedule.schedule_data = ThermostatMapper._schedule_dto_to_orm(dto_data, mode)
            day_schedule.save()

        # Presets
        presets = {preset.type: preset for preset in
                   Preset.select().where((Preset.thermostat == thermostat))}
        for field, preset_type in [('setp3', Preset.Types.AWAY),
                                   ('setp4', Preset.Types.VACATION),
                                   ('setp5', Preset.Types.PARTY)]:
            if field not in thermostat_dto.loaded_fields:
                continue
            if preset_type not in presets:
                # Create default presets
                preset = Preset(type=preset_type, thermostat=thermostat)
                if preset_type in Preset.DEFAULT_PRESET_TYPES:
                    preset.heating_setpoint = Preset.DEFAULT_PRESETS[ThermostatGroup.Modes.HEATING][preset_type]
                    preset.cooling_setpoint = Preset.DEFAULT_PRESETS[ThermostatGroup.Modes.COOLING][preset_type]
                preset.active = False
                if preset_type == Preset.Types.AUTO:
                    preset.active = True
                preset.save()
            else:
                preset = presets[preset_type]
            dto_data = getattr(thermostat_dto, field)
            try:
                preset_value = float(dto_data)
            except (ValueError, TypeError):
                continue
            setattr(preset, '{0}_setpoint'.format(mode), preset_value)
            preset.active = False
            preset.save()

        # TODO: Map missing [permanent_manual, setp0, setp1, setp2, pid_int]
        return thermostat

    @staticmethod
    def _schedule_dto_to_orm(schedule_dto, mode):  # type: (ThermostatScheduleDTO, Literal['cooling', 'heating']) -> Dict[int, float]
        def get_seconds(hour_timestamp):
            # type: (str) -> Optional[int]
            try:
                x = time.strptime(hour_timestamp, '%H:%M')
                return int(datetime.timedelta(hours=x.tm_hour, minutes=x.tm_min, seconds=x.tm_sec).total_seconds())
            except Exception:
                return None

        temperatures = [schedule_dto.temp_night, schedule_dto.temp_day_1, schedule_dto.temp_day_2]
        times = [0,
                 get_seconds(schedule_dto.start_day_1),
                 get_seconds(schedule_dto.end_day_1),
                 get_seconds(schedule_dto.start_day_2),
                 get_seconds(schedule_dto.end_day_2)]

        if None in temperatures or None in times:
            # Some partial data and/or parsing errors, fallback to defaults
            return DaySchedule.DEFAULT_SCHEDULE[mode]

        # Added `ignore` type annotation below, since mypy couldn't figure out we checked for None above
        return {times[0]: temperatures[0],  # type: ignore
                times[1]: temperatures[1],  # type: ignore
                times[2]: temperatures[0],  # type: ignore
                times[3]: temperatures[2],  # type: ignore
                times[4]: temperatures[0]}  # type: ignore

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
            setattr(dto, key, ThermostatMapper._schedule_to_dto({}, mode=mode, log_warnings=False))

        return dto
