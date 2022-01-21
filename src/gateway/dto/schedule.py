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
from datetime import datetime

from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Optional, Any, List


class BaseScheduleDTO(BaseDTO):
    @property
    def job_id(self):
        # type: () -> str
        raise NotImplementedError()


class ScheduleDTO(BaseScheduleDTO):
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

        # Status
        self.next_execution = None  # type: Optional[float]
        self.last_executed = None  # type: Optional[float]
        self.running = False  # type: bool

    @property
    def job_id(self):
        # type: () -> str
        return 'schedule.{0}'.format(self.id)

    @property
    def has_ended(self):
        if self.repeat is None:
            return self.last_executed is not None
        if self.end is not None:
            return self.end < time.time()
        return False


class ScheduleSetpointDTO(BaseScheduleDTO):
    def __init__(self, thermostat=None, mode=None, temperature=None, weekday=None, hour=None, minute=None):
        self.thermostat = thermostat  # type: int
        self.mode = mode  # type: str
        self.temperature = temperature  # type: float
        self.weekday = weekday  # type: int
        self.hour = hour  # type: int
        self.minute = minute  # type: int

    @property
    def job_id(self):
        # type: () -> str
        day = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}.get(self.weekday)
        return 'thermostat.{0}.{1}.{2}.{3:02}h{4:02}m'.format(self.mode, self.thermostat, day, self.hour, self.minute)
