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
from gateway.dto import ThermostatAircoStatusDTO, ThermostatDTO, \
    ThermostatGroupDTO, ThermostatScheduleDTO, ThermostatGroupStatusDTO, \
    PumpGroupDTO

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
                # TODO: Remove once UI can handle "no schedule"
                dto_data = ThermostatScheduleDTO(temp_night=16, temp_day_1=20, temp_day_2=20,
                                                 start_day_1="07:00", end_day_1="09:00",
                                                 start_day_2="16:00", end_day_2="22:00")
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
        thermostat_dto = ThermostatDTO(api_data['id'])
        loaded_fields += SerializerToolbox.deserialize(
            dto=thermostat_dto,  # Referenced
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
            setattr(thermostat_dto, field, field_dto)
        return thermostat_dto, loaded_fields


class ThermostatGroupSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(thermostat_group_dto, fields):  # type: (ThermostatGroupDTO, Optional[List[str]]) -> Dict
        data = {'id': thermostat_group_dto.id,
                'outside_sensor': Toolbox.denonify(thermostat_group_dto.outside_sensor_id, ThermostatGroupSerializer.BYTE_MAX),
                'threshold_temperature': Toolbox.denonify(thermostat_group_dto.threshold_temperature, ThermostatGroupSerializer.BYTE_MAX),
                'pump_delay': Toolbox.denonify(thermostat_group_dto.pump_delay, ThermostatGroupSerializer.BYTE_MAX)}
        for mode in ['heating', 'cooling']:
            for i in range(4):
                output = 'switch_to_{0}_output_{1}'.format(mode, i)
                value = 'switch_to_{0}_value_{1}'.format(mode, i)
                field = 'switch_to_{0}_{1}'.format(mode, i)
                dto_value = getattr(thermostat_group_dto, field)  # type: Optional[Tuple[int, int]]
                data[output] = Toolbox.denonify(None if dto_value is None else dto_value[0], ThermostatGroupSerializer.BYTE_MAX)
                data[value] = Toolbox.denonify(None if dto_value is None else dto_value[1], ThermostatGroupSerializer.BYTE_MAX)
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> Tuple[ThermostatGroupDTO, List[str]]
        loaded_fields = []
        thermostat_group_dto = ThermostatGroupDTO(id=0)
        loaded_fields += SerializerToolbox.deserialize(
            dto=thermostat_group_dto,  # Referenced
            api_data=api_data,
            mapping={'outside_sensor': ('outside_sensor_id', ThermostatGroupSerializer.BYTE_MAX),
                     'threshold_temperature': ('threshold_temperature', ThermostatGroupSerializer.BYTE_MAX),
                     'pump_delay': ('pump_delay', ThermostatGroupSerializer.BYTE_MAX)}
        )
        for mode in ['heating', 'cooling']:
            for i in range(4):
                output_field = 'switch_to_{0}_output_{1}'.format(mode, i)
                value_field = 'switch_to_{0}_value_{1}'.format(mode, i)
                dto_field = 'switch_to_{0}_{1}'.format(mode, i)
                if output_field in api_data and value_field in api_data:
                    loaded_fields.append(dto_field)
                    output = Toolbox.nonify(api_data[output_field], ThermostatGroupSerializer.BYTE_MAX)
                    value = api_data[value_field]
                    if output is None:
                        setattr(thermostat_group_dto, dto_field, None)
                    else:
                        setattr(thermostat_group_dto, dto_field, [output, value])
        return thermostat_group_dto, loaded_fields


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


class ThermostatAircoStatusSerializer(object):
    @staticmethod
    def serialize(thermostat_airco_status_dto):  # type: (ThermostatAircoStatusDTO) -> Dict[str, Any]
        return {'ASB{0}'.format(i): 1 if thermostat_airco_status_dto.status[i] else 0
                for i in range(32)}


class PumpGroupSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(pump_group_dto, fields):  # type: (PumpGroupDTO, Optional[List[str]]) -> Dict
        data = {'id': pump_group_dto.id,
                'output': Toolbox.denonify(pump_group_dto.pump_output_id, PumpGroupSerializer.BYTE_MAX),
                'outputs': ','.join(str(output_id) for output_id in pump_group_dto.valve_output_ids),
                'room': Toolbox.denonify(pump_group_dto.room_id, PumpGroupSerializer.BYTE_MAX)}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> Tuple[PumpGroupDTO, List[str]]
        loaded_fields = []
        pump_group_dto = PumpGroupDTO(id=0)
        loaded_fields += SerializerToolbox.deserialize(
            dto=pump_group_dto,  # Referenced
            api_data=api_data,
            mapping={'output': ('pump_output_id', PumpGroupSerializer.BYTE_MAX),
                     'rooom': ('room_id', PumpGroupSerializer.BYTE_MAX)}
        )
        if 'outputs' in api_data:
            loaded_fields.append('valve_output_ids')
            pump_group_dto.valve_output_ids = [int(output_id) for output_id in api_data['outputs'].split(',')]
        return pump_group_dto, loaded_fields
