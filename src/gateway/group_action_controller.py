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
GroupAction BLL
"""
from __future__ import absolute_import
import logging
from ioc import Injectable, Inject, INJECTED, Singleton
from gateway.base_controller import BaseController, SyncStructure
from gateway.dto import GroupActionDTO
from gateway.models import GroupAction

if False:  # MYPY
    from typing import List, Tuple

logger = logging.getLogger("openmotics")


@Injectable.named('group_action_controller')
@Singleton
class GroupActionController(BaseController):

    SYNC_STRUCTURES = [SyncStructure(GroupAction, 'output')]

    @Inject
    def __init__(self, master_controller=INJECTED):
        super(GroupActionController, self).__init__(master_controller)

    def do_group_action(self, group_action_id):  # type: (int) -> None
        self._master_controller.do_group_action(group_action_id)

    def load_group_action(self, group_action_id):  # type: (int) -> GroupActionDTO
        group_action = GroupAction.get(number=group_action_id)  # type: GroupAction
        group_action_dto = self._master_controller.load_group_action(group_action_id=group_action.number)
        return group_action_dto

    def load_group_actions(self):  # type: () -> List[GroupActionDTO]
        group_action_dtos = []
        for group_action in GroupAction.select():
            group_action_dto = self._master_controller.load_group_action(group_action_id=group_action.number)
            group_action_dtos.append(group_action_dto)
        return group_action_dtos

    def save_group_actions(self, group_actions):  # type: (List[Tuple[GroupActionDTO, List[str]]]) -> None
        group_actions_to_save = []
        for group_action_dto, fields in group_actions:
            group_action = GroupAction.get_or_none(number=group_action_dto.id)  # type: GroupAction
            if group_action is None:
                continue
            group_actions_to_save.append((group_action_dto, fields))
        self._master_controller.save_group_actions(group_actions_to_save)
