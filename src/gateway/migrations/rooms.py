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
from toolbox import Toolbox
from ioc import INJECTED, Inject
from gateway.models import Feature, Output, Room, Floor
from gateway.orm_syncer import ORMSyncer
from platform_utils import Platform

if False:  # MYPY
    from typing import Dict
    from gateway.hal.master_controller_classic import MasterClassicController

logger = logging.getLogger('openmotics')


class RoomsMigrator(object):

    @staticmethod
    @Inject
    def migrate(master_controller=INJECTED):  # type: (MasterClassicController) -> None
        try:
            # Check if migration already done
            feature = Feature.get_or_none(name='orm_rooms')
            if feature is None:
                feature = Feature(name='orm_rooms',
                                  enabled=False)
            if not feature.enabled:
                # Core(+) platforms never had non-ORM rooms
                if Platform.get_platform() != Platform.Type.CLASSIC:
                    feature.enabled = True
                    feature.save()
                    return

                # Sync
                ORMSyncer.sync()

                # Import legacy code
                from master.classic.eeprom_models import OutputConfiguration, RoomConfiguration, FloorConfiguration

                rooms = {}  # type: Dict[int, Room]
                floors = {}  # type: Dict[int, Floor]

                # Rooms and floors
                for room_classic_orm in master_controller._eeprom_controller.read_all(RoomConfiguration):
                    if room_classic_orm.name == '' and room_classic_orm.floor == 255:
                        continue
                    room_id = room_classic_orm.id
                    room = RoomsMigrator._get_or_create_room(master_controller, room_id, rooms, floors)
                    rooms[room_id] = room

                # Outputs
                for output_classic_orm in master_controller._eeprom_controller.read_all(OutputConfiguration):
                    output_id = output_classic_orm.id
                    room_id = output_classic_orm.room
                    output_orm, _ = Output.get_or_create(number=output_id)
                    if room_id == 255:
                        output_orm.room = None
                    else:
                        output_orm.room = rooms.setdefault(room_id, RoomsMigrator._get_or_create_room(master_controller, room_id, rooms, floors))
                    output_orm.save()

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
