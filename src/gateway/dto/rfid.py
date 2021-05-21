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
RFID DTO
"""
from gateway.dto.base import BaseDTO, capture_fields

if False:  # MYPY
    from typing import Any
    from gateway.dto.user import UserDTO


class RfidDTO(BaseDTO):
    @capture_fields
    def __init__(self, id, tag_string, uid_manufacturer, timestamp_created, user_dto,
                 uid_extension='', enter_count=-1, blacklisted=False, label='',
                 timestamp_last_used=''):
        self.id = id  # type: int
        self.tag_string = tag_string  # type: str
        self.uid_manufacturer = uid_manufacturer  # type: str
        self.uid_extension = uid_extension  # type: str
        self.enter_count = enter_count  # type: int
        self.blacklisted = blacklisted  # type: bool
        self.label = label  # type: str
        self.timestamp_created = timestamp_created  # type: str
        self.timestamp_last_used = timestamp_last_used  # type: str
        self.user = user_dto  # type: UserDTO
