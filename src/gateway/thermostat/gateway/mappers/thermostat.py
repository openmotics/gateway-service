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
from models import Thermostat, DaySchedule, ValveToThermostat, Output, Valve, Preset

if False:  # MYPY
    from typing import List, Optional, Dict

logger = logging.getLogger("openmotics")


class ThermostatMapper(object):

    @staticmethod
    def orm_to_dto(orm_object, mode):  # type: (Thermostat, str) -> ThermostatDTO
        dto = ThermostatDTO(id=orm_object.number,
                            name=orm_object.name,
                            sensor=orm_object.sensor,
                            pid_p=getattr(orm_object, 'pid_{0}_p'.format(mode)),
                            pid_i=getattr(orm_object, 'pid_{0}_i'.format(mode)),
                            pid_d=getattr(orm_object, 'pid_{0}_d'.format(mode)),
                            permanent_manual=orm_object.automatic,
                            room=orm_object.room)

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
        for preset in orm_object.presets:
            setpoint = getattr(preset, '{0}_setpoint'.format(mode))
            if preset.name == 'AWAY':
                dto.setp3 = setpoint
            elif preset.name == 'VACATION':
                dto.setp4 = setpoint
            elif preset.name == 'PARTY':
                dto.setp5 = setpoint

        # Schedules
        day_schedules = sorted(getattr(orm_object, '{0}_schedules'.format(mode))(),
                               key=lambda s: s.index,
                               reverse=False)
        start_day_of_week = (orm_object.start / 86400 - 4) % 7  # 0: Monday, 1: Tuesday, ...
        for day_index, key in [(0, 'auto_mon'),
                               (1, 'auto_tue'),
                               (2, 'auto_wed'),
                               (3, 'auto_thu'),
                               (4, 'auto_fri'),
                               (5, 'auto_sat'),
                               (6, 'auto_sun')]:
            index = int((7 - start_day_of_week + day_index) % 7)
            setattr(dto, key, ThermostatMapper._schedule_orm_to_dto(day_schedules[index]))

        # TODO: Map missing [pid_int, setp0, setp1, setp2]
        return dto

    @staticmethod
    def _schedule_orm_to_dto(schedule_orm):  # type: (DaySchedule) -> Optional[ThermostatScheduleDTO]
        schedule = schedule_orm.schedule_data
        amount_of_entries = len(schedule)
        if amount_of_entries == 0:
            logger.warning('Mapping an empty temperature day schedule.')
            return None
        if amount_of_entries < 5:
            logger.warning('Not enough data to map day schedule. Returning best effort data.')
            first_value = schedule.itervalues().next()
            return ThermostatScheduleDTO(temp_night=first_value,
                                         start_day_1='42:30',
                                         end_day_1='42:30',
                                         temp_day_1=first_value,
                                         start_day_2='42:30',
                                         end_day_2='42:30',
                                         temp_day_2=first_value)

        # Parsing day/night, assuming following (classic) schedule:
        #      ______     ______
        #      |    |     |    |
        # _____|    |_____|    |_____
        # ^    ^    ^     ^    ^
        # So to parse a classic format out of it, at least 5 of the markers are required
        index = 0
        kwargs = {}
        for timestamp in sorted(schedule.keys(), key=lambda t: int(t)):
            temperature = schedule[timestamp]
            timestamp = int(timestamp)
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
            index += 1
        return ThermostatScheduleDTO(**kwargs)

    @staticmethod
    def dto_to_orm(thermostat_dto, fields, mode):  # type: (ThermostatDTO, List[str], str) -> Thermostat
        # TODO: A mapper should not alter the database, but instead give an in-memory
        #       structure back to the caller to process

        # We don't get a start date, calculate last monday night to map the schedules
        now = int(time.time())
        day_of_week = (now / 86400 - 4) % 7  # 0: Monday, 1: Tuesday, ...
        last_monday_night = now - now % 86400 - day_of_week * 86400

        # Update/save thermostat configuration
        try:
            thermostat = Thermostat.get(number=thermostat_dto.id)
        except Thermostat.DoesNotExist:
            thermostat = Thermostat(number=thermostat_dto.id)
        for orm_field, (dto_field, mapping) in {'name': ('name', None),
                                                'sensor': ('sensor', int),
                                                'room': ('room', int),
                                                'pid_{0}_p'.format(mode): ('pid_p', float),
                                                'pid_{0}_i'.format(mode): ('pid_i', float),
                                                'pid_{0}_d'.format(mode): ('pid_d', float)}.items():
            if dto_field not in fields:
                continue
            value = getattr(thermostat_dto, dto_field)
            if mapping is not None:
                value = mapping(value)
            setattr(thermostat, orm_field, value)

        thermostat.start = last_monday_night
        thermostat.save()

        # Update/save output configuration
        output_config_present = 'output0' in fields or 'output1' in fields
        if output_config_present:
            # Unlink all previously linked valve_numbers, we are resetting this with the new outputs we got from the API
            deleted = ValveToThermostat \
                .delete() \
                .where(ValveToThermostat.thermostat == thermostat) \
                .where(ValveToThermostat.mode == mode) \
                .execute()
            logger.info('Unlinked {0} valve_numbers from thermostat {1}'.format(deleted, thermostat.name))

            for field in ['output0', 'output1']:
                dto_data = getattr(thermostat_dto, field)
                if dto_data is None:
                    continue

                # 1. Get or create output, creation also saves to db
                output_number = int(dto_data)
                output, output_created = Output.get_or_create(number=output_number)

                # 2. Get or create the valve and link to this output
                try:
                    valve = Valve.get(output=output, number=output_number)
                except DoesNotExist:
                    valve = Valve(output=output, number=output_number)
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
        for day_index, key in [(0, 'auto_mon'),
                               (1, 'auto_tue'),
                               (2, 'auto_wed'),
                               (3, 'auto_thu'),
                               (4, 'auto_fri'),
                               (5, 'auto_sat'),
                               (6, 'auto_sun')]:
            if key not in fields:
                continue
            dto_data = getattr(thermostat_dto, key)
            if dto_data is None:
                continue
            try:
                day_schedule = DaySchedule.get(thermostat=thermostat, index=day_index, mode=mode)
            except DoesNotExist:
                day_schedule = DaySchedule(thermostat=thermostat, index=day_index, mode=mode)
            day_schedule.schedule_data = ThermostatMapper._schedule_dto_to_orm(dto_data)
            day_schedule.save()

        # Presets
        for field, preset_name in [('setp3', 'AWAY'),
                                   ('setp4', 'VACATION'),
                                   ('setp5', 'PARTY')]:
            if field not in fields:
                continue
            dto_data = getattr(thermostat_dto, field)
            if dto_data is None:
                continue
            try:
                preset = Preset.get(name=preset_name, thermostat=thermostat)
            except DoesNotExist:
                preset = Preset(name=preset_name, thermostat=thermostat)
            setattr(preset, '{0}_setpoint'.format(mode), float(dto_data))
            preset.active = False
            preset.save()

        # TODO: Map missing [permanent_manual, setp0, setp1, setp2, pid_int]
        return thermostat

    @staticmethod
    def _schedule_dto_to_orm(schedule_dto):  # type: (ThermostatScheduleDTO) -> Dict[int, Optional[float]]
        def get_seconds(hour_timestamp):
            x = time.strptime(hour_timestamp, '%H:%M')
            return int(datetime.timedelta(hours=x.tm_hour, minutes=x.tm_min, seconds=x.tm_sec).total_seconds())

        return {0: schedule_dto.temp_night,
                get_seconds(schedule_dto.start_day_1): schedule_dto.temp_day_1,
                get_seconds(schedule_dto.end_day_1): schedule_dto.temp_night,
                get_seconds(schedule_dto.start_day_2): schedule_dto.temp_day_2,
                get_seconds(schedule_dto.end_day_2): schedule_dto.temp_night}
