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
from dateutil.parser import parse

from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Any, Optional
    from gateway.dto.user import UserDTO


class DeliveryDTO(BaseDTO):

    def __init__(self, id=None, type=None, timestamp_delivery=None, user_delivery=None, timestamp_pickup=None,
                 courier_firm=None, signature_delivery=None, signature_pickup=None, parcelbox_rebus_id=None,
                 user_pickup=None):
        self.id = id  # type: int
        self.type = type  # type: str
        self.timestamp_delivery = timestamp_delivery  # type: str
        self.timestamp_pickup = timestamp_pickup  # type: str
        self.courier_firm = courier_firm  # type: str
        self.signature_delivery = signature_delivery  # type: str
        self.signature_pickup = signature_pickup  # type: str
        self.parcelbox_rebus_id = parcelbox_rebus_id  # type: int
        self.user_delivery = user_delivery  # type: UserDTO
        self.user_pickup = user_pickup  # type: Optional[UserDTO]

    @property
    def timestamp_delivery_datetime(self):
        if self.timestamp_delivery is not None:
            return parse(self.timestamp_delivery)
        return None

    @property
    def timestamp_pickup_datetime(self):
        if self.timestamp_pickup is not None:
            return parse(self.timestamp_pickup)
        return None

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
