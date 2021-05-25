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
GroupAction DTO
"""
from gateway.dto.base import BaseDTO, capture_fields

if False:  # MYPY
    from typing import Optional, List


class GroupActionDTO(BaseDTO):
    @capture_fields
    def __init__(self, id, name='', actions=None, internal=False):
        # type: (int, str, Optional[List[int]], bool) -> None
        # The argument `actions` is None since you should not set a reference type as default value
        self.id = id
        self.name = name
        self.actions = [] if actions is None else actions  # type: List[int]
        self.internal = internal
