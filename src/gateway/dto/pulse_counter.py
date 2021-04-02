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
PulseCounter DTO
"""
from gateway.dto.base import BaseDTO, capture_fields

if False:  # MYPY
    from typing import Optional


class PulseCounterDTO(BaseDTO):
    @capture_fields
    def __init__(self, id, name='', room=None, input_id=None, persistent=False):
        self.id = id  # type: int
        self.name = name  # type: str
        self.input_id = input_id  # type: Optional[int]
        self.room = room  # type: Optional[int]
        self.persistent = persistent  # type: bool

    def __eq__(self, other):
        if not isinstance(other, PulseCounterDTO):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.input_id == other.input_id and
                self.room == other.room and
                self.persistent == other.persistent)
