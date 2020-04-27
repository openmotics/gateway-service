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
Room DTO
"""
from gateway.dto.base import BaseDTO
from gateway.dto.floor import FloorDTO

if False:  # MYPY
    from typing import Optional


class RoomDTO(BaseDTO):
    def __init__(self, id, name=None, floor=None):
        self.id = id  # type: int
        self.name = name  # type: Optional[str]
        self.floor = floor  # type: Optional[FloorDTO]

    def __eq__(self, other):
        if not isinstance(other, RoomDTO):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.floor == other.floor)

    @property
    def in_use(self):
        return ((self.name is not None and self.name != '') or
                self.floor is not None)
