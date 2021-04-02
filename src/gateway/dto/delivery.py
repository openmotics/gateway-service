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
Delivery DTO
"""
from gateway.dto.base import BaseDTO, capture_fields

if False:  # MYPY
    from typing import Any, Optional
    from gateway.dto.user import UserDTO


class DeliveryDTO(BaseDTO):
    @capture_fields
    def __init__(self, id, type, timestamp_delivery, user_delivery, timestamp_pickup=None, courier_firm='',
                 signature_delivery='', signature_pickup='', parcelbox_rebus_id=None, user_pickup=None):
        self.id = id  # type: int
        self.type = type  # type: str
        self.timestamp_delivery = timestamp_delivery  # type: int
        self.timestamp_pickup = timestamp_pickup  # type: Optional[int]
        self.courier_firm = courier_firm  # type: str
        self.signature_delivery = signature_delivery  # type: str
        self.signature_pickup = signature_pickup  # type: str
        self.parcelbox_rebus_id = parcelbox_rebus_id  # type: int
        self.user_delivery = user_delivery  # type: UserDTO
        self.user_pickup = user_pickup  # type: Optional[UserDTO]

        self._loaded_fields.remove('user_delivery')
        self._loaded_fields.add('user_id_delivery')
        if user_pickup is not None:
            self._loaded_fields.add('user_id_pickup')
            self._loaded_fields.remove('user_pickup')

    @property
    def user_id_delivery(self):
        if self.user_delivery is not None:
            return self.user_delivery.id
        return None


    @property
    def user_id_pickup(self):
        if self.user_pickup is not None:
            return self.user_pickup.id
        return None

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, DeliveryDTO):
            return False
        return (self.id == other.id and
                self.type == other.type and
                self.timestamp_delivery == other.timestamp_delivery and
                self.timestamp_pickup == other.timestamp_pickup and
                self.courier_firm == other.courier_firm and
                self.signature_delivery == other.signature_delivery and
                self.signature_pickup == other.signature_pickup and
                self.parcelbox_rebus_id == other.parcelbox_rebus_id and
                self.user_delivery == other.user_delivery and
                self.user_pickup == other.user_pickup)

