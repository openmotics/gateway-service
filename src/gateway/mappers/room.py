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
Room Mapper
"""
from __future__ import absolute_import
from gateway.dto.room import RoomDTO
from gateway.models import Room

if False:  # MYPY
    from typing import List


class RoomMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):  # type: (Room) -> RoomDTO
        return RoomDTO(id=orm_object.number,
                       name=orm_object.name)

    @staticmethod
    def dto_to_orm(room_dto):  # type: (RoomDTO) -> Room
        room = Room.get_or_none(number=room_dto.id)
        if room is None:
            room = Room(number=room_dto.id)
        if 'name' in room_dto.loaded_fields:
            room.name = room_dto.name
        return room
