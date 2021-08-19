# Copyright (C) 2018 OpenMotics BV
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
The events module contains various event classes
"""
from __future__ import absolute_import

import ujson as json

from gateway.enums import BaseEnum

if False:  # MYPY
    from typing import Any, Dict, Optional


class BaseEvent(object):
    """
    This class represents the base template for any type of events
    """
    VERSION = 1
    NAMESPACE = 'BASE_EVENT'

    def __init__(self, event_type, data):
        # type: (str, Optional[Dict[str,Any]]) -> None
        self.type = event_type
        self.data = data

    def serialize(self):
        # type: () -> Dict[str,Any]
        version = self.__class__.VERSION
        if version == 1:
            return {'type': self.type,
                    'data': self.data,
                    '_version': 1.0}  # Add version so that event processing code can handle multiple formats
        else:
            if self.namespace == BaseEvent.NAMESPACE:
                raise NotImplementedError('Cannot serialize a BaseEvent instance, needs to be a subclass')
            return {'type': self.type,
                    'data': self.data,
                    'namespace': self.namespace,
                    '_version': float(version)}

    def __eq__(self, other):
        # type: (Any) -> bool
        return isinstance(other, self.__class__) \
               and self.type == other.type \
               and self.data == other.data

    def __repr__(self):
        # type: () -> str
        return '<{} {} {}>'.format(self.__class__.__name__, self.type, self.data)

    def __str__(self):
        # type: () -> str
        return json.dumps(self.serialize())

    @classmethod
    def deserialize(cls, data):
        # type: (Dict[str,Any]) -> BaseEvent
        return cls(event_type=data['type'],
                   data=data['data'])

    @property
    def namespace(self):
        return self.__class__.NAMESPACE


class GatewayEvent(BaseEvent):
    """
    GatewayEvent object

    Data formats:
    * CONFIG_CHANGE
      {'type': str}  # Resource type, output, input, ...

    * OUTPUT_CHANGE
      {'id': int,                     # Output ID
       'status': {'on': bool,         # On/off
                  'value': int},      # Optional, dimmer value
       'location': {'room_id': int}}  # Room ID

    * SENSOR_CHANGE
      {'id': int,       # Sensor ID
       'plugin': str,   # Target Plugin
       'value': float}  # Value

    * VENTILATION_CHANGE
      {'id': str,      # Device ID
       'plugin': str,  # Target Plugin
       'mode': str,    # Auto/Manual
       'level': int,
       'connected': bool}
    """
    NAMESPACE = 'OPENMOTICS'

    class Types(BaseEnum):
        CONFIG_CHANGE = 'CONFIG_CHANGE'
        INPUT_CHANGE = 'INPUT_CHANGE'
        OUTPUT_CHANGE = 'OUTPUT_CHANGE'
        SENSOR_CHANGE = 'SENSOR_CHANGE'
        SHUTTER_CHANGE = 'SHUTTER_CHANGE'
        THERMOSTAT_CHANGE = 'THERMOSTAT_CHANGE'
        THERMOSTAT_GROUP_CHANGE = 'THERMOSTAT_GROUP_CHANGE'
        VENTILATION_CHANGE = 'VENTILATION_CHANGE'
        ACTION = 'ACTION'
        PING = 'PING'
        PONG = 'PONG'


class EsafeEvent(BaseEvent):
    """
    eSafeEvent object

    Data formats:

    * CONFIG_CHANGE
      {'type': str}  # config type: Global, Doorbell, RFID

    * DELIVERY_CHANGE
      {'type': str,              # Delivery type: DELIVERY or RETURN
       'action': str,            # action type: DELIVERY or PICKUP
       'user_delivery_id': int,  # ID of the delivery user (can be None)
       'user_pickup_id': int,    # ID of the pickup user (Always has a value, but can be a courier)
       'parcel_rebus_id': int}   # Rebus id of the used parcelbox

    * LOCK_CHANGE
      {'id': int,      # Rebus lock id
       'status': str}  # action type: 'open' or 'close'

    * RFID_CHANGE
      {'uuid': str,      # RFID uuid
       'action': str}    # action of the rfid change: "SCAN" or "REGISTER"
    """
    VERSION = 2
    NAMESPACE = 'ESAFE'

    class Types(BaseEnum):
        CONFIG_CHANGE = 'CONFIG_CHANGE'
        DELIVERY_CHANGE = 'DELIVERY_CHANGE'
        LOCK_CHANGE = 'LOCK_CHANGE'
        RFID_CHANGE = 'RFID_CHANGE'
