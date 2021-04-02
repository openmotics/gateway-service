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
ShutterGroup DTO
"""
from gateway.dto.base import BaseDTO, capture_fields

if False:  # MYPY
    from typing import Optional


class ShutterGroupDTO(BaseDTO):
    @capture_fields
    def __init__(self, id, timer_up=None, timer_down=None, room=None):
        self.id = id  # type: int
        self.timer_up = timer_up  # type: Optional[int]
        self.timer_down = timer_down  # type: Optional[int]
        self.room = room  # type: Optional[int]

    def __eq__(self, other):
        if not isinstance(other, ShutterGroupDTO):
            return False
        return (self.id == other.id and
                self.timer_up == other.timer_up and
                self.timer_down == other.timer_down and
                self.room == other.room)
