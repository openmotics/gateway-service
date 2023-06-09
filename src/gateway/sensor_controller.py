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

from sqlalchemy import func

from gateway.base_controller import BaseController, SyncStructure
from gateway.dto import MasterSensorDTO, SensorDTO, SensorSourceDTO, \
    SensorStatusDTO
from gateway.events import GatewayEvent
from gateway.hal.master_event import MasterEvent
from gateway.mappers.sensor import SensorMapper
from gateway.models import Database, Plugin, Room, Sensor, Session
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import Any, Dict, List, Optional, Set, Tuple
    from gateway.hal.master_controller import MasterController

logger = logging.getLogger(__name__)


@Injectable.named('sensor_controller')
@Singleton
class SensorController(BaseController):
    SYNC_STRUCTURES = [SyncStructure(Sensor, 'sensor')]

    MASTER_TYPES = {MasterEvent.SensorType.TEMPERATURE: Sensor.PhysicalQuantities.TEMPERATURE,
                    MasterEvent.SensorType.HUMIDITY: Sensor.PhysicalQuantities.HUMIDITY,
                    MasterEvent.SensorType.BRIGHTNESS: Sensor.PhysicalQuantities.BRIGHTNESS}

    @Inject
    def __init__(self, master_controller=INJECTED, pubsub=INJECTED):
        # type: (MasterController, PubSub) -> None
        super(SensorController, self).__init__(master_controller, sync_interval=600)
        self._pubsub = pubsub
        self._master_cache = {}  # type: Dict[Tuple[str, int],SensorDTO]
        self._status = {}  # type: Dict[int, SensorStatusDTO]
        self._pubsub.subscribe_master_events(PubSub.MasterTopics.SENSOR, self._handle_master_event)

    def sync_state(self):
        # type: () -> None
        logger.debug('Publishing latest sensor status')
        for status_dto in self._status.values():
            event_data = {'id': status_dto.id,
                          'value': status_dto.value}
            gateway_event = GatewayEvent(GatewayEvent.Types.SENSOR_CHANGE, event_data)
            self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _publish_config(self):
        # type: () -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'sensor'})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def _handle_status(self, status_dto):
        # type: (SensorStatusDTO) -> None
        if not (status_dto == self._status.get(status_dto.id)):
            event_data = {'id': status_dto.id,
                          'value': status_dto.value}
            gateway_event = GatewayEvent(GatewayEvent.Types.SENSOR_CHANGE, event_data)
            logger.debug('Sensor value changed %s', gateway_event)
            self._status[status_dto.id] = status_dto
            self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        super(SensorController, self)._handle_master_event(master_event)
        if master_event.type == MasterEvent.Types.SENSOR_VALUE:
            sensor_type = SensorController.MASTER_TYPES.get(master_event.data['type'])
            if sensor_type is None:
                return  # TODO: Support more sensors
            key = (sensor_type, master_event.data['sensor'])
            sensor_dto = self._master_cache.get(key)
            if sensor_dto is not None:
                self._handle_status(SensorStatusDTO(sensor_dto.id,
                                                    value=master_event.data['value']))
            else:
                logger.warning('Received value for unknown %s sensor %s', key, master_event)
                self._sync_structures = True
                self._send_config_event = True
                self.request_sync_orm()

    def _sync_orm_structure(self, structure):  # type: (SyncStructure) -> None
        if structure.orm_model is Sensor:
            master_orm_mapping = {}
            for dto in self._master_controller.load_sensors():
                if structure.skip is not None and structure.skip(dto):
                    continue
                master_orm_mapping[dto.id] = dto
            ids = set()

            with Database.get_session() as db:
                temperature = self._master_controller.get_sensors_temperature()
                ids |= self._sync_orm_master(db, Sensor.PhysicalQuantities.TEMPERATURE, 'celcius', temperature, master_orm_mapping)
                humidity = self._master_controller.get_sensors_humidity()
                ids |= self._sync_orm_master(db, Sensor.PhysicalQuantities.HUMIDITY, 'percent', humidity, master_orm_mapping)
                brighness = self._master_controller.get_sensors_brightness()
                ids |= self._sync_orm_master(db, Sensor.PhysicalQuantities.BRIGHTNESS, 'percent', brighness, master_orm_mapping)

                query = (Sensor.source == Sensor.Sources.MASTER) & (Sensor.external_id.notin_(ids))
                count = db.query(Sensor).where(query).delete()
                if count > 0:
                    logger.info('Removed {} unreferenced sensor(s)'.format(count))
                db.commit()
        else:
            super(SensorController, self)._sync_orm_structure(structure)

    def _sync_orm_master(self, db, physical_quantity, unit, values, master_orm_mapping):
        # type: (Any, str, str, List[Optional[float]], Dict[int,MasterSensorDTO]) -> Set[str]
        source = SensorSourceDTO(Sensor.Sources.MASTER)
        ids = set()
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
            sensor, _ = self._create_or_update_sensor(db, sensor_dto)
            sensor_dto.id = sensor.id
            self._master_cache[(physical_quantity, i)] = sensor_dto

            status_dto = SensorStatusDTO(sensor.id, value=float(value))
            self._handle_status(status_dto)
        return ids

    def load_sensor(self, sensor_id):
        # type: (int) -> SensorDTO
        with Database.get_session() as db:
            sensor = db.get(Sensor, sensor_id)
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

    def load_sensors(self):
        # type: () -> List[SensorDTO]
        with Database.get_session() as db:
            sensors = db.query(Sensor) \
                .where(Sensor.physical_quantity != None) \
                .all()  # type: List[Sensor]
            sensor_dtos = []
            for sensor in sensors:
                source_name = None
                if sensor.plugin is not None:
                    source_name = sensor.plugin.name
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

    def save_sensors(self, sensors):  # type: (List[SensorDTO]) -> List[SensorDTO]
        publish = False
        master_sensors = []
        with Database.get_session() as db:
            mapper = SensorMapper(db)
            for sensor_dto in sensors:
                sensor = mapper.dto_to_orm(sensor_dto)
                publish |= sensor in db.dirty

                sensor_dto.external_id = sensor.external_id
                if sensor_dto.source is None:
                    source_name = None
                    if sensor.plugin is not None:
                        source_name = sensor.plugin.name
                    sensor_dto.source = SensorSourceDTO(sensor.source, name=source_name)
                if sensor_dto.physical_quantity is None:
                    sensor_dto.physical_quantity = sensor.physical_quantity
                master_dto = mapper.dto_to_master_dto(sensor_dto)
                if master_dto:
                    master_sensors.append(master_dto)
            db.commit()
        if master_sensors:
            self._master_controller.save_sensors(master_sensors)
        if publish:
            self._publish_config()
        return sensors

    def register_sensor(self, source_dto, external_id, physical_quantity, unit, default_config=None):
        # type: (SensorSourceDTO, str, str, str, Optional[Dict[str,Any]]) -> SensorDTO
        changed = False
        default_config = default_config or {}
        with Database.get_session() as db:
            if source_dto.type == 'plugin':
                plugin = db.query(Plugin).filter_by(name=source_dto.name).one()  # type: Plugin
                lookup_kwargs = {'source': source_dto.type, 'plugin': plugin,
                                 'external_id': external_id,
                                 'physical_quantity': physical_quantity,
                                 'unit': unit}
            else:
                raise ValueError('Can\'t register Sensor with source {}'.format(source_dto.type))
            sensor = db.query(Sensor).filter_by(**lookup_kwargs).one_or_none()  # type: Optional[Sensor]
            if sensor is None:
                sensor = Sensor(id=get_sensor_orm_id(db, source_dto.type), **lookup_kwargs)
                db.add(sensor)
                changed = True
                for field in ('name',):
                    setattr(sensor, field, default_config.get(field, ''))
            db.commit()
            sensor_dto = self.load_sensor(sensor.id)
        if changed:
            self._publish_config()
        return sensor_dto

    def _create_or_update_sensor(self, db, sensor_dto):  # type: (Any, SensorDTO) -> Tuple[Sensor, bool]
        changed = False
        if sensor_dto.id:
            sensor = SensorMapper(db).dto_to_orm(sensor_dto)
        else:
            if 'physical_quantity' in sensor_dto.loaded_fields and 'external_id' in sensor_dto.loaded_fields:
                sensor = db.query(Sensor) \
                    .filter_by(source=Sensor.Sources.MASTER,
                               external_id=sensor_dto.external_id,
                               physical_quantity=sensor_dto.physical_quantity) \
                    .one_or_none()
            if sensor is None:
                sensor = db.query(Sensor) \
                    .filter_by(source=Sensor.Sources.MASTER,
                               external_id=sensor_dto.external_id,
                               physical_quantity=None) \
                    .first()
            if sensor:
                sensor_dto.id = sensor.id
                sensor = SensorMapper(db).dto_to_orm(sensor_dto)
            if sensor is None and sensor_dto.source:
                if 'room' in sensor_dto.loaded_fields and sensor_dto.room is not None:
                    room = db.query(Room).filter_by(number=sensor_dto.room).one()
                else:
                    query = (Sensor.source == sensor_dto.source.type) \
                        & (Sensor.external_id == sensor_dto.external_id) \
                        & (Sensor.room != None)
                    sensor = db.query(Sensor).where(query).first()
                    if sensor:
                        room = sensor.room
                    else:
                        room = None
                sensor = Sensor(id=get_sensor_orm_id(db, sensor_dto.source.type),
                                source=sensor_dto.source.type,
                                external_id=sensor_dto.external_id,
                                physical_quantity=sensor_dto.physical_quantity,
                                unit=sensor_dto.unit,
                                name=sensor_dto.name,
                                in_use=sensor_dto.in_use or True,
                                room=room)
                db.add(sensor)
        if sensor.source == Sensor.Sources.MASTER and sensor.id > 200:
            db.rollback()
            db.query(Sensor).filter_by(id=sensor.id).delete()
            db.commit()
            raise ValueError('Master sensor id {} out of range'.format(sensor.id))
        if sensor.source == Sensor.Sources.PLUGIN and sensor.id < 500:
            db.rollback()
            db.query(Sensor).filter_by(id=sensor.id).delete()
            db.commit()
            raise ValueError('Plugin sensor id {} is invalid'.format(sensor.id))
        if sensor in db.dirty:
            changed = True
        db.commit()  # explicit commit here because of id allocation
        return sensor, changed

    def get_sensors_status(self):  # type: () -> List[SensorStatusDTO]
        """ Get the current status of all sensors.
        """
        return list(self._status.values())

    def get_sensor_status(self, sensor_id):  # type: (int) -> Optional[SensorStatusDTO]
        """ Get the current status of a sensor.
        """
        return self._status.get(sensor_id)

    def set_sensor_status(self, status_dto):  # type: (SensorStatusDTO) -> SensorStatusDTO
        """ Update the current status of a (non master) sensor.
        """
        if status_dto.id < 200:
            raise ValueError('Sensor %s status is readonly' % status_dto.id)
        self._handle_status(status_dto)
        return status_dto

    def set_virtual_sensor(self, sensor_id, temperature, humidity, brightness):
        """ Set the temperature, humidity and brightness value of a (master) virtual sensor. """
        self._master_controller.set_virtual_sensor(sensor_id, temperature, humidity, brightness)

    def _translate_legacy_statuses(self, physical_quantity):  # type: (str) -> List[Optional[float]]
        with Database.get_session() as db:
            sensors = db.query(Sensor) \
                .filter_by(physical_quantity=physical_quantity,
                           source=Sensor.Sources.MASTER) \
                .all()
        try:
            sensor_count = max(s.id for s in sensors) + 1
        except ValueError:
            sensor_count = 0
        values = [None] * sensor_count  # type: List[Optional[float]]
        for sensor in sensors:
            status_dto = self._status.get(sensor.id)
            values[sensor.id] = status_dto.value if status_dto is not None else None
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


def get_sensor_orm_id(db, source):
    if source == Sensor.Sources.PLUGIN:
        # Plugins sensors use 510 or auto increment
        if db.query(Sensor).where(Sensor.id > 255).count() == 0:
            return 510
    if source == Sensor.Sources.MASTER:
        # Master sensors use 1-200
        value = db.query(func.max(Sensor.id)) \
            .where(Sensor.source == Sensor.Sources.MASTER) \
            .where(Sensor.id < 200) \
            .scalar()
        return (value or 0) + 1
    return None
