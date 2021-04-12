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
Sensor DTO
"""
from gateway.dto.base import BaseDTO, capture_fields

if False:  # MYPY
    from typing import Any, Optional


class SensorDTO(BaseDTO):
    @capture_fields
    def __init__(self, id, source=None, external_id=None, physical_quantity=None, unit=None, name='', room=None, offset=None, virtual=False):
        self.id = id  # type: int
        self.source = source  # type: str
        self.external_id = external_id  # type: str
        self.physical_quantity = physical_quantity  # type: Optional[str]
        self.unit = unit  # type: Optional[str]
        self.name = name  # type: str
        self.offset = offset  # type: Optional[float]
        self.room = room  # type: Optional[int]
        self.virtual = virtual  # type: bool

    def __eq__(self, other):
        if not isinstance(other, SensorDTO):
            return False
        return (self.id == other.id and
                self.source == other.source and
                self.external_id == other.external_id and
                self.physical_quantity == other.physical_quantity and
                self.unit == other.unit and
                self.name == other.name and
                self.offset == other.offset and
                self.room == other.room and
                self.virtual == other.virtual)


class SensorStatusDTO(BaseDTO):
    @capture_fields
    def __init__(self, id, value=None):
        # type: (int, Optional[float]) -> None
        self.id = id
        self.value = value

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, SensorStatusDTO):
            return False
        return (self.id == other.id and
                self.value == other.value)


class MasterSensorDTO(BaseDTO):
    @capture_fields
    def __init__(self, id, name='', offset=None, virtual=False):
        self.id = id  # type: int
        self.name = name[:16]  # type: str
        self.offset = offset  # type: Optional[float]
        self.virtual = virtual  # type: bool

    def __eq__(self, other):
        if not isinstance(other, SensorDTO):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.offset == other.offset and
                self.virtual == other.virtual)
