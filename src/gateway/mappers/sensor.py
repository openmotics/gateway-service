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
from gateway.models import Plugin, Room, Sensor

if False:  # MYPY
    from typing import Optional

logger = logging.getLogger('openmotics')


class SensorMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(sensor):  # type: (Sensor) -> SensorDTO
        source_dto = SensorSourceDTO(type=sensor.source)
        if source_dto.is_plugin:
            source_dto.id = sensor.plugin.id
            source_dto.name = sensor.plugin.name
        return SensorDTO(sensor.id,
                         source=source_dto,
                         external_id=sensor.external_id,
                         name=sensor.name)

    @staticmethod
    def dto_to_orm(sensor_dto):  # type: (SensorDTO) -> Sensor
        plugin = None
        if sensor_dto.id:
            query = Sensor.select().where(Sensor.id == sensor_dto.id)
        elif sensor_dto.source and sensor_dto.external_id and sensor_dto.physical_quantity:
            if sensor_dto.source.is_plugin:
                plugin = Plugin.get(name=sensor_dto.source.name)
            query = Sensor.select() \
                .where(Sensor.source == sensor_dto.source.type) \
                .where(Sensor.plugin == plugin) \
                .where(Sensor.external_id == sensor_dto.external_id) \
                .where(Sensor.physical_quantity == sensor_dto.physical_quantity)
        else:
            raise ValueError('Invalid sensor %s', sensor_dto)
        sensor = query.first()
        if sensor is None:
            if sensor_dto.source and sensor_dto.source.is_master:
                query = Sensor.select() \
                    .where(Sensor.source == sensor_dto.source.type) \
                    .where(Sensor.external_id == sensor_dto.external_id) \
                    .where(Sensor.physical_quantity.is_null())
                sensor = query.first()
        if sensor is None:
            if plugin is None and sensor_dto.source.is_plugin:
                plugin = Plugin.get(name=sensor_dto.source.name)
            if 'room' in sensor_dto.loaded_fields:
                room = Room.get_or_create(number=sensor_dto.room)
            else:
                query = Sensor.select() \
                    .where(Sensor.source == sensor_dto.source.type) \
                    .where(Sensor.external_id == sensor_dto.external_id) \
                    .where(~Sensor.room.is_null())
                sensor = query.first()
                if sensor:
                    room = sensor.room
                else:
                    room = None
            sensor = Sensor(source=sensor_dto.source.type,
                            plugin=plugin,
                            external_id=sensor_dto.external_id,
                            physical_quantity=sensor_dto.physical_quantity,
                            unit=sensor_dto.unit,
                            name=sensor_dto.name,
                            room=room)
        else:
            if 'physical_quantity' in sensor_dto.loaded_fields:
                sensor.physical_quantity = sensor_dto.physical_quantity
            if 'unit' in sensor_dto.loaded_fields:
                sensor.unit = sensor_dto.unit
            if 'name' in sensor_dto.loaded_fields:
                sensor.name = sensor_dto.name
            if 'room' in sensor_dto.loaded_fields:
                if sensor_dto.room is None:
                    room = None
                elif 0 <= sensor_dto.room <= 100:
                    room, _ = Room.get_or_create(number=sensor_dto.room)
                sensor.room = room
        return sensor

    @staticmethod
    def dto_to_master_dto(sensor_dto):  # type: (SensorDTO) -> Optional[MasterSensorDTO]
        if sensor_dto.source.is_master:
            master_id = int(sensor_dto.external_id)
            master_dto = MasterSensorDTO(id=master_id)
            if 'name' in sensor_dto.loaded_fields:
                master_dto.name = sensor_dto.name
            if 'virtual' in sensor_dto.loaded_fields:
                master_dto.virtual = sensor_dto.virtual
            if 'offset' in sensor_dto.loaded_fields and sensor_dto.physical_quantity == Sensor.PhysicalQuanitites.TEMPERATURE:
                master_dto.offset = sensor_dto.offset
            return master_dto
        else:
            return None
