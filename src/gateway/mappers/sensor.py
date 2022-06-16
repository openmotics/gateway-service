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

import logging

from gateway.dto.sensor import MasterSensorDTO, SensorDTO, SensorSourceDTO
from gateway.models import Database, Plugin, Room, Sensor

if False:  # MYPY
    from typing import Optional

logger = logging.getLogger(__name__)


class SensorMapper(object):
    BYTE_MAX = 255

    def __init__(self, db):
        self._db = db

    def orm_to_dto(self, sensor):  # type: (Sensor) -> SensorDTO
        source_dto = SensorSourceDTO(type=sensor.source)
        plugin = sensor.plugin
        if sensor.source == Sensor.Sources.PLUGIN and plugin is not None:
            source_dto.id = plugin.id
            source_dto.name = plugin.name
        room = sensor.room.number if sensor.room else None
        return SensorDTO(sensor.id,
                         source=source_dto,
                         external_id=sensor.external_id,
                         physical_quantity=sensor.physical_quantity,
                         unit=sensor.unit,
                         name=sensor.name,
                         in_use=sensor.in_use,
                         room=room)

    def dto_to_orm(self, sensor_dto):  # type: (SensorDTO) -> Sensor
        sensor = self._db.query(Sensor).filter_by(id=sensor_dto.id).one()  # type: Sensor
        if 'physical_quantity' in sensor_dto.loaded_fields:
            sensor.physical_quantity = sensor_dto.physical_quantity
        if 'unit' in sensor_dto.loaded_fields:
            sensor.unit = sensor_dto.unit
        if 'name' in sensor_dto.loaded_fields:
            sensor.name = sensor_dto.name
        if 'room' in sensor_dto.loaded_fields:
            if sensor_dto.room not in (None, 255):
                sensor.room = self._db.query(Room).filter_by(number=sensor_dto.room).one()
            else:
                sensor.room = None
        if 'in_use' in sensor_dto.loaded_fields:
            sensor.in_use = sensor_dto.in_use
        return sensor

    def dto_to_master_dto(self, sensor_dto):  # type: (SensorDTO) -> Optional[MasterSensorDTO]
        if sensor_dto.source.is_master:
            master_id = int(sensor_dto.external_id)
            master_dto = MasterSensorDTO(id=master_id)
            if 'name' in sensor_dto.loaded_fields:
                master_dto.name = sensor_dto.name
            if 'virtual' in sensor_dto.loaded_fields:
                master_dto.virtual = sensor_dto.virtual
            if 'offset' in sensor_dto.loaded_fields and sensor_dto.physical_quantity == Sensor.PhysicalQuantities.TEMPERATURE:
                master_dto.offset = sensor_dto.offset
            return master_dto
        else:
            return None
