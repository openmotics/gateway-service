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
Shutter DTO
"""
if False:  # MYPY
    from typing import Optional


class ShutterDTO(object):
    def __init__(self, id, name='', timer_up=None, timer_down=None, up_down_config=None,
                 group_1=None, group_2=None, room=None, steps=None):
        self.id = id  # type: int
        self.name = name  # type: str
        self.timer_up = timer_up  # type: Optional[int]
        self.timer_down = timer_down  # type: Optional[int]
        self.up_down_config = up_down_config  # type: Optional[int]
        self.group_1 = group_1  # type: Optional[int]
        self.group_2 = group_2  # type: Optional[int]
        self.room = room  # type: Optional[int]
        self.steps = steps  # type: Optional[int]

    def __eq__(self, other):
        if not isinstance(other, ShutterDTO):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.timer_up == other.timer_up and
                self.timer_down == other.timer_down and
                self.up_down_config == other.up_down_config and
                self.group_1 == other.group_1 and
                self.group_2 == other.group_2 and
                self.room == other.room and
                self.steps == other.steps)
