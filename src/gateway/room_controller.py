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
Room BLL
"""
from __future__ import absolute_import

import logging
from gateway.dto import RoomDTO
from gateway.mappers import RoomMapper
from gateway.models import Database, Room
from ioc import Injectable, Singleton

if False:  # MYPY
    from typing import List, Tuple

logger = logging.getLogger(__name__)


@Injectable.named('room_controller')
@Singleton
class RoomController(object):
    def __init__(self):
        pass

    def load_room(self, room_id):  # type: (int) -> RoomDTO
        with Database.get_session() as db:
            room = db.query(Room).where(Room.number == room_id).one()
            room_dto = RoomMapper(db).orm_to_dto(room)
        return room_dto

    def load_rooms(self):  # type: () -> List[RoomDTO]
        room_dtos = []
        with Database.get_session() as db:
            rooms = db.query(Room).all()
            for room in  rooms:
                room_dtos.append(RoomMapper(db).orm_to_dto(room))
        return room_dtos

    def save_rooms(self, rooms):  # type: (List[RoomDTO]) -> None
        with Database.get_session() as db:
            rooms_to_add = []
            rooms_to_delete = []
            for room_dto in rooms:
                if room_dto.in_use:
                    rooms_to_add.append(RoomMapper(db).dto_to_orm(room_dto))
                else:
                    rooms_to_delete.append(room_dto.id)
            db.add_all(rooms_to_add)
            db.query(Room).where(Room.number.in_(rooms_to_delete)).delete()
            db.commit()
