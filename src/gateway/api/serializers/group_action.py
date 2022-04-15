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
GroupAction (de)serializer
"""
from __future__ import absolute_import
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import GroupActionDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class GroupActionSerializer(object):
    WORD_MAX = 2 ** 16 - 1
    BYTE_MAX = 255

    @staticmethod
    def serialize(group_action_dto, fields):  # type: (GroupActionDTO, Optional[List[str]]) -> Dict
        data = {'id': group_action_dto.id,
                'name': group_action_dto.name,
                'actions': ','.join([str(action) for action in group_action_dto.actions]),
                'internal': group_action_dto.internal,
                'show_in_app': group_action_dto.show_in_app}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> GroupActionDTO
        group_action_dto = GroupActionDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=group_action_dto,  # Referenced
            api_data=api_data,
            mapping={'name': ('name', None),
                     'actions': ('actions', lambda s: [] if s == '' else [int(a) for a in s.split(',')]),
                     'show_in_app': ('show_in_app', True)}
        )
        return group_action_dto
