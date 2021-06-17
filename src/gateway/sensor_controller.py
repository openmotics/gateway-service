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
import time

from peewee import JOIN

from gateway.base_controller import BaseController, SyncStructure
from gateway.dto import MasterSensorDTO, SensorDTO, SensorSourceDTO, \
    SensorStatusDTO
from gateway.events import GatewayEvent
from gateway.hal.master_event import MasterEvent
from gateway.mappers.sensor import SensorMapper
from gateway.models import Plugin, Room, Sensor
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import Dict, List, Optional, Set, Tuple
    from gateway.master_controller import MasterController

logger = logging.getLogger(__name__)


@Injectable.named('sensor_controller')
@Singleton
class SensorController(BaseController):
    SYNC_STRUCTURES = [SyncStructure(Sensor, 'sensor')]
    STATUS_EXIPRE = 60.0

    MASTER_TYPES = {MasterEvent.SensorType.TEMPERATURE: Sensor.PhysicalQuantities.TEMPERATURE,
                    MasterEvent.SensorType.HUMIDITY: Sensor.PhysicalQuantities.HUMIDITY,
                    MasterEvent.SensorType.BRIGHTNESS: Sensor.PhysicalQuantities.BRIGHTNESS}

    @Inject
    def __init__(self, master_controller=INJECTED, pubsub=INJECTED):
        # type: (MasterController, PubSub) -> None
        super(SensorController, self).__init__(master_controller, sync_interval=600)
        self._pubsub = pubsub
        self._master_cache = {}  # type: Dict[Tuple[str,int],SensorDTO]
        self._status = {}  # type: Dict[int,SensorStatusDTO]

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.SENSOR, self._handle_master_event)

    def _publish_config(self):
        # type: () -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'sensor'})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def _handle_status(self, status_dto):
        # type: (SensorStatusDTO) -> None
        event_data = {'id': status_dto.id,
                      'value': status_dto.value}
        gateway_event = GatewayEvent(GatewayEvent.Types.SENSOR_CHANGE, event_data)
        if not (status_dto == self._status.get(status_dto.id)):
            logger.debug('Sensor value changed %s', gateway_event)
            self._status[status_dto.id] = status_dto
            self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)
        self._status[status_dto.id].last_value = time.time()

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        super(SensorController, self)._handle_master_event(master_event)
        if master_event.type == MasterEvent.Types.SENSOR_VALUE:
            sensor_type = SensorController.MASTER_TYPES[master_event.data['type']]
            key = (sensor_type, master_event.data['sensor'])
            sensor_dto = self._master_cache.get(key)
            if sensor_dto is not None:
                self._handle_status(SensorStatusDTO(sensor_dto.id,
                                                    value=master_event.data['value']))
            else:
                logger.warning('Received value for unknown %s sensor %s', key, master_event)
                self.request_sync_orm()

    def _sync_orm_structure(self, structure):  # type: (SyncStructure) -> None
        if structure.orm_model is Sensor:
            master_orm_mapping = {}
            for dto in self._master_controller.load_sensors():
                if structure.skip is not None and structure.skip(dto):
                    continue
                master_orm_mapping[dto.id] = dto
            ids = set()
            brighness = self._master_controller.get_sensors_brightness()
            humidity = self._master_controller.get_sensors_humidity()
            temperature = self._master_controller.get_sensors_temperature()
            ids |= self._sync_orm_master(Sensor.PhysicalQuantities.TEMPERATURE, 'celcius', temperature, master_orm_mapping)
            ids |= self._sync_orm_master(Sensor.PhysicalQuantities.HUMIDITY, 'percent', humidity, master_orm_mapping)
            ids |= self._sync_orm_master(Sensor.PhysicalQuantities.BRIGHTNESS, 'percent', brighness, master_orm_mapping)
            count = Sensor.delete() \
                .where(Sensor.source == Sensor.Sources.MASTER) \
                .where(Sensor.external_id.not_in(ids)) \
                .execute()
            if count > 0:
                logger.info('Removed {} unreferenced sensor(s)'.format(count))
        else:
            super(SensorController, self)._sync_orm_structure(structure)

    def _sync_orm_master(self, physical_quantity, unit, values, master_orm_mapping):
        # type: (str, str, List[Optional[float]], Dict[int,MasterSensorDTO]) -> Set[str]
        source = SensorSourceDTO(Sensor.Sources.MASTER)
        ids = set()
        now = time.time()
        for i, value in enumerate(values):
            if i not in master_orm_mapping:
                continue
            # Keep if a corresponding master sensor exists
            external_id = str(i)
            ids.add(external_id)
            if value is None:
                continue
            master_sensor_dto = master_orm_mapping[i]

            sensor_dto = SensorDTO(None,
                                   source=source,
                                   external_id=external_id,
                                   physical_quantity=physical_quantity,
                                   unit=unit,
                                   name=master_sensor_dto.name)
            sensor, _ = self._create_or_update_sensor(sensor_dto)

            sensor_dto.id = sensor.id
            self._master_cache[(physical_quantity, i)] = sensor_dto

            status_dto = SensorStatusDTO(sensor.id, value=float(value))
            self._handle_status(status_dto)
        return ids

    def load_sensor(self, sensor_id):  # type: (int) -> SensorDTO
        sensor = Sensor.select() \
                       .join_from(Sensor, Room, join_type=JOIN.LEFT_OUTER) \
                       .where(Sensor.id == sensor_id) \
                       .get()  # type: Sensor
        room = sensor.room.number if sensor.room is not None else None
        source_name = None if sensor.plugin is None else sensor.plugin.name
        sensor_dto = SensorDTO(id=sensor.id,
                               source=SensorSourceDTO(sensor.source, name=source_name),
                               external_id=sensor.external_id,
                               physical_quantity=sensor.physical_quantity,
                               unit=sensor.unit,
                               name=sensor.name,
                               room=room)
        if sensor.source == Sensor.Sources.MASTER:
            master_sensor_dto = self._master_controller.load_sensor(sensor_id=int(sensor.external_id))
            sensor_dto.virtual = master_sensor_dto.virtual
            if sensor.physical_quantity == Sensor.PhysicalQuantities.TEMPERATURE:
                sensor_dto.offset = master_sensor_dto.offset
        return sensor_dto

    def load_sensors(self):  # type: () -> List[SensorDTO]
        sensor_dtos = []
        query = Sensor.select() \
            .join_from(Sensor, Room, join_type=JOIN.LEFT_OUTER) \
            .where(~Sensor.physical_quantity.is_null())
        for sensor in list(query):
            source_name = None if sensor.plugin is None else sensor.plugin.name
            room = sensor.room.number if sensor.room is not None else None
            sensor_dto = SensorDTO(id=sensor.id,
                                   source=SensorSourceDTO(sensor.source, name=source_name),
                                   external_id=sensor.external_id,
                                   physical_quantity=sensor.physical_quantity,
                                   unit=sensor.unit,
                                   name=sensor.name,
                                   room=room)
            if sensor.source == Sensor.Sources.MASTER:
                master_sensor_dto = self._master_controller.load_sensor(sensor_id=int(sensor.external_id))
                sensor_dto.virtual = master_sensor_dto.virtual
                if sensor.physical_quantity == Sensor.PhysicalQuantities.TEMPERATURE:
                    sensor_dto.offset = master_sensor_dto.offset
            sensor_dtos.append(sensor_dto)
        return sensor_dtos

    def save_sensors(self, sensors):  # type: (List[SensorDTO]) -> None
        publish = False
        master_sensors = []
        for sensor_dto in sensors:
            sensor, changed = self._create_or_update_sensor(sensor_dto)
            publish |= changed

            sensor_dto.id = sensor.id
            sensor_dto.external_id = sensor.external_id
            if sensor_dto.source is None:
                source_name = None if sensor.plugin is None else sensor.plugin.name
                sensor_dto.source = SensorSourceDTO(sensor.source, name=source_name)

            master_dto = SensorMapper.dto_to_master_dto(sensor_dto)
            if master_dto:
                master_sensors.append(master_dto)
        if master_sensors:
            self._master_controller.save_sensors(master_sensors)
        if publish:
            self._publish_config()

    def _create_or_update_sensor(self, sensor_dto):  # type: (SensorDTO) -> Tuple[Sensor, bool]
        changed = False
        sensor = SensorMapper.dto_to_orm(sensor_dto)
        if sensor.id is None:
            orm_id = get_sensor_orm_id(sensor.source)
            sensor = Sensor.create(id=orm_id,
                                   source=sensor.source,
                                   plugin=sensor.plugin,
                                   external_id=sensor.external_id,
                                   physical_quantity=sensor.physical_quantity,
                                   unit=sensor.unit,
                                   name=sensor.name,
                                   room=sensor.room)
            changed = True
        else:
            if sensor.save() > 0:
                changed = True
        if sensor.source == Sensor.Sources.MASTER and sensor.id > 200:
            Sensor.delete().where(Sensor.id == sensor.id).execute()
            raise ValueError('Master sensor id {} out of range'.format(sensor.id))
        if sensor.source == Sensor.Sources.PLUGIN and sensor.id < 500:
            Sensor.delete().where(Sensor.id == sensor.id).execute()
            raise ValueError('Plugin sensor id {} is invalid'.format(sensor.id))
        return sensor, changed

    def get_sensors_status(self):  # type: () -> List[SensorStatusDTO]
        """ Get the current status of all sensors.
        """
        now = time.time()
        status = []
        for status_dto in list(self._status.values()):
            if status_dto.last_value is None or status_dto.last_value < now - self.STATUS_EXIPRE:
                self._status.pop(status_dto.id)
                continue
            status.append(status_dto)
        return status

    def get_sensor_status(self, sensor_id):  # type: (int) -> Optional[SensorStatusDTO]
        """ Get the current status of a sensor.
        """
        now = time.time()
        status_dto = None
        if sensor_id in self._status:
            status_dto = self._status[sensor_id]
            if status_dto.last_value is None or status_dto.last_value < now - self.STATUS_EXIPRE:
                self._status.pop(sensor_id)
                status_dto = None
        return status_dto

    def set_sensor_status(self, status_dto):  # type: (SensorStatusDTO) -> SensorStatusDTO
        """ Update the current status of a (non master) sensor.
        """
        if status_dto.id < 200:
            raise ValueError('Sensor %s status is readonly' % status_dto.id)
        self._handle_status(status_dto)
        return status_dto

    def set_virtual_sensor(self, sensor_id, temperature, humidity, brightness):
        """ Set the temperature, humidity and brightness value of a (master) virtual sensor. """
        self.__master_controller.set_virtual_sensor(sensor_id, temperature, humidity, brightness)

    def _translate_legacy_statuses(self, physical_quantity):  # type: (str) -> List[Optional[float]]
        sensors = Sensor.select() \
            .where(Sensor.source == Sensor.Sources.MASTER) \
            .where(Sensor.physical_quantity == physical_quantity)
        try:
            sensor_count = max(s.id for s in sensors) + 1
        except ValueError:
            sensor_count = 0
        now = time.time()
        values = [None] * sensor_count  # type: List[Optional[float]]
        for sensor in sensors:
            status_dto = self._status.get(sensor.id)
            if status_dto:
                if status_dto.last_value is None or status_dto.last_value < now - self.STATUS_EXIPRE:
                    self._status.pop(sensor.id)
                    status_dto = None
            if status_dto:
                values[sensor.id] = status_dto.value
        return values

    def get_temperature_status(self):  # type: () -> List[Optional[float]]
        """ Get the current temperature of all sensors.

        :returns: list with 32 temperatures, 1 for each sensor. None/null if not connected
        """
        return self._translate_legacy_statuses(Sensor.PhysicalQuantities.TEMPERATURE)

    def get_humidity_status(self):  # type: () -> List[Optional[float]]
        """ Get the current humidity of all sensors. """
        return self._translate_legacy_statuses(Sensor.PhysicalQuantities.HUMIDITY)

    def get_brightness_status(self):  # type: () -> List[Optional[float]]
        """ Get the current brightness of all sensors. """
        return self._translate_legacy_statuses(Sensor.PhysicalQuantities.BRIGHTNESS)


def get_sensor_orm_id(source):  # type: (str) -> Optional[int]
    if source == Sensor.Sources.PLUGIN:
        # Plugins sensors use 510 or auto increment
        if Sensor.select().where(Sensor.id > 255).count() == 0:
            return 510
    if source == Sensor.Sources.MASTER:
        # Master sensors use 1-200
        query = Sensor.select(Sensor.id) \
            .where(Sensor.source == Sensor.Sources.MASTER) \
            .where(Sensor.id < 200)
        try:
            return max(x for (x,) in query.tuples()) + 1
        except ValueError:
            return 0
    return None
