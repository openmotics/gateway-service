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
apartment DTO
"""
from gateway.dto.base import BaseDTO, capture_fields

if False:  # MYPY
    from typing import Any


class ApartmentDTO(BaseDTO):
    @capture_fields
    def __init__(self, id, name, mailbox_rebus_id, doorbell_rebus_id):
        self.id = id  # type: int
        self.name = name  # type: str
        self.mailbox_rebus_id = mailbox_rebus_id  # type: int
        self.doorbell_rebus_id = doorbell_rebus_id  # type: int

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, ApartmentDTO):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.mailbox_rebus_id == other.mailbox_rebus_id and
                self.doorbell_rebus_id == other.doorbell_rebus_id)
