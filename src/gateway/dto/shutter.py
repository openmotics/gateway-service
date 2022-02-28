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
from gateway.dto.base import BaseDTO
from gateway.dto.module import ModuleDTO

if False:  # MYPY
    from typing import Optional


class ShutterDTO(BaseDTO):
    def __init__(self, id, name='', timer_up=None, timer_down=None, up_down_config=None,
                 group_1=None, group_2=None, room=None, steps=None, module=None):
        self.id = id  # type: int
        self.name = name  # type: str
        self.timer_up = timer_up  # type: Optional[int]
        self.timer_down = timer_down  # type: Optional[int]
        self.up_down_config = up_down_config  # type: Optional[int]
        self.group_1 = group_1  # type: Optional[int]
        self.group_2 = group_2  # type: Optional[int]
        self.room = room  # type: Optional[int]
        self.steps = steps  # type: Optional[int]
        self.module = module  # type: Optional[ModuleDTO]
