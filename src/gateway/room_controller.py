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
from peewee import JOIN
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
        _ = self
        room = Room.select(Room) \
                   .where(Room.number == room_id) \
                   .get()  # type: Room  # TODO: Load dict
        room_dto = RoomMapper.orm_to_dto(room)
        return room_dto

    def load_rooms(self):  # type: () -> List[RoomDTO]
        _ = self
        room_dtos = []
        for room in Room.select():  # TODO: Load dicts
            room_dtos.append(RoomMapper.orm_to_dto(room))
        return room_dtos

    def save_rooms(self, rooms):  # type: (List[RoomDTO]) -> None
        _ = self
        with Database.get_db().atomic():
            for room_dto in rooms:
                if room_dto.in_use:
                    room = RoomMapper.dto_to_orm(room_dto)
                    room.save()
                else:
                    Room.delete().where(Room.number == room_dto.id).execute()
