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
Heating thermostat (de)serializer
"""
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import ThermostatDTO, ThermostatScheduleDTO, \
    ThermostatGroupStatusDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple, Any


class ThermostatSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(thermostat_dto, fields):  # type: (ThermostatDTO, Optional[List[str]]) -> Dict
        data = {'id': thermostat_dto.id,
                'name': thermostat_dto.name,
                'room': Toolbox.denonify(thermostat_dto.room, ThermostatSerializer.BYTE_MAX),
                'setp0': thermostat_dto.setp0,
                'setp1': thermostat_dto.setp1,
                'setp2': thermostat_dto.setp2,
                'setp3': thermostat_dto.setp3,
                'setp4': thermostat_dto.setp4,
                'setp5': thermostat_dto.setp5,
                'sensor': Toolbox.denonify(thermostat_dto.sensor, ThermostatSerializer.BYTE_MAX),
                'output0': Toolbox.denonify(thermostat_dto.output0, ThermostatSerializer.BYTE_MAX),
                'output1': Toolbox.denonify(thermostat_dto.output1, ThermostatSerializer.BYTE_MAX),
                'pid_p': Toolbox.denonify(thermostat_dto.pid_p, ThermostatSerializer.BYTE_MAX),
                'pid_i': Toolbox.denonify(thermostat_dto.pid_i, ThermostatSerializer.BYTE_MAX),
                'pid_d': Toolbox.denonify(thermostat_dto.pid_d, ThermostatSerializer.BYTE_MAX),
                'pid_int': Toolbox.denonify(thermostat_dto.pid_int, ThermostatSerializer.BYTE_MAX),
                'permanent_manual': thermostat_dto.permanent_manual}
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            field = 'auto_{0}'.format(day)
            dto_data = getattr(thermostat_dto, field)  # type: ThermostatScheduleDTO
            if dto_data is None:
                continue
            data[field] = [dto_data.temp_night,
                           dto_data.start_day_1,
                           dto_data.end_day_1,
                           dto_data.temp_day_1,
                           dto_data.start_day_2,
                           dto_data.end_day_2,
                           dto_data.temp_day_2]
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> Tuple[ThermostatDTO, List[str]]
        loaded_fields = ['id']
        heating_thermostat_dto = ThermostatDTO(api_data['id'])
        loaded_fields += SerializerToolbox.deserialize(
            dto=heating_thermostat_dto,  # Referenced
            api_data=api_data,
            mapping={'name': ('name', None),
                     'permanent_manual': ('permanent_manual', None),
                     'setp0': ('setp0', None),
                     'setp1': ('setp1', None),
                     'setp2': ('setp2', None),
                     'setp3': ('setp3', None),
                     'setp4': ('setp4', None),
                     'setp5': ('setp5', None),
                     'room': ('room', ThermostatSerializer.BYTE_MAX),
                     'sensor': ('sensor', ThermostatSerializer.BYTE_MAX),
                     'output0': ('output0', ThermostatSerializer.BYTE_MAX),
                     'output1': ('output1', ThermostatSerializer.BYTE_MAX),
                     'pid_p': ('pid_p', ThermostatSerializer.BYTE_MAX),
                     'pid_i': ('pid_i', ThermostatSerializer.BYTE_MAX),
                     'pid_d': ('pid_d', ThermostatSerializer.BYTE_MAX),
                     'pid_int': ('pid_int', ThermostatSerializer.BYTE_MAX)}
        )
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            field = 'auto_{0}'.format(day)
            if field not in api_data:
                continue
            loaded_fields.append(field)
            field_dto = ThermostatScheduleDTO(temp_night=api_data[field][0],
                                              start_day_1=api_data[field][1],
                                              end_day_1=api_data[field][2],
                                              temp_day_1=api_data[field][3],
                                              start_day_2=api_data[field][4],
                                              end_day_2=api_data[field][5],
                                              temp_day_2=api_data[field][6])
            setattr(heating_thermostat_dto, field, field_dto)
        return heating_thermostat_dto, loaded_fields


class ThermostatGroupStatusSerializer(object):
    @staticmethod
    def serialize(thermostat_group_status_dto):  # type: (ThermostatGroupStatusDTO) -> Dict[str, Any]
        return {'thermostats_on': thermostat_group_status_dto.on,
                'automatic': thermostat_group_status_dto.automatic,
                'setpoint': thermostat_group_status_dto.setpoint,
                'cooling': thermostat_group_status_dto.cooling,
                'status': [{'id': status.id,
                            'act': status.actual_temperature,
                            'csetp': status.setpoint_temperature,
                            'outside': status.outside_temperature,
                            'mode': status.mode,
                            'automatic': status.automatic,
                            'setpoint': status.setpoint,
                            'name': status.name,
                            'sensor_nr': status.sensor_id,
                            'airco': status.airco,
                            'output0': status.output_0_level,
                            'output1': status.output_1_level}
                           for status in thermostat_group_status_dto.statusses]}
