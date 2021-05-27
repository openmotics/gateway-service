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
Output DTO
"""
import time
from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Any, Optional


class VentilationDTO(BaseDTO):
    def __init__(self, id, source, external_id='', name='', amount_of_levels=0,
                 device_vendor='', device_type='', device_serial=''):
        self.id = id  # type: int
        self.source = source  # type: VentilationSourceDTO
        self.external_id = external_id  # type: str
        self.name = name  # type: str
        self.amount_of_levels = amount_of_levels  # type: int
        self.device_vendor = device_vendor  # type: str
        self.device_type = device_type  # type: str
        self.device_serial = device_serial  # type: str


class VentilationSourceDTO(BaseDTO):
    class Type(object):
        PLUGIN = 'plugin'

    def __init__(self, id, type='', name=''):
        self.id = id  # type: int
        self.type = type  # type: str
        self.name = name  # type: str

    @property
    def is_plugin(self):
        return self.type == VentilationSourceDTO.Type.PLUGIN


class VentilationStatusDTO(BaseDTO):
    STATUS_TIMEOUT = 300  # Seconds until the last status is invalid
    class Mode(object):
        AUTO = 'auto'
        MANUAL = 'manual'

    def __init__(self, id, mode, level=None, timer=None, remaining_time=None, last_seen=None):
        # type: (int, str, Optional[int], Optional[float], Optional[float], Optional[float]) -> None
        self.id = id
        self.mode = mode
        self.level = level
        self.timer = timer
        self.remaining_time = remaining_time
        self.last_seen = last_seen or time.time()

    @property
    def is_connected(self):
        # type: () -> bool
        return (time.time() - self.last_seen) < VentilationStatusDTO.STATUS_TIMEOUT

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, VentilationStatusDTO):
            return False
        if self.timer:  # is write only
            return False
        return (self.id == other.id and
                self.mode == other.mode and
                self.level == other.level and
                self.remaining_time == other.remaining_time)
