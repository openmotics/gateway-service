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
Room (de)serializer
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import RoomDTO, FloorDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class RoomSerializer(object):

    @staticmethod
    def serialize(room_dto, fields):  # type: (RoomDTO, Optional[List[str]]) -> Dict
        data = {'id': room_dto.id,
                'name': room_dto.name,
                'floor': None if room_dto.floor is None else room_dto.floor.id}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> Tuple[RoomDTO, List[str]]
        loaded_fields = ['id']
        room_dto = RoomDTO(id=api_data['id'])
        loaded_fields += SerializerToolbox.deserialize(
            dto=room_dto,  # Referenced
            api_data=api_data,
            mapping={'name': ('name', None)}
        )
        if 'floor' in api_data:
            loaded_fields.append('floor')
            room_dto.floor = FloorDTO(id=api_data['floor'])
        return room_dto, loaded_fields
