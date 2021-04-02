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
Sensor Mapper
"""
from __future__ import absolute_import
from gateway.dto.sensor import SensorDTO
from master.core.memory_models import SensorConfiguration

if False:  # MYPY
    from typing import List, Dict, Any


class SensorMapper(object):
    @staticmethod
    def orm_to_dto(orm_object):  # type: (SensorConfiguration) -> SensorDTO
        return SensorDTO(id=orm_object.id,
                         name=orm_object.name,
                         offset=orm_object.temperature_offset)

    @staticmethod
    def dto_to_orm(sensor_dto):  # type: (SensorDTO) -> SensorConfiguration
        new_data = {'id': sensor_dto.id}  # type: Dict[str, Any]
        if 'name' in sensor_dto.loaded_fields:
            new_data['name'] = sensor_dto.name
        if 'offset' in sensor_dto.loaded_fields:
            new_data['temperature_offset'] = sensor_dto.offset
        return SensorConfiguration.deserialize(new_data)
