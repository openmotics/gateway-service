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

import logging
import os

import constants
from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import Feature, Floor, Input, Output, PulseCounter, Room, \
    Sensor, Shutter, ShutterGroup
from ioc import INJECTED, Inject
from platform_utils import Platform

if False:  # MYPY
    from typing import Any, Callable, Dict, List, Optional, Tuple, Type
    from gateway.hal.master_controller_classic import MasterClassicController
    from master.classic.eeprom_controller import EepromModel
    from master.classic.eeprom_extension import EepromExtension
    from master.models import BaseModel

logger = logging.getLogger(__name__)


class RoomsMigrator(BaseMigrator):

    MIGRATION_KEY = 'rooms'

    @classmethod
    @Inject
    def _migrate(cls, master_controller=INJECTED):  # type: (MasterClassicController) -> None
        # Core(+) platforms never had non-ORM rooms
        if Platform.get_platform() in Platform.CoreTypes:
            return

        # Import legacy code
        @Inject
        def _load_eeprom_extension(eeprom_extension=INJECTED):
            # type: (EepromExtension) -> EepromExtension
            return eeprom_extension

        eext_controller = _load_eeprom_extension()
        from master.classic.eeprom_models import (
            OutputConfiguration, InputConfiguration, SensorConfiguration, ShutterConfiguration,
            ShutterGroupConfiguration, PulseCounterConfiguration
        )

        rooms = {}  # type: Dict[int, Room]
        floors = {}  # type: Dict[int, Floor]

        # Rooms and floors
        logger.info('* Rooms & floors')
        for room_id in range(100):
            try:
                RoomsMigrator._get_or_create_room(eext_controller, room_id, rooms, floors, skip_empty=True)
            except Exception:
                logger.exception('Could not migrate single RoomConfiguration')

        # Main objects
        items = [
            (OutputConfiguration, Output, lambda o: True),
            (InputConfiguration, Input, lambda i: i.module_type in ['i', 'I']),
            (SensorConfiguration, Sensor, lambda s: True),
            (ShutterConfiguration, Shutter, lambda s: True),
            (ShutterGroupConfiguration, ShutterGroup, lambda s: True)
        ]  # type: List[Tuple[Type[EepromModel], Type[BaseModel], Callable[[Any],bool]]]
        for eeprom_model, orm_model, filter_ in items:
            logger.info('* {0}s'.format(eeprom_model.__name__))
            try:
                for classic_orm in master_controller._eeprom_controller.read_all(eeprom_model):
                    try:
                        object_id = classic_orm.id
                        if object_id is None:
                            continue
                        if not filter_(classic_orm):
                            RoomsMigrator._delete_eext_fields(eext_controller, eeprom_model.__name__, object_id, ['room'])
                            continue
                        try:
                            room_id = int(RoomsMigrator._read_eext_fields(eext_controller, eeprom_model.__name__, object_id, ['room']).get('room', 255))
                        except ValueError:
                            room_id = 255
                        if orm_model in (Sensor,):
                            object_orm, _ = orm_model.get_or_create(source='master',
                                                                    external_id=str(object_id),
                                                                    defaults={'name': ''})
                        else:
                            object_orm, _ = orm_model.get_or_create(number=object_id)
                        if room_id == 255:
                            object_orm.room = None
                        else:
                            object_orm.room = RoomsMigrator._get_or_create_room(eext_controller, room_id, rooms, floors)
                        object_orm.save()
                        RoomsMigrator._delete_eext_fields(eext_controller, eeprom_model.__name__, object_id, ['room'])
                    except Exception:
                        logger.exception('Could not migrate single {0}'.format(eeprom_model.__name__))
            except Exception:
                logger.exception('Could not migrate {0}s'.format(eeprom_model.__name__))

        # PulseCounters
        pulse_counter = None  # type: Optional[PulseCounter]
        # - Master
        try:
            logger.info('* PulseCounters (master)')
            for pulse_counter_classic_orm in master_controller._eeprom_controller.read_all(PulseCounterConfiguration):
                try:
                    pulse_counter_id = pulse_counter_classic_orm.id
                    try:
                        room_id = int(RoomsMigrator._read_eext_fields(eext_controller, 'PulseCounterConfiguration', pulse_counter_id, ['room']).get('room', 255))
                    except ValueError:
                        room_id = 255
                    pulse_counter = PulseCounter.get_or_none(number=pulse_counter_id)
                    if pulse_counter is None:
                        pulse_counter = PulseCounter(number=pulse_counter_id,
                                                     name=pulse_counter_classic_orm.name,
                                                     persistent=False,
                                                     source=u'master')
                    else:
                        pulse_counter.name = pulse_counter_classic_orm.name
                        pulse_counter.persistent = False
                        pulse_counter.source = u'master'
                    if room_id == 255:
                        pulse_counter.room = None
                    else:
                        pulse_counter.room = RoomsMigrator._get_or_create_room(eext_controller, room_id, rooms, floors)
                    pulse_counter.save()
                    RoomsMigrator._delete_eext_fields(eext_controller, 'PulseCounterConfiguration', pulse_counter_id, ['room'])
                except Exception:
                    logger.exception('Could not migrate classic master PulseCounter')
        except Exception:
            logger.exception('Could not migrate classic master PulseCounters')
        # - Old SQLite3
        old_sqlite_db = constants.get_pulse_counter_database_file()
        if os.path.exists(old_sqlite_db):
            try:
                logger.info('* PulseCounters (gateway)')
                import sqlite3
                connection = sqlite3.connect(old_sqlite_db,
                                             detect_types=sqlite3.PARSE_DECLTYPES,
                                             check_same_thread=False,
                                             isolation_level=None)
                cursor = connection.cursor()
                for row in cursor.execute('SELECT id, name, room, persistent FROM pulse_counters ORDER BY id ASC;'):
                    try:
                        pulse_counter_id = int(row[0])
                        room_id = int(row[2])
                        pulse_counter = PulseCounter.get_or_none(number=pulse_counter_id)
                        if pulse_counter is None:
                            pulse_counter = PulseCounter(number=pulse_counter_id,
                                                         name=str(row[1]),
                                                         persistent=row[3] >= 1,
                                                         source=u'gateway')
                        else:
                            pulse_counter.name = str(row[1])
                            pulse_counter.persistent = row[3] >= 1
                            pulse_counter.source = u'gateway'
                        if room_id == 255:
                            pulse_counter.room = None
                        else:
                            pulse_counter.room = RoomsMigrator._get_or_create_room(eext_controller, room_id, rooms, floors)
                        pulse_counter.save()
                    except Exception:
                        logger.exception('Could not migratie gateway PulseCounter')
                os.rename(old_sqlite_db, '{0}.bak'.format(old_sqlite_db))
            except Exception:
                logger.exception('Could not migrate gateway PulseCounters')

    @staticmethod
    def _get_or_create_room(eext_controller, room_id, rooms, floors, skip_empty=False):
        # type: (EepromExtension, int, Dict[int, Room], Dict[int, Floor], bool) -> Optional[Room]
        if room_id not in rooms:
            room = Room.get_or_none(number=room_id)
            if room is None:
                room_data = RoomsMigrator._read_eext_fields(eext_controller, 'RoomConfiguration', room_id, ['floor', 'name'])
                name = room_data.get('name', '')
                try:
                    floor_id = int(room_data.get('floor', 255))
                except ValueError:
                    floor_id = 255
                if skip_empty and name == '' and floor_id == 255:
                    return None
                room = Room(number=room_id,
                            name=name)
                if floor_id != 255:
                    room.floor = RoomsMigrator._get_or_create_floor(eext_controller, floor_id, floors)
                room.save()
                RoomsMigrator._delete_eext_fields(eext_controller, 'RoomConfiguration', room_id, ['floor', 'name'])
            rooms[room_id] = room
        return rooms[room_id]

    @staticmethod
    def _get_or_create_floor(eext_controller, floor_id, floors):
        # type: (EepromExtension, int, Dict[int, Floor]) -> Floor
        if floor_id not in floors:
            floor = Floor.get_or_none(number=floor_id)
            if floor is None:
                name = RoomsMigrator._read_eext_fields(eext_controller, 'FloorConfiguration', floor_id, ['name']).get('name', '')
                floor = Floor(number=floor_id,
                              name=name)
                floor.save()
                RoomsMigrator._delete_eext_fields(eext_controller, 'FloorConfiguration', floor_id, ['name'])
            floors[floor_id] = floor
        return floors[floor_id]

    @staticmethod
    def _read_eext_fields(eext_controller, model_name, model_id, fields):
        # type: (EepromExtension, str, int, List[str]) -> Dict[str, Any]
        data = {}
        for field in fields:
            value = eext_controller.read_data(model_name, model_id, field)
            if value is not None:
                data[field] = value
        return data

    @staticmethod
    def _delete_eext_fields(eext_controller, model_name, model_id, fields):
        # type: (EepromExtension, str, int, List[str]) -> None
        for field in fields:
            eext_controller.delete_data(model_name, model_id, field)
