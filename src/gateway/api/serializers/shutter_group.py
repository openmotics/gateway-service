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
ShutterGroup (de)serializer
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import ShutterGroupDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class ShutterGroupSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(shutter_group_dto, fields):  # type: (ShutterGroupDTO, Optional[List[str]]) -> Dict
        data = {'id': shutter_group_dto.id,
                'timer_up': Toolbox.denonify(shutter_group_dto.timer_up, ShutterGroupSerializer.BYTE_MAX),
                'timer_down': Toolbox.denonify(shutter_group_dto.timer_down, ShutterGroupSerializer.BYTE_MAX),
                'room': Toolbox.denonify(shutter_group_dto.room, ShutterGroupSerializer.BYTE_MAX),
                'in_use': shutter_group_dto.in_use}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> ShutterGroupDTO
        shutter_group_dto = ShutterGroupDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=shutter_group_dto,  # Referenced
            api_data=api_data,
            mapping={'timer_up': ('timer_up', ShutterGroupSerializer.BYTE_MAX),
                     'timer_down': ('timer_down', ShutterGroupSerializer.BYTE_MAX),
                     'room': ('room', ShutterGroupSerializer.BYTE_MAX),
                     'in_use': ('in_use', None)}
        )
        return shutter_group_dto
