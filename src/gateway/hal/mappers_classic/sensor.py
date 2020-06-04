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
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import SensorConfiguration

if False:  # MYPY
    from typing import List, Dict, Any


class SensorMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> SensorDTO
        data = orm_object.serialize()
        return SensorDTO(id=data['id'],
                         name=data['name'],
                         offset=data['offset'],
                         virtual=data['virtual'])

    @staticmethod
    def dto_to_orm(sensor_dto, fields):  # type: (SensorDTO, List[str]) -> EepromModel
        data = {'id': sensor_dto.id}  # type: Dict[str, Any]
        for dto_field, data_field in {'name': 'name',
                                      'offset': 'offset',
                                      'virtual': 'virtual'}.items():
            if dto_field in fields:
                data[data_field] = getattr(sensor_dto, dto_field)
        return SensorConfiguration.deserialize(data)
