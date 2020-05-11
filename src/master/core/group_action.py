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
Contains Group Action related code
"""

from __future__ import absolute_import
from master.core.memory_models import GroupActionAllocationTable, GroupActionConfiguration, GroupActionBasicAction

if False:  # MYPY
    from typing import List
    from master.core.basic_action import BasicAction


class GroupAction(object):
    def __init__(self, id, name='', actions=None):  # type: (int, str, List[BasicAction]) -> None
        self.id = id  # type: int
        self.name = name  # type: str
        self.actions = [] if actions is None else actions  # type: List[BasicAction]

    @property
    def in_use(self):  # type: () -> bool
        return len(self.actions) > 0


class GroupActionController(object):

    @staticmethod
    def load_group_actions():  # type: () -> List[GroupAction]
        group_actions = []
        for i in range(255):
            group_actions.append(GroupActionController.load_group_action(group_action_id=i))
        return group_actions

    @staticmethod
    def load_group_action(group_action_id):  # type: (int) -> GroupAction
        if not (0 <= group_action_id <= 254):
            # There are only 255 GroupActions, not 256
            raise ValueError('GroupAction ID {0} not in range 0 <= id <= 254'.format(group_action_id))

        group_action_configuration = GroupActionConfiguration(group_action_id)
        gat = GroupActionAllocationTable(None)
        if group_action_id < 127:
            start_address = gat.addresses_0[group_action_id]
            end_address = gat.addresses_0[group_action_id + 1]
        elif group_action_id == 127:
            start_address = gat.addresses_0[group_action_id]
            end_address = gat.addresses_1[0]
        else:  # group_action_id <= 254:
            start_address = gat.addresses_0[group_action_id - 128]
            end_address = gat.addresses_0[group_action_id - 128 + 1]

        basic_actions = []
        for address in range(start_address, end_address):
            basic_action = GroupActionBasicAction(address).basic_action
            if not basic_action.in_use:
                break
            basic_actions.append(basic_action)
        return GroupAction(id=group_action_id,
                           name=group_action_configuration.name,
                           actions=basic_actions)

    @staticmethod
    def save_group_action(group_action, fields):  # type: (GroupAction, List[str]) -> None
        if 'name' in fields:
            group_action_configuration = GroupActionConfiguration(group_action.id)
            group_action_configuration.name = group_action.name
            group_action_configuration.save()
        if 'actions' in fields:
            # TODO: A change request was made (FIR-16) to use explicit end addresses
            pass
