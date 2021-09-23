# Copyright (C) 2021 OpenMotics BV
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
Contains Serial Number related code
"""

from __future__ import absolute_import
from master.core.fields import UInt32Field
from master.core.toolbox import Toolbox

if False:  # MYPY
    from typing import Any


class SerialNumber(object):
    def __init__(self, year, month, day, company, serial):  # type: (int, int, int, int, int) -> None
        self._uint32_helper = UInt32Field('')
        self._year = year if 0 <= year <= 99 else 0
        self._month = month if 1 <= month <= 12 else 0
        self._day = day if 1 <= day <= 31 else 0
        self._company = company
        self._serial = serial

    @staticmethod
    def decode(data):  # type: (bytearray) -> SerialNumber
        uint32_helper = UInt32Field('')
        return SerialNumber(year=data[0],
                            month=data[1],
                            day=data[2],
                            company=data[3],
                            serial=uint32_helper.decode(bytearray([0]) + data[4:7]))

    def encode(self):
        serial = self._uint32_helper.encode(self._serial)
        return bytearray([self._year, self._month, self._day, self._company]) + serial[1:4]

    def __str__(self):
        return 'SN(20{0:02d}{1:02d}{2:02d},{3},{4})'.format(self._year, self._month, self._day,
                                                            self._company, self._serial)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):  # type: (Any) -> bool
        if not isinstance(other, SerialNumber):
            return False
        return self.encode() == other.encode()

    def __hash__(self):
        return Toolbox.hash(self.encode())
