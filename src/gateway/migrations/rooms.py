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

import os
import logging
import constants
from toolbox import Toolbox
from ioc import INJECTED, Inject
from gateway.models import (
    Feature, Output, Room, Floor, Input, Sensor,
    ShutterGroup, Shutter, PulseCounter
)
from master.orm_syncer import ORMSyncer
from platform_utils import Platform

if False:  # MYPY
    from typing import Dict, Optional
    from gateway.hal.master_controller_classic import MasterClassicController

logger = logging.getLogger('openmotics')


class RoomsMigrator(object):

    @staticmethod
    @Inject
    def migrate(master_controller=INJECTED, sync=True):  # type: (MasterClassicController, bool) -> None
        try:
            # Check if migration already done
            feature = Feature.get_or_none(name='orm_rooms')
            if feature is None:
                feature = Feature(name='orm_rooms',
                                  enabled=False)
            if feature.enabled:
                return

            # Core(+) platforms never had non-ORM rooms
            if Platform.get_platform() != Platform.Type.CLASSIC:
                feature.enabled = True
                feature.save()
                return

            # Sync
            if sync:
                ORMSyncer.sync()

            # Import legacy code
            from master.classic.eeprom_models import (
                OutputConfiguration, RoomConfiguration, FloorConfiguration,
                InputConfiguration, SensorConfiguration, ShutterConfiguration,
                ShutterGroupConfiguration, PulseCounterConfiguration
            )

            rooms = {}  # type: Dict[int, Room]
            floors = {}  # type: Dict[int, Floor]

            # Rooms and floors
            for room_classic_orm in master_controller._eeprom_controller.read_all(RoomConfiguration):
                if room_classic_orm.name == '' and room_classic_orm.floor == 255:
                    continue
                room_id = room_classic_orm.id
                room = RoomsMigrator._get_or_create_room(master_controller, room_id, rooms, floors)
                rooms[room_id] = room

            # Main objects
            for eeprom_model, orm_model, filter_ in [(OutputConfiguration, Output, lambda o: True),
                                                     (InputConfiguration, Input, lambda i: i.module_type in ['i', 'I']),
                                                     (SensorConfiguration, Sensor, lambda s: True),
                                                     (ShutterConfiguration, Shutter, lambda s: True),
                                                     (ShutterGroupConfiguration, ShutterGroup, lambda s: True)]:
                for classic_orm in master_controller._eeprom_controller.read_all(eeprom_model):
                    if not filter_(classic_orm):
                        continue
                    object_id = classic_orm.id
                    room_id = classic_orm.room  # type: ignore
                    object_orm, _ = orm_model.get_or_create(number=object_id)  # type: ignore
                    if room_id == 255:
                        object_orm.room = None
                    else:
                        object_orm.room = rooms.setdefault(room_id, RoomsMigrator._get_or_create_room(master_controller, room_id, rooms, floors))
                    object_orm.save()

            # PulseCounters
            pulse_counter = None  # type: Optional[PulseCounter]
            # - Master
            for pulse_counter_classic_orm in master_controller._eeprom_controller.read_all(PulseCounterConfiguration):
                pulse_counter_id = pulse_counter_classic_orm.id
                room_id = pulse_counter_classic_orm.room
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
                    pulse_counter.room = rooms.setdefault(room_id, RoomsMigrator._get_or_create_room(master_controller, room_id, rooms, floors))
                pulse_counter.save()
            # - Old SQLite3
            old_sqlite_db = constants.get_pulse_counter_database_file()
            if os.path.exists(old_sqlite_db):
                import sqlite3
                connection = sqlite3.connect(old_sqlite_db,
                                             detect_types=sqlite3.PARSE_DECLTYPES,
                                             check_same_thread=False,
                                             isolation_level=None)
                cursor = connection.cursor()
                for row in cursor.execute('SELECT id, name, room, persistent FROM pulse_counters ORDER BY id ASC;'):
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
                        pulse_counter.room = rooms.setdefault(room_id, RoomsMigrator._get_or_create_room(master_controller, room_id, rooms, floors))
                    pulse_counter.save()
                os.rename(old_sqlite_db, '{0}.bak'.format(old_sqlite_db))

            # Migration complete
            feature.enabled = True
            feature.save()
        except Exception:
            logger.exception('Error migrating rooms')

    @staticmethod
    def _get_or_create_room(master_controller, room_id, rooms, floors):  # type: (MasterClassicController, int, Dict[int, Room], Dict[int, Floor]) -> Room
        from master.classic.eeprom_models import RoomConfiguration

        if room_id not in rooms:
            room, created = Room.get_or_create(number=room_id)
            if created:
                room_classic_orm = master_controller._eeprom_controller.read(RoomConfiguration, room_id)  # type: RoomConfiguration
                room.name = Toolbox.nonify(room_classic_orm.name, '')
                if room_classic_orm.floor == 255:
                    room.floor = None
                else:
                    room.floor = RoomsMigrator._get_or_create_floor(master_controller, room_classic_orm.floor, floors)
                room.save()
            rooms[room_id] = room
        return rooms[room_id]

    @staticmethod
    def _get_or_create_floor(master_controller, floor_id, floors):  # type: (MasterClassicController, int, Dict[int, Floor]) -> Floor
        from master.classic.eeprom_models import FloorConfiguration

        if floor_id not in floors:
            floor, created = Floor.get_or_create(number=floor_id)
            if created:
                floor_classic_orm = master_controller._eeprom_controller.read(FloorConfiguration, floor_id)  # type: FloorConfiguration
                floor.name = Toolbox.nonify(floor_classic_orm.name, '')
                floor.save()
            floors[floor_id] = floor
        return floors[floor_id]
