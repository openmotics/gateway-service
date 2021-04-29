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
Sensor (de)serializer
"""
from __future__ import absolute_import

from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import SensorDTO, SensorSourceDTO, SensorStatusDTO
from toolbox import Toolbox

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class SensorSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(sensor_dto, fields):  # type: (SensorDTO, Optional[List[str]]) -> Dict
        source = None
        if sensor_dto.source:
            source = {'type': sensor_dto.source.type,
                      'name': sensor_dto.source.name}
        data = {'id': sensor_dto.id,
                'source': source,
                'external_id': sensor_dto.external_id,
                'physical_quantity': sensor_dto.physical_quantity,
                'unit': sensor_dto.unit,
                'name': sensor_dto.name,
                'offset': Toolbox.denonify(sensor_dto.offset, 0),
                'room': Toolbox.denonify(sensor_dto.room, SensorSerializer.BYTE_MAX),
                'virtual': sensor_dto.virtual}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> SensorDTO
        sensor_id = None  # type: Optional[int]
        if 'id' in api_data:
            sensor_id = api_data['id']
        sensor_dto = SensorDTO(sensor_id)
        if 'source' in api_data:
            source_name = api_data['source'].get('name') or None
            sensor_dto.source = SensorSourceDTO(api_data['source']['type'],
                                                name=source_name)
        SerializerToolbox.deserialize(
            dto=sensor_dto,  # Referenced
            api_data=api_data,
            mapping={'external_id': ('external_id', None),
                     'physical_quantity': ('physical_quantity', None),
                     'unit': ('unit', None),
                     'name': ('name', None),
                     'offset': ('offset', 0),
                     'room': ('room', SensorSerializer.BYTE_MAX),
                     'virtual': ('virtual', None)}
        )
        return sensor_dto


class SensorStatusSerializer(object):
    @staticmethod
    def serialize(status_dto, fields):  # type: (SensorStatusDTO, Optional[List[str]]) -> Dict
        data = {'id': status_dto.id,
                'value': status_dto.value}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> SensorStatusDTO
        status_dto = SensorStatusDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=status_dto,
            api_data=api_data,
            mapping={'value': ('value', None)}
        )
        return status_dto
