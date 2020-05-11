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
GroupAction Mapper
"""
from __future__ import absolute_import
from gateway.dto import GroupActionDTO
from master.core.group_action import GroupAction
from master.core.basic_action import BasicAction

if False:  # MYPY
    from typing import List, Dict, Any


class GroupActionMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (GroupAction) -> GroupActionDTO
        return GroupActionDTO(id=orm_object.id,
                              name=orm_object.name,
                              actions=GroupActionMapper.core_actions_to_classic_actions(orm_object.actions))

    @staticmethod
    def dto_to_orm(group_action_dto, fields):  # type: (GroupActionDTO, List[str]) -> GroupAction
        data = {'id': group_action_dto.id}  # type: Dict[str, Any]
        for dto_field, data_field in {'name': 'name'}.items():
            if dto_field in fields:
                data[data_field] = getattr(group_action_dto, dto_field)
        if 'actions' in fields:
            data['actions'] = GroupActionMapper.classic_actions_to_core_actions(group_action_dto.actions)
        return GroupAction(**data)

    @staticmethod
    def core_actions_to_classic_actions(actions):  # type: (List[BasicAction]) -> List[int]
        classic_actions = []
        for action in actions:
            classic_actions += []
        return classic_actions

    @staticmethod
    def classic_actions_to_core_actions(classic_actions):  # type: (List[int]) -> List[BasicAction]
        actions = []
        for classic_action in classic_actions:
            pass
        return actions
