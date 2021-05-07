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
import time
import datetime

import six
from dateutil.parser import parse
import pytz

from gateway.dto.base import BaseDTO, capture_fields


import debug_ignore

if False:  # MYPY
    from typing import Any, Optional, Union
    from gateway.dto.user import UserDTO


class DeliveryDTO(BaseDTO):
    # TIME_FORMAT = '%Y-%m-%dT%H:%M:%S%z'
    # TIMEZONE = 'Europe/Brussels'

    @capture_fields
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

    # @property
    # def timestamp_pickup(self):
    #     # type: () -> Optional[datetime.datetime]
    #     debug_ignore.debug('reading out pickup timestamp: {}, type: {}'.format(self.__timestamp_pickup, type(self.__timestamp_pickup)))
    #     return self.__timestamp_pickup
    #     # try:
    #     #     parsed = parse(self.__timestamp_pickup)
    #     #     return parsed
    #     # except Exception as ex:
    #     #     debug_ignore.debug('Coudl not parse time: {}'.format(ex))
    #     #     return None
    #
    # def get_timestamp_pickup_formatted(self):
    #     # type: () -> Optional[str]
    #     if self.__timestamp_pickup is not None:
    #         return self.__timestamp_pickup.strftime(DeliveryDTO.TIME_FORMAT)
    #     return None
    #
    # @timestamp_pickup.setter
    # def timestamp_pickup(self, value):
    #     # type: (Optional[Union[time.struct_time, str]]) -> None
    #     debug_ignore.debug('received pickup timestamp: {}, type: {}'.format(value, type(value)))
    #     if value is None:
    #         self.__timestamp_pickup = None
    #         return
    #     if isinstance(value, six.string_types):
    #         try:
    #             self.__timestamp_pickup = parse(value)
    #             self._loaded_fields.add('timestamp_pickup')
    #             self._loaded_fields.discard('_DeliveryDTO__timestamp_delivery')
    #             return
    #         except Exception:
    #             raise RuntimeError('Not a valid string passed to the timestamp pickup')
    #     if not isinstance(value, datetime.datetime):
    #         raise RuntimeError('timestamp should be an instance of datetime.datetime or string. Received: {}'.format(type(value)))
    #     self.__timestamp_pickup = pytz.timezone(DeliveryDTO.TIMEZONE).localize(value)
    #     self._loaded_fields.add('timestamp_pickup')
    #     self._loaded_fields.discard('_DeliveryDTO__timestamp_delivery')
    #
    # @property
    # def timestamp_delivery(self):
    #     # type: () -> Optional[datetime.datetime]
    #     debug_ignore.debug('reading out delivery timestamp: {}, type: {}'.format(self.__timestamp_delivery, type(self.__timestamp_delivery)))
    #     return self.__timestamp_delivery
    #     # try:
    #     #     parsed = parse(self.__timestamp_delivery)
    #     #     return parsed
    #     # except Exception as ex:
    #     #     debug_ignore.debug('Coudl not parse time: {}'.format(ex))
    #     #     return None
    #
    # def get_timestamp_delivery_formatted(self):
    #     # type: () -> Optional[str]
    #     if self.__timestamp_delivery is not None:
    #         return self.__timestamp_delivery.strftime(DeliveryDTO.TIME_FORMAT)
    #     return None
    #
    # @timestamp_delivery.setter
    # def timestamp_delivery(self, value):
    #     # type: (Optional[Union[time.struct_time, str]]) -> None
    #     debug_ignore.debug('received delivery timestamp: {}, type: {}'.format(value, type(value)))
    #     if value is None:
    #         self.__timestamp_delivery = None
    #         return
    #     if isinstance(value, six.string_types):
    #         try:
    #             self.__timestamp_delivery = parse(value)
    #             self._loaded_fields.add('timestamp_delivery')
    #             self._loaded_fields.discard('_DeliveryDTO__timestamp_delivery')
    #             return
    #         except Exception:
    #             raise RuntimeError('Not a valid string passed to the timestamp delivery')
    #     if not isinstance(value, datetime.datetime):
    #         raise RuntimeError('timestamp should be an instance of datetime.datetime or string. Received: {}'.format(type(value)))
    #     self.__timestamp_delivery = pytz.timezone(DeliveryDTO.TIMEZONE).localize(value)
    #     self._loaded_fields.add('timestamp_delivery')
    #     self._loaded_fields.discard('_DeliveryDTO__timestamp_delivery')

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

