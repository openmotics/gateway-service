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
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import SensorDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class SensorSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(sensor_dto, fields):  # type: (SensorDTO, Optional[List[str]]) -> Dict
        data = {'id': sensor_dto.id,
                'name': sensor_dto.name,
                'offset': Toolbox.denonify(sensor_dto.offset, 0),
                'room': Toolbox.denonify(sensor_dto.room, SensorSerializer.BYTE_MAX),
                'virtual': sensor_dto.virtual}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> Tuple[SensorDTO, List[str]]
        loaded_fields = ['id']
        sensor_dto = SensorDTO(api_data['id'])
        loaded_fields += SerializerToolbox.deserialize(
            dto=sensor_dto,  # Referenced
            api_data=api_data,
            mapping={'name': ('name', None),
                     'offset': ('offset', 0),
                     'room': ('room', SensorSerializer.BYTE_MAX),
                     'virtual': ('virtual', None)}
        )
        return sensor_dto, loaded_fields
