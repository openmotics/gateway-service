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
from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Optional


class PulseCounterDTO(BaseDTO):
    def __init__(self, id, name='', room=None, input_id=None, persistent=False, in_use=True):
        self.id = id  # type: int
        self.name = name  # type: str
        self.input_id = input_id  # type: Optional[int]
        self.room = room  # type: Optional[int]
        self.in_use = in_use  # type: bool
        self.persistent = persistent  # type: bool
