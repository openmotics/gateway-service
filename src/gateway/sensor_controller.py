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
Sensor BLL
"""
from __future__ import absolute_import
import logging
from ioc import Injectable, Inject, INJECTED, Singleton
from gateway.base_controller import BaseController, SyncStructure
from gateway.dto import SensorDTO
from gateway.models import Sensor, Room

if False:  # MYPY
    from typing import List, Tuple

logger = logging.getLogger("openmotics")


@Injectable.named('sensor_controller')
@Singleton
class SensorController(BaseController):

    SYNC_STRUCTURES = [SyncStructure(Sensor, 'sensor')]

    @Inject
    def __init__(self, master_controller=INJECTED):
        super(SensorController, self).__init__(master_controller)

    def load_sensor(self, sensor_id):  # type: (int) -> SensorDTO
        sensor = Sensor.get(number=sensor_id)  # type: Sensor
        sensor_dto = self._master_controller.load_sensor(sensor_id=sensor.number)
        sensor_dto.room = sensor.room.number if sensor.room is not None else None
        return sensor_dto

    def load_sensors(self):  # type: () -> List[SensorDTO]
        sensor_dtos = []
        for sensor_ in Sensor.select():
            sensor_dto = self._master_controller.load_sensor(sensor_id=sensor_.number)
            sensor_dto.room = sensor_.room.number if sensor_.room is not None else None
            sensor_dtos.append(sensor_dto)
        return sensor_dtos

    def save_sensors(self, sensors):  # type: (List[Tuple[SensorDTO, List[str]]]) -> None
        sensors_to_save = []
        for sensor_dto, fields in sensors:
            sensor_ = Sensor.get_or_none(number=sensor_dto.id)  # type: Sensor
            if sensor_ is None:
                logger.info('Ignored saving non-existing Sensor {0}'.format(sensor_dto.id))
            if 'room' in fields:
                if sensor_dto.room is None:
                    sensor_.room = None
                elif 0 <= sensor_dto.room <= 100:
                    sensor_.room, _ = Room.get_or_create(number=sensor_dto.room)
                sensor_.save()
            sensors_to_save.append((sensor_dto, fields))
        self._master_controller.save_sensors(sensors_to_save)
