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
from gateway.models import Plugin, Room, Sensor
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import Dict, List, Optional, Set, Tuple
    from gateway.master_controller import MasterController

logger = logging.getLogger('gateway.sensor_controller')


@Injectable.named('sensor_controller')
@Singleton
class SensorController(BaseController):
    SYNC_STRUCTURES = [SyncStructure(Sensor, 'sensor')]
    STATUS_EXIPRE = 60.0

    @Inject
    def __init__(self, master_controller=INJECTED, pubsub=INJECTED):
        # type: (MasterController, PubSub) -> None
        super(SensorController, self).__init__(master_controller, sync_interval=60)
        self._pubsub = pubsub
        self._master_cache = {}  # type: Dict[Tuple[str,int],SensorDTO]
        self._status = {}  # type: Dict[int,SensorStatusDTO]

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.SENSOR, self._handle_master_event)

    def _publish_config(self):
        # type: () -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'sensor'})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def _publish_state(self, status_dto):
        # type: (SensorStatusDTO) -> None
        event_data = {'id': status_dto.id,
                      'value': status_dto.value}
        gateway_event = GatewayEvent(GatewayEvent.Types.SENSOR_CHANGE, event_data)
        logger.debug('Sensor value changed %s', gateway_event)
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        super(SensorController, self)._handle_master_event(master_event)
        if master_event.type == MasterEvent.Types.SENSOR_VALUE:
            key = (master_event.data['type'], master_event.data['id'])
            sensor_dto = self._master_cache.get(key)
            if sensor_dto is not None:
                self._master_cache[key] = sensor_dto
                self._publish_state(SensorStatusDTO(sensor_dto.id,
                                                    value=master_event.data['value']))
            else:
                logger.warning('Received value for unknown sensor %s', master_event)
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
            ids |= self._sync_orm_master(Sensor.PhysicalQuanitites.TEMPERATURE, 'celcius', temperature, master_orm_mapping)
            ids |= self._sync_orm_master(Sensor.PhysicalQuanitites.HUMIDITY, 'percent', humidity, master_orm_mapping)
            ids |= self._sync_orm_master(Sensor.PhysicalQuanitites.BRIGHTNESS, 'percent', brighness, master_orm_mapping)
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
        source = Sensor.Sources.MASTER
        ids = set()
        now = time.time()
        for i, value in enumerate(values):
            if i not in master_orm_mapping:
                continue
            # Keep if a corresponding master sensor exists
            logger.debug('Sync S#%s %s value=%s', i, physical_quantity, value)
            external_id = str(i)
            ids.add(external_id)
            if value is None:
                continue
            master_sensor_dto = master_orm_mapping[i]
            query = Sensor.select(Sensor.id).where(Sensor.source == source)
            try:
                sensor_max = max(x for (x,) in query.tuples())
            except ValueError:
                sensor_max = 0

            query = Sensor.select() \
                .where(Sensor.source == source) \
                .where(Sensor.external_id == external_id)
            sensor = query.where(Sensor.physical_quantity == physical_quantity) \
                .first()
            if sensor is None:
                sensor = query.where(Sensor.physical_quantity.is_null()) \
                    .first()
            fields = {'id': sensor_max + 1,
                      'source': source,
                      'external_id': external_id,
                      'physical_quantity': physical_quantity,
                      'unit': unit,
                      'name': master_sensor_dto.name}
            if sensor is None:
                sensor = Sensor.create(**fields)
            elif sensor.physical_quantity is None:
                sensor.physical_quantity = physical_quantity
                sensor.unit = unit
                sensor.name = master_sensor_dto.name
                sensor.save()
            else:
                pass  # no changes
            if sensor.id > 200:
                self._status.pop(sensor.id, None)
                Sensor.delete().where(Sensor.id == sensor.id).execute()
                logger.warning('Sensor id %s out of range, removed', sensor.id)
            room = sensor.room.number if sensor.room is not None else None
            source_name = None if sensor.plugin is None else sensor.plugin.name
            sensor_dto = SensorDTO(id=sensor.id,
                                   source=SensorSourceDTO(None,
                                                          type=sensor.source,
                                                          name=source_name),
                                   external_id=sensor.external_id,
                                   physical_quantity=sensor.physical_quantity,
                                   unit=sensor.unit,
                                   name=sensor.name,
                                   room=room)
            self._master_cache[(physical_quantity, i)] = sensor_dto
            status_dto = SensorStatusDTO(sensor.id, value=float(value))
            if not (status_dto == self._status.get(status_dto.id)):
                self._status[sensor.id] = status_dto
                self._publish_state(status_dto)
            self._status[sensor.id].last_value = now
        return ids

    def load_sensor(self, sensor_id):  # type: (int) -> SensorDTO
        sensor = Sensor.select() \
                       .join_from(Sensor, Room, join_type=JOIN.LEFT_OUTER) \
                       .where(Sensor.id == sensor_id) \
                       .get()  # type: Sensor
        room = sensor.room.number if sensor.room is not None else None
        source_name = None if sensor.plugin is None else sensor.plugin.name
        sensor_dto = SensorDTO(id=sensor.id,
                               source=SensorSourceDTO(None,
                                                      type=sensor.source,
                                                      name=source_name),
                               external_id=sensor.external_id,
                               physical_quantity=sensor.physical_quantity,
                               unit=sensor.unit,
                               name=sensor.name,
                               room=room)
        if sensor.source == Sensor.Sources.MASTER:
            master_sensor_dto = self._master_controller.load_sensor(sensor_id=int(sensor.external_id))
            sensor_dto.virtual = master_sensor_dto.virtual
            if sensor.physical_quantity == Sensor.PhysicalQuanitites.TEMPERATURE:
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
                                   source=SensorSourceDTO(None,
                                                          type=sensor.source,
                                                          name=source_name),
                                   external_id=sensor.external_id,
                                   physical_quantity=sensor.physical_quantity,
                                   unit=sensor.unit,
                                   name=sensor.name,
                                   room=room)
            if sensor.source == Sensor.Sources.MASTER:
                master_sensor_dto = self._master_controller.load_sensor(sensor_id=int(sensor.external_id))
                sensor_dto.virtual = master_sensor_dto.virtual
                if sensor.physical_quantity == Sensor.PhysicalQuanitites.TEMPERATURE:
                    sensor_dto.offset = master_sensor_dto.offset
            sensor_dtos.append(sensor_dto)
        return sensor_dtos

    def save_sensors(self, sensors):  # type: (List[SensorDTO]) -> None
        any_changed = False
        master_sensors = []
        for sensor_dto in sensors:
            plugin = None
            if sensor_dto.id is not None:
                sensor = Sensor.get_or_none(id=sensor_dto.id)  # type: Sensor
            elif 'source' in sensor_dto.loaded_fields and 'external_id' in sensor_dto.loaded_fields and 'physical_quantity' in sensor_dto.loaded_fields:
                plugin = Plugin.get(name=sensor_dto.source.name) if sensor_dto.source.type == Sensor.Sources.PLUGIN else None
                sensor = Sensor.select() \
                    .where(Sensor.source == sensor_dto.source.type) \
                    .where(Sensor.external_id == sensor_dto.external_id) \
                    .where(Sensor.physical_quantity == sensor_dto.physical_quantity) \
                    .where(Sensor.plugin == plugin) \
                    .first()
            else:
                sensor = None
            if sensor is None:
                if sensor_dto.id is not None:
                    raise ValueError('Sensor {0} does not exist'.format(sensor_dto.id))
                if sensor_dto.source and sensor_dto.source.type == Sensor.Sources.PLUGIN:
                    sensor_id = None  # type: Optional[int]
                    if Sensor.select().where(Sensor.id > 255).count() == 0:
                        sensor_id = 510
                    room = None
                    if 'room' in sensor_dto.loaded_fields:
                        if sensor_dto.room is None:
                            room = None
                        elif 0 <= sensor_dto.room <= 100:
                            room, _ = Room.get_or_create(number=sensor_dto.room)
                    plugin = Plugin.get(name=sensor_dto.source.name) if sensor_dto.source.type == Sensor.Sources.PLUGIN else None
                    sensor = Sensor.create(id=sensor_id,
                                           source=sensor_dto.source.type,
                                           plugin=plugin,
                                           external_id=sensor_dto.external_id,
                                           physical_quantity=sensor_dto.physical_quantity,
                                           unit=sensor_dto.unit,
                                           name=sensor_dto.name,
                                           room=room)
                elif 'virtual' in sensor_dto.loaded_fields and sensor_dto.source and sensor_dto.source.type == Sensor.Sources.MASTER:
                    query = Sensor.select(Sensor.id).where(Sensor.source == Sensor.Sources.MASTER)
                    try:
                        sensor_max = max(x for (x,) in query.tuples())
                    except ValueError:
                        sensor_max = 0
                    room = None
                    if 'room' in sensor_dto.loaded_fields:
                        if sensor_dto.room is None:
                            room = None
                        elif 0 <= sensor_dto.room <= 100:
                            room, _ = Room.get_or_create(number=sensor_dto.room)
                    sensor = Sensor.create(id=sensor_max + 1,
                                           source=sensor_dto.source.type,
                                           plugin=plugin,
                                           external_id=sensor_dto.external_id,
                                           physical_quantity=sensor_dto.physical_quantity,
                                           unit=sensor_dto.unit,
                                           name=sensor_dto.name,
                                           room=room)
                    if sensor.id > 200:
                        Sensor.delete().where(Sensor.id == sensor.id).execute()
                        logger.warning('Sensor id %s out of range, removed', sensor.id)
                else:
                    raise ValueError('Sensor {0} is invalid'.format(sensor_dto))
            sensor_dto.id = sensor.id
            changed = False
            if 'physical_quantity' in sensor_dto.loaded_fields:
                sensor.physical_quantity = sensor_dto.physical_quantity
                changed = True
            if 'unit' in sensor_dto.loaded_fields:
                sensor.unit = sensor_dto.unit
                changed = True
            if 'name' in sensor_dto.loaded_fields:
                sensor.name = sensor_dto.name
                changed = True
            if 'room' in sensor_dto.loaded_fields:
                if sensor_dto.room is None:
                    sensor.room = None
                elif 0 <= sensor_dto.room <= 100:
                    sensor.room, _ = Room.get_or_create(number=sensor_dto.room)
                changed = True
            any_changed |= changed
            if changed:
                sensor.save()
            if sensor.source == Sensor.Sources.MASTER:
                dto = MasterSensorDTO(id=int(sensor.external_id), name=sensor.name)
                if 'virtual' in sensor_dto.loaded_fields:
                    dto.virtual = sensor_dto.virtual
                if 'offset' in sensor_dto.loaded_fields and sensor.physical_quantity == Sensor.PhysicalQuanitites.TEMPERATURE:
                    dto.offset = sensor_dto.offset
                master_sensors.append(dto)
        if master_sensors:
            self._master_controller.save_sensors(master_sensors)
        if any_changed:
            self._publish_config()

    def get_sensors_status(self):  # type: () -> List[SensorStatusDTO]
        """ Get the current status of all sensors.
        """
        status = []
        for status_dto in list(self._status.values()):
            if status_dto.last_value is None or status_dto.last_value < time.time() - self.STATUS_EXIPRE:
                self._status.pop(status_dto.id)
                continue
            status.append(status_dto)
        return status

    def get_sensor_status(self, sensor_id):  # type: (int) -> Optional[SensorStatusDTO]
        """ Get the current status of a sensor.
        """
        status_dto = None
        if sensor_id in self._status:
            status_dto = self._status[sensor_id]
            if status_dto.last_value is None or status_dto.last_value < time.time() - self.STATUS_EXIPRE:
                self._status.pop(sensor_id)
                status_dto = None
        return status_dto

    def set_sensor_status(self, status_dto):  # type: (SensorStatusDTO) -> SensorStatusDTO
        """ Update the current status of a (non master) sensor.
        """
        if status_dto.id < 256:
            raise ValueError('Sensor %s status is readonly' % status_dto.id)
        if not (status_dto == self._status.get(status_dto.id)):
            self._status[status_dto.id] = status_dto
            self._publish_state(status_dto)
        self._status[status_dto.id].last_value = time.time()
        return status_dto

    def _translate_legacy_statuses(self, physical_quantity):  # type: (str) -> List[Optional[float]]
        sensors = Sensor.select() \
            .where(Sensor.source == Sensor.Sources.MASTER) \
            .where(Sensor.physical_quantity == physical_quantity)
        try:
            sensor_count = max(s.id for s in sensors) + 1
        except ValueError:
            sensor_count = 0
        values = [None] * sensor_count  # type: List[Optional[float]]
        for sensor in sensors:
            values[sensor.id] = self._status[sensor.id].value
        return values

    def get_temperature_status(self):  # type: () -> List[Optional[float]]
        """ Get the current temperature of all sensors.

        :returns: list with 32 temperatures, 1 for each sensor. None/null if not connected
        """
        return self._translate_legacy_statuses(Sensor.PhysicalQuanitites.TEMPERATURE)

    def get_humidity_status(self):  # type: () -> List[Optional[float]]
        """ Get the current humidity of all sensors. """
        return self._translate_legacy_statuses(Sensor.PhysicalQuanitites.HUMIDITY)

    def get_brightness_status(self):  # type: () -> List[Optional[float]]
        """ Get the current brightness of all sensors. """
        return self._translate_legacy_statuses(Sensor.PhysicalQuanitites.BRIGHTNESS)
