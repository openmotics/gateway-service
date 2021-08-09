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
Box DTO's (parcelbox and mailbox)
"""
import enum
from gateway.dto.base import BaseDTO

if False:  # mypy
    from gateway.dto.apartment import ApartmentDTO


class ParcelBoxDTO(BaseDTO):
    class Size(enum.Enum):
        XS = 'XS'
        S = 'S'
        M = 'M'
        L1 = 'L1'
        L2 = 'L2'
        XL = 'XL'
        UNKNOWN = 'UNKNOWN'

    def __init__(self, id=None, label=None, height=None, width=None, size=None, available=True, is_open=False):
        self.id = id  # type: int
        self.label = label  # type: str
        self.height = height  # type: int
        self.width = width  # type: int
        self.size = size  # type: ParcelBoxDTO.Size
        self.available = available  # type: bool
        self.is_open = is_open  # type: bool


class MailBoxDTO(BaseDTO):

    def __init__(self, id=None, label=None, apartment=None, is_open=False):
        self.id = id  # type: int
        self.label = label  # type: str
        self.apartment = apartment  # type: ApartmentDTO
        self.is_open = is_open  # type: bool
