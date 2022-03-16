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


class EventError(object):

    class ErrorTypes(BaseEnum):
        NO_ERROR = {'code': 0, 'description': 'no error'}
        WRONG_INPUT_PARAM = {'code': 1, 'description': 'wrong input parameter(s)'}
        MODULE_BUSY = {'code': 2, 'description': 'module is busy and cannot accept new requests'}
        PARSE_ERROR = {'code': 3, 'description': 'couldn\'t parse input'}
        TIMER_ERROR = {'code': 4, 'description': 'timer error'}
        TIME_OUT = {'code': 5, 'description': 'timer expired'}
        STATE_ERROR = {'code': 6, 'description': 'unexpected state'}
        DOES_NOT_EXIST = {'code': 7, 'description': 'item does not exist'}
        INVALID_OPERATION = {'code': 8, 'description': 'invalid operation'}
        UN_AUTHORIZED = {'code': 9, 'description': 'unauthorized operation'}
        NOT_IMPLEMENTED = {'code': 10, 'description': 'not implemented'}
        BAD_CONFIGURATION = {'code': 11, 'description': 'bad configuration'}
        Aborted = {'code': 12, 'description': 'aborted'}
        Forbidden = {'code': 13, 'description': 'forbidden'}

    def __init__(self, code, description):
        self.code = code
        self.description = description

    @staticmethod
    def from_error_type(error_type):
        return EventError(**error_type)

    def to_dict(self):
        return {'code': self.code, 'description': self.description}

    def __str__(self):
        return '<Event Error: {} >'.format(self.to_dict())


class BaseEvent(object):
    """
    This class represents the base template for any type of events
    """
    VERSION = 1
    NAMESPACE = 'BASE_EVENT'

    def __init__(self, event_type, data, error=None):
        if error is None:
            error = EventError.ErrorTypes.NO_ERROR
        elif not isinstance(error, dict) or 'code' not in error or 'description' not in error:
            raise ValueError('Not a proper error format: need a dict with {"code": <ERROR_CODE>, "description": <ERROR_DESCRIPTION>}')
        self.type = event_type
        self.data = data
        self.error = EventError.from_error_type(error)

    def serialize(self):
        # type: () -> Dict[str,Any]
        version = self.__class__.VERSION
        if version == 1:
            return {'type': self.type,
                    'data': self.data,
                    'error': self.error.to_dict(),
                    '_version': 1.0}  # Add version so that event processing code can handle multiple formats
        else:
            if self.namespace == BaseEvent.NAMESPACE:
                raise NotImplementedError('Cannot serialize a BaseEvent instance, needs to be a subclass')
            return {'type': self.type,
                    'data': self.data,
                    'error': self.error.to_dict(),
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

