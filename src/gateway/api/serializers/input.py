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
Input (de)serializer
"""
from __future__ import absolute_import

from gateway.dto.input import InputStatusDTO
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import InputDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class InputSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(input_dto, fields):  # type: (InputDTO, Optional[List[str]]) -> Dict
        data = {'id': input_dto.id,
                'module_type': input_dto.module_type,
                'name': input_dto.name,
                'action': Toolbox.denonify(input_dto.action, InputSerializer.BYTE_MAX),
                'basic_actions': ','.join([str(action) for action in input_dto.basic_actions]),
                'invert': 0 if input_dto.invert else 255,
                'room': Toolbox.denonify(input_dto.room, InputSerializer.BYTE_MAX),
                'can': 'C' if input_dto.can else ' ',
                'event_enabled': input_dto.event_enabled}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> InputDTO
        input_dto = InputDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=input_dto,  # Referenced
            api_data=api_data,
            mapping={'module_type': ('module_type', None),
                     'name': ('name', None),
                     'action': ('action', InputSerializer.BYTE_MAX),
                     'basic_actions': ('basic_actions', lambda s: [] if s == '' else [int(a) for a in s.split(',')]),
                     'invert': ('invert', lambda i: i != 255),
                     'can': ('can', lambda s: s == 'C'),
                     'event_enabled': ('event_enabled', None),
                     'room': ('room', InputSerializer.BYTE_MAX)}
        )
        return input_dto


class InputStateSerializer(object):
    @staticmethod
    def serialize(input_state_dto, fields):
        # type: (InputStatusDTO, Optional[List[str]]) -> Dict
        data = {'id': input_state_dto.id,
                'status': 1 if input_state_dto.status else 0}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict) -> InputStatusDTO
        input_state_dto = InputStatusDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=input_state_dto,  # Referenced
            api_data=api_data,
            mapping={'status': ('status', bool)}
        )
        return input_state_dto
