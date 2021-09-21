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
Doorbell DTO
"""

from gateway.dto.base import BaseDTO

if False:  # mypy
    from typing import Optional
    from gateway.dto.apartment import ApartmentDTO

class DoorbellDTO(BaseDTO):

    def __init__(self, id=None, label=None, apartment=None):
        self.id = id  # type: int
        self.label = label  # type: str
        self.apartment = apartment  # type: Optional[ApartmentDTO]
