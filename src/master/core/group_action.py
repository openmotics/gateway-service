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
import logging
from master.core.memory_models import GroupActionAddressConfiguration, GroupActionConfiguration, GroupActionBasicAction
from master.core.memory_types import MemoryActivator

if False:  # MYPY
    from typing import List, Dict, Optional
    from master.core.basic_action import BasicAction

logger = logging.getLogger(__name__)


class GroupAction(object):
    def __init__(self, id, name='', actions=None):  # type: (int, str, List[BasicAction]) -> None
        self.id = id  # type: int
        self.name = name  # type: str
        self.actions = [] if actions is None else actions  # type: List[BasicAction]

    @property
    def in_use(self):  # type: () -> bool
        return len(self.actions) > 0

    def __repr__(self):
        return 'GA({0},{1},[{2}])'.format(
            self.id, self.name, ','.join(repr(action) for action in self.actions)
        )

    def __eq__(self, other):
        if not isinstance(other, GroupAction):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.actions == other.actions)


class GroupActionController(object):
    MAX_WORD = 2 ** 16 - 1

    @staticmethod
    def get_unused_group_action():  # type: () -> Optional[GroupAction]
        for group_action in GroupActionController.load_group_actions():
            if not group_action.in_use:
                return group_action
        return None

    @staticmethod
    def load_group_actions():  # type: () -> List[GroupAction]
        group_actions = []
        for i in range(256):
            group_actions.append(GroupActionController.load_group_action(group_action_id=i))
        return group_actions

    @staticmethod
    def load_group_action(group_action_id):  # type: (int) -> GroupAction
        if not (0 <= group_action_id <= 255):
            raise ValueError('GroupAction ID {0} not in range 0 <= id <= 255'.format(group_action_id))

        group_action_configuration = GroupActionConfiguration(group_action_id)
        address_configuration = GroupActionAddressConfiguration(group_action_id)

        basic_actions = []
        if GroupActionController.MAX_WORD not in [address_configuration.start, address_configuration.end]:
            for address in range(address_configuration.start, address_configuration.end + 1):
                basic_action = GroupActionBasicAction(address).basic_action
                if not basic_action.in_use:
                    break
                basic_actions.append(basic_action)
        return GroupAction(id=group_action_id,
                           name=group_action_configuration.name,
                           actions=basic_actions)

    @staticmethod
    def save_group_action(group_action, fields, activate=True):  # type: (GroupAction, List[str], bool) -> None
        group_action_id = group_action.id
        if not (0 <= group_action_id <= 255):
            raise ValueError('GroupAction ID {0} not in range 0 <= id <= 255'.format(group_action_id))

        if 'actions' in fields:
            address_configuration = GroupActionAddressConfiguration(group_action_id)
            previous_length = address_configuration.end - address_configuration.start + 1
            if GroupActionController.MAX_WORD in [address_configuration.start, address_configuration.end]:
                previous_length = 0
            needed_length = len(group_action.actions)
            if needed_length == 0:
                # Empty, clear addresses
                address_configuration.start = GroupActionController.MAX_WORD
                address_configuration.end = GroupActionController.MAX_WORD
                address_configuration.save(activate=False)
            else:
                if needed_length == previous_length:
                    # No new location needed
                    start_address = address_configuration.start
                else:
                    # Different length, search for (better) location
                    free_space_map = GroupActionController._free_address_space_map(group_action_id)
                    found_length = None
                    for length in sorted(list(free_space_map.keys())):
                        if length >= needed_length:
                            found_length = length
                            break
                    if found_length is None:
                        logger.error('Insufficient storage saving GroupAction with {0} BAs: {1}'.format(needed_length, free_space_map))
                        raise RuntimeError('Cannot save GroupAction {0}. Insufficient storage'.format(group_action_id))
                    available_start_addresses = free_space_map[found_length]
                    if address_configuration.start in available_start_addresses:
                        start_address = address_configuration.start  # Prefer same location
                    else:
                        start_address = available_start_addresses[0]
                    address_configuration.start = start_address
                    address_configuration.end = start_address + needed_length - 1
                    address_configuration.save(activate=False)
                # Store BAs
                for i, new_action in enumerate(group_action.actions):
                    basic_action = GroupActionBasicAction(start_address + i)
                    basic_action.basic_action = new_action
                    basic_action.save(activate=False)
        if 'name' in fields:
            group_action_configuration = GroupActionConfiguration(group_action.id)
            group_action_configuration.name = group_action.name
            group_action_configuration.save(activate=False)

        if activate:
            MemoryActivator.activate()

    @staticmethod
    def _free_address_space_map(exclude_group_action_id=None):  # type: (Optional[int]) -> Dict[int, List[int]]
        free_addresses_set = set(range(4200))
        for i in range(256):
            if i == exclude_group_action_id:
                continue
            used_address_configuration = GroupActionAddressConfiguration(i)
            if GroupActionController.MAX_WORD not in [used_address_configuration.start,
                                                      used_address_configuration.end]:
                free_addresses_set -= set(range(used_address_configuration.start, used_address_configuration.end + 1))
        free_addresses = sorted(list(free_addresses_set))
        space_map = {}  # type: Dict[int, List[int]]
        length = start_address = last_address = 0
        for i in range(len(free_addresses)):
            address = free_addresses[i]
            if length == 0:
                # Empty sequence
                start_address = address
                length = 1
            elif address == last_address + 1:
                # Consecutive
                length += 1
            else:
                # Found a gap
                space_map.setdefault(length, []).append(start_address)
                start_address = address
                length = 1
            last_address = address
        if length > 0:
            space_map.setdefault(length, []).append(start_address)
        return space_map
