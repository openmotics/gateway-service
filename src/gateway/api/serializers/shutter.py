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
Shutter (de)serializer
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import ShutterDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class ShutterSerializer(object):
    WORD_MAX = 2 ** 16 - 1
    BYTE_MAX = 255

    @staticmethod
    def serialize(shutter_dto, fields):  # type: (ShutterDTO, Optional[List[str]]) -> Dict
        data = {'id': shutter_dto.id,
                'name': shutter_dto.name,
                'timer_up': Toolbox.denonify(shutter_dto.timer_up, ShutterSerializer.BYTE_MAX),
                'timer_down': Toolbox.denonify(shutter_dto.timer_down, ShutterSerializer.BYTE_MAX),
                'up_down_config': Toolbox.denonify(shutter_dto.up_down_config, ShutterSerializer.BYTE_MAX),
                'group_1': Toolbox.denonify(shutter_dto.group_1, ShutterSerializer.BYTE_MAX),
                'group_2': Toolbox.denonify(shutter_dto.group_2, ShutterSerializer.BYTE_MAX),
                'room': Toolbox.denonify(shutter_dto.room, ShutterSerializer.BYTE_MAX),
                'steps': Toolbox.denonify(shutter_dto.steps, ShutterSerializer.WORD_MAX),
                'in_use': shutter_dto.in_use}
        if shutter_dto.module is not None:
            data.update({'module': {'hardware_type': shutter_dto.module.hardware_type,
                                    'hardware_module': shutter_dto.module.module_type,
                                    'module_id': shutter_dto.module.order}})
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> ShutterDTO
        shutter_dto = ShutterDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=shutter_dto,  # Referenced
            api_data=api_data,
            mapping={'name': ('name', None),
                     'in_use': ('in_use', None),
                     'timer_up': ('timer_up', ShutterSerializer.BYTE_MAX),
                     'timer_down': ('timer_down', ShutterSerializer.BYTE_MAX),
                     'up_down_config': ('up_down_config', ShutterSerializer.BYTE_MAX),
                     'group_1': ('group_1', ShutterSerializer.BYTE_MAX),
                     'group_2': ('group_2', ShutterSerializer.BYTE_MAX),
                     'room': ('room', ShutterSerializer.BYTE_MAX),
                     'steps': ('steps', ShutterSerializer.WORD_MAX)}
        )
        return shutter_dto
