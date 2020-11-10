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
RTD10 Mapper
"""
from toolbox import Toolbox
from gateway.dto import GlobalRTD10DTO, RTD10DTO
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import GlobalRTD10Configuration

if False:  # MYPY
    from typing import List, Type


class GlobalRTD10Mapper(object):
    @staticmethod
    def _temp_to_str(temp):
        return str(temp).replace('.', '_')

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> GlobalRTD10DTO
        data = orm_object.serialize()
        heating_values = {}
        cooling_values = {}
        for temperature in GlobalRTD10DTO.TEMPERATURES:
            field = 'output_value_heating_{0}'.format(GlobalRTD10Mapper._temp_to_str(temperature))
            heating_values[temperature] = data[field]
            field = 'output_value_cooling_{0}'.format(GlobalRTD10Mapper._temp_to_str(temperature))
            cooling_values[temperature] = data[field]
        return GlobalRTD10DTO(heating_values=heating_values,
                              cooling_values=cooling_values)

    @staticmethod
    def dto_to_orm(global_rtd10_dto, fields):  # type: (GlobalRTD10DTO, List[str]) -> EepromModel
        data = {}
        for temperature in GlobalRTD10DTO.TEMPERATURES:
            field = 'output_value_heating_{0}'.format(GlobalRTD10Mapper._temp_to_str(temperature))
            if field in fields:
                data[field] = global_rtd10_dto.heating_values[temperature]
            field = 'output_value_cooling_{0}'.format(GlobalRTD10Mapper._temp_to_str(temperature))
            if field in fields:
                data[field] = global_rtd10_dto.cooling_values[temperature]
        return GlobalRTD10Configuration.deserialize(data)


class RTD10Mapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> RTD10DTO
        data = orm_object.serialize()
        kwargs = {}
        for field in ['temp_setpoint_output', 'ventilation_speed_output', 'ventilation_speed_value',
                      'mode_output', 'mode_value', 'on_off_output', 'poke_angle_output',
                      'poke_angle_value', 'room']:
            kwargs[field] = Toolbox.nonify(data[field], RTD10Mapper.BYTE_MAX)
        return RTD10DTO(id=data['id'], **kwargs)

    @staticmethod
    def dto_to_orm(model_type, rtd10_dto, fields):  # type: (Type[EepromModel], RTD10DTO, List[str]) -> EepromModel
        data = {'id': rtd10_dto.id}
        for field in ['temp_setpoint_output', 'ventilation_speed_output', 'ventilation_speed_value',
                      'mode_output', 'mode_value', 'on_off_output', 'poke_angle_output',
                      'poke_angle_value', 'room']:
            if field in fields:
                data[field] = Toolbox.denonify(getattr(rtd10_dto, field), RTD10Mapper.BYTE_MAX)
        return model_type.deserialize(data)
