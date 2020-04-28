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
Input DTO
"""
from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Optional, List


class InputDTO(BaseDTO):
    def __init__(self, id, name='', module_type='I', action=None, basic_actions=None, invert=False, can=False, room=None, event_enabled=False):
        # The argument `basic_actions` is None since you should not set a reference type as default value
        self.id = id  # type: int
        self.name = name  # type: str
        self.module_type = module_type  # type: str
        self.room = room  # type: Optional[int]
        self.action = action  # type: Optional[int]
        self.basic_actions = [] if basic_actions is None else basic_actions  # type: List[int]
        self.invert = invert  # type: bool
        self.can = can  # type: bool
        self.event_enabled = event_enabled  # type: bool

    def __eq__(self, other):
        if not isinstance(other, InputDTO):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.module_type == other.module_type and
                self.room == other.room and
                self.action == other.action and
                self.basic_actions == other.basic_actions and
                self.invert == other.invert and
                self.can == other.can and
                self.event_enabled == other.event_enabled)
