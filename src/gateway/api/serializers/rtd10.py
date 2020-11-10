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
RTD10 (de)serializer
"""
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import GlobalRTD10DTO, RTD10DTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple, Any


class GlobalRTD10Serializer(object):

    @staticmethod
    def _temp_to_str(temp):
        return str(temp).replace('.', '_')

    @staticmethod
    def serialize(global_rtd10_dto, fields):  # type: (GlobalRTD10DTO, Optional[List[str]]) -> Dict[str, Any]
        data = {}
        for temperature in GlobalRTD10DTO.TEMPERATURES:
            data['output_value_heating_{0}'.format(GlobalRTD10Serializer._temp_to_str(temperature))] = global_rtd10_dto.heating_values[temperature]
            data['output_value_cooling_{0}'.format(GlobalRTD10Serializer._temp_to_str(temperature))] = global_rtd10_dto.cooling_values[temperature]
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> Tuple[GlobalRTD10DTO, List[str]]
        loaded_fields = []
        heating_values = {}
        cooling_values = {}
        for temperature in GlobalRTD10DTO.TEMPERATURES:
            field = 'output_value_heating_{0}'.format(GlobalRTD10Serializer._temp_to_str(temperature))
            if field in api_data:
                loaded_fields.append(field)
                heating_values[temperature] = api_data[field]
            field = 'output_value_cooling_{0}'.format(GlobalRTD10Serializer._temp_to_str(temperature))
            if field in api_data:
                loaded_fields.append(field)
                cooling_values[temperature] = api_data[field]
        pump_group_dto = GlobalRTD10DTO(heating_values=heating_values,
                                        cooling_values=cooling_values)
        return pump_group_dto, loaded_fields


class RTD10Serializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(rtd10_dto, fields):  # type: (RTD10DTO, Optional[List[str]]) -> Dict
        data = {'id': rtd10_dto.id}
        for field in ['temp_setpoint_output', 'ventilation_speed_output', 'ventilation_speed_value',
                      'mode_output', 'mode_value', 'on_off_output', 'poke_angle_output',
                      'poke_angle_value', 'room']:
            data[field] = Toolbox.denonify(getattr(rtd10_dto, field), RTD10Serializer.BYTE_MAX)
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> Tuple[RTD10DTO, List[str]]
        loaded_fields = ['id']
        shutter_dto = RTD10DTO(api_data['id'])
        loaded_fields += SerializerToolbox.deserialize(
            dto=shutter_dto,  # Referenced
            api_data=api_data,
            mapping={field: (field, RTD10Serializer.BYTE_MAX)
                     for field in ['temp_setpoint_output', 'ventilation_speed_output', 'ventilation_speed_value',
                                   'mode_output', 'mode_value', 'on_off_output', 'poke_angle_output',
                                   'poke_angle_value', 'room']}
        )
        return shutter_dto, loaded_fields
