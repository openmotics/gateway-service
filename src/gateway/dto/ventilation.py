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

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, VentilationDTO):
            return False
        return (self.id == other.id and
                self.source == other.source and
                self.external_id == other.external_id and
                self.name == other.name and
                self.device_vendor == other.device_vendor and
                self.device_type == other.device_type and
                self.device_serial == other.device_serial and
                self.amount_of_levels == other.amount_of_levels)


class VentilationSourceDTO(BaseDTO):
    class Type:
        PLUGIN = 'plugin'

    def __init__(self, id, type='', name=''):
        self.id = id  # type: int
        self.type = type  # type: str
        self.name = name  # type: str

    @property
    def is_plugin(self):
        return self.type == VentilationSourceDTO.Type.PLUGIN

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, VentilationSourceDTO):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.type == other.type)


class VentilationStatusDTO(BaseDTO):
    class Mode:
        AUTO = 'auto'
        MANUAL = 'manual'

    def __init__(self, id, mode, level=None, timer=None, remaining_time=None, timestamp=None):
        # type: (int, str, Optional[int], Optional[float], Optional[float], Optional[float]) -> None
        if timestamp is None:
            # Set the default value for a timestamp as the current timestamp
            timestamp = time.time()
        self.id = id
        self.mode = mode
        self.level = level
        self.timer = timer
        self.remaining_time = remaining_time
        self.timestamp = timestamp

    @property
    def is_connected(self):
        # type: () -> bool
        return (time.time() - self.timestamp) < 300

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, VentilationStatusDTO):
            return False
        if self.timer:  # is write only
            return False
        return (self.id == other.id and
                self.mode == other.mode and
                self.level == other.level)
