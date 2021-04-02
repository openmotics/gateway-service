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
HeatingThermostat Mapper
"""
from toolbox import Toolbox
from gateway.dto import ThermostatDTO, ThermostatScheduleDTO, \
    ThermostatGroupDTO, PumpGroupDTO
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import ThermostatConfiguration, GlobalThermostatConfiguration

if False:  # MYPY
    from typing import List, Dict, Any, Optional, Tuple, Type


class ThermostatMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> ThermostatDTO
        data = orm_object.serialize()
        kwargs = {'name': data['name'],
                  'permanent_manual': data['permanent_manual']}
        for i in range(6):
            field = 'setp{0}'.format(i)
            kwargs[field] = data[field]
        for field in ['sensor', 'output0', 'output1', 'pid_p', 'pid_i', 'pid_d', 'pid_int', 'room']:
            kwargs[field] = Toolbox.nonify(data[field], ThermostatMapper.BYTE_MAX)
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            field = 'auto_{0}'.format(day)
            kwargs[field] = ThermostatScheduleDTO(temp_night=data[field][0],
                                                  start_day_1=data[field][1],
                                                  end_day_1=data[field][2],
                                                  temp_day_1=data[field][3],
                                                  start_day_2=data[field][4],
                                                  end_day_2=data[field][5],
                                                  temp_day_2=data[field][6])
        return ThermostatDTO(id=data['id'],
                             **kwargs)

    @staticmethod
    def dto_to_orm(model_type, thermostat_dto):  # type: (Type[EepromModel], ThermostatDTO) -> EepromModel
        data = {'id': thermostat_dto.id}  # type: Dict[str, Any]
        for field in ['name', 'permanent_manual'] + ['setp{0}'.format(i) for i in range(6)]:
            if field in thermostat_dto.loaded_fields:
                data[field] = getattr(thermostat_dto, field)
        for field in ['sensor', 'output0', 'output1', 'pid_p', 'pid_i', 'pid_d', 'pid_int', 'room']:
            if field in thermostat_dto.loaded_fields:
                data[field] = Toolbox.denonify(getattr(thermostat_dto, field), ThermostatMapper.BYTE_MAX)
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            field = 'auto_{0}'.format(day)
            if field not in thermostat_dto.loaded_fields:
                continue
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
        return model_type.deserialize(data)


class ThermostatGroupMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> ThermostatGroupDTO
        data = orm_object.serialize()
        kwargs = {}
        for dto_field, orm_field in {'outside_sensor_id': 'outside_sensor',
                                     'threshold_temperature': 'threshold_temp',
                                     'pump_delay': 'pump_delay'}.items():
            kwargs[dto_field] = Toolbox.nonify(data[orm_field], ThermostatGroupMapper.BYTE_MAX)
        for mode in ['heating', 'cooling']:
            for i in range(4):
                output_field = 'switch_to_{0}_output_{1}'.format(mode, i)
                value_field = 'switch_to_{0}_value_{1}'.format(mode, i)
                dto_field = 'switch_to_{0}_{1}'.format(mode, i)
                output = Toolbox.nonify(data[output_field], ThermostatGroupMapper.BYTE_MAX)
                value = Toolbox.nonify(data[value_field], ThermostatGroupMapper.BYTE_MAX)
                if output is not None:
                    kwargs[dto_field] = [output, value]
        return ThermostatGroupDTO(id=0, **kwargs)

    @staticmethod
    def dto_to_orm(thermostat_group_dto):  # type: (ThermostatGroupDTO) -> EepromModel
        data = {}  # type: Dict[str, Any]
        for dto_field, orm_field in {'outside_sensor_id': 'outside_sensor',
                                     'threshold_temperature': 'threshold_temp',
                                     'pump_delay': 'pump_delay'}.items():
            if dto_field in thermostat_group_dto.loaded_fields:
                data[orm_field] = Toolbox.denonify(getattr(thermostat_group_dto, dto_field), ThermostatGroupMapper.BYTE_MAX)
        for mode in ['heating', 'cooling']:
            for i in range(4):
                output = 'switch_to_{0}_output_{1}'.format(mode, i)
                value = 'switch_to_{0}_value_{1}'.format(mode, i)
                field = 'switch_to_{0}_{1}'.format(mode, i)
                if field in thermostat_group_dto.loaded_fields:
                    dto_value = getattr(thermostat_group_dto, field)  # type: Optional[Tuple[int, int]]
                    data[output] = Toolbox.denonify(None if dto_value is None else dto_value[0], ThermostatGroupMapper.BYTE_MAX)
                    data[value] = Toolbox.denonify(None if dto_value is None else dto_value[1], ThermostatGroupMapper.BYTE_MAX)
        return GlobalThermostatConfiguration.deserialize(data)


class PumpGroupMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> PumpGroupDTO
        data = orm_object.serialize()
        kwargs = {'pump_output_id': Toolbox.nonify(data['output'], PumpGroupMapper.BYTE_MAX),
                  'valve_output_ids': ([int(output_id) for output_id in data['outputs'].split(',')]
                                       if data['outputs'] != '' else []),
                  'room_id': Toolbox.nonify(data['room'], PumpGroupMapper.BYTE_MAX)}
        return PumpGroupDTO(id=data['id'], **kwargs)

    @staticmethod
    def dto_to_orm(model_type, pump_group_dto):  # type: (Type[EepromModel], PumpGroupDTO) -> EepromModel
        data = {'id': pump_group_dto.id}  # type: Dict[str, Any]
        if 'pump_output_id' in pump_group_dto.loaded_fields:
            data['output'] = Toolbox.denonify(pump_group_dto.pump_output_id, PumpGroupMapper.BYTE_MAX)
        if 'valve_output_ids' in pump_group_dto.loaded_fields:
            data['outputs'] = ','.join(str(output_id) for output_id in pump_group_dto.valve_output_ids)
        if 'room_id' in pump_group_dto.loaded_fields:
            data['room'] = Toolbox.denonify(pump_group_dto.room_id, PumpGroupMapper.BYTE_MAX)
        return model_type.deserialize(data)
