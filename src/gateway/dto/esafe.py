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
from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Any, Optional
    import time

class EsafeApartmentDTO(BaseDTO):
    def __init__(self, id, name, mailbox_rebus_id, doorbell_rebus_id):
        self.id = id  # type: int
        self.name = name  # type: str
        self.mailbox_rebus_id = mailbox_rebus_id  # type: int
        self.doorbell_rebus_id = doorbell_rebus_id  # type: int

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, EsafeApartmentDTO):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.mailbox_rebus_id == other.mailbox_rebus_id and
                self.doorbell_rebus_id == other.doorbell_rebus_id)

class EsafeUserDTO(BaseDTO):
    def __init__(self, id, first_name='', last_name='', role='', code=None, apartment_dto=None):
        self.id = id  # type: int
        self.first_name = first_name  # type: str
        self.last_name = last_name  # type: str
        self.role = role  # type: str
        self.code = code  # type: str
        self.apartment = apartment_dto  # type: EsafeApartmentDTO

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, EsafeUserDTO):
            return False
        return (self.id == other.id and
                self.first_name == other.first_name and
                self.last_name == other.last_name and
                self.role == other.role and
                self.code == other.code and
                self.apartment == other.apartment)

class EsafeSystemDTO(BaseDTO):
    def __init__(self, key, value):
        self.key = key  # type: str
        self.value = value  # type: str

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, EsafeSystemDTO):
            return False
        return (self.key == other.key and
                self.value == other.value)


class EsafeRfidDTO(BaseDTO):
    def __init__(self, id, tag_string, uid_manufacturer, uid_extension='', enter_count=-1, blacklisted=False, label='',
                 timestamp_created='', timestamp_last_used='', user_dto=None):
        self.id = id  # type: int
        self.tag_string = tag_string  # type: str
        self.uid_manufacturer = uid_manufacturer  # type: str
        self.uid_extension = uid_extension  # type: str
        self.enter_count = enter_count  # type: int
        self.blacklisted = blacklisted  # type: bool
        self.label = label  # type: str
        self.timestamp_created = timestamp_created  # type: int
        self.timestamp_last_used = timestamp_last_used  # type: int
        self.user = user_dto  # type: EsafeUserDTO

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, EsafeRfidDTO):
            return False
        return (self.id == other.id and
                self.tag_string == other.tag_string and
                self.uid_extension == other.uid_extension and
                self.uid_manufacturer == other.uid_manufacturer and
                self.enter_count == other.enter_count and
                self.blacklisted == other.blacklisted and
                self.label == other.label and
                self.timestamp_created == other.timestamp_created and
                self.timestamp_last_used == other.timestamp_last_used and
                self.user == other.user)

class EsafeDeliveryDTO(BaseDTO):
    def __init__(self, id, type, timestamp_delivery='', timestamp_pickup='', courier_firm='', signature_delivery='',
                 signature_pickup='', parcelbox_rebus_id=None, user_dto_delivery=None, user_dto_pickup=None):
        self.id = id  # type: int
        self.type = type  # type: str
        self.timestamp_delivery = timestamp_delivery  # type: int
        self.timestamp_pickup = timestamp_pickup  # type: int
        self.courier_firm = courier_firm  # type: str
        self.signature_delivery = signature_delivery  # type: str
        self.signature_pickup = signature_pickup  # type: str
        self.parcelbox_rebus_id = parcelbox_rebus_id  # type: int
        self.user_delivery = user_dto_delivery  # type: EsafeUserDTO
        self.user_pickup = user_dto_pickup  # type: EsafeUserDTO

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, EsafeDeliveryDTO):
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

