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
Schedule DTO
"""
import time
from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Optional, Any, List


class ScheduleDTO(BaseDTO):
    def __init__(self, id, name, start, action, source=None, external_id=None, status=None, repeat=None, duration=None, end=None, arguments=None):
        self.id = id  # type: int
        self.source = source  # type: str
        self.external_id = external_id  # type: Optional[str]
        self.name = name  # type: str
        self.start = start  # type: float
        self.action = action  # type: str
        self.status = status  # type: Optional[str]
        self.repeat = repeat  # type: Optional[str]
        self.duration = duration  # type: Optional[float]
        self.end = end  # type: Optional[float]
        self.arguments = arguments  # type: Optional[Any]

        self.next_execution = None  # type: Optional[float]
        self.last_executed = None  # type: Optional[float]
        self.running = False  # type: bool

    def __eq__(self, other):
        if not isinstance(other, ScheduleDTO):
            return False
        return self.id == other.id

    @property
    def is_due(self):
        if self.repeat is None:
            # Single-run schedules should start on their set starting time if not yet executed
            if self.last_executed is not None:
                return False
            return self.start <= time.time()
        # Repeating
        now = time.time()
        lower_limit = now - (15 * 60)  # Don't execute a schedule that's overdue for 15 minutes
        upper_limit = now if self.end is None else min(now, self.end)
        return self.next_execution is not None and lower_limit <= self.next_execution <= upper_limit

    @property
    def has_ended(self):
        if self.repeat is None:
            return self.last_executed is not None
        if self.end is not None:
            return self.end < time.time()
        return False


class LegacyScheduleDTO(BaseDTO):
    def __init__(self, id, hour=0, minute=0, day=0, action=None):
        # type: (int, int, int, int, Optional[List[int]]) -> None
        self.id = id
        self.hour = hour
        self.minute = minute
        self.day = day
        self.action = [] if action is None else action  # type: List[int]


class LegacyStartupActionDTO(BaseDTO):
    def __init__(self, actions=None):  # type: (Optional[List[int]]) -> None
        self.actions = [] if actions is None else actions  # type: List[int]
