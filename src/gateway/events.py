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

if False:  # MYPY
    from typing import Any, Dict


class GatewayEvent(object):
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

    * VENTILATION_CHANGE
      {'id': str,      # Device ID
       'plugin': str,  # Target Plugin
       'mode': str,    # Auto/Manual
       'level': int,
       'connected': bool}
    """

    class Types(object):
        CONFIG_CHANGE = 'CONFIG_CHANGE'
        INPUT_CHANGE = 'INPUT_CHANGE'
        OUTPUT_CHANGE = 'OUTPUT_CHANGE'
        SHUTTER_CHANGE = 'SHUTTER_CHANGE'
        THERMOSTAT_CHANGE = 'THERMOSTAT_CHANGE'
        THERMOSTAT_GROUP_CHANGE = 'THERMOSTAT_GROUP_CHANGE'
        VENTILATION_CHANGE = 'VENTILATION_CHANGE'
        ACTION = 'ACTION'
        PING = 'PING'
        PONG = 'PONG'

    def __init__(self, event_type, data):
        # type: (str, Dict[str,Any]) -> None
        self.type = event_type
        self.data = data

    def serialize(self):
        # type: () -> Dict[str,Any]
        return {'type': self.type,
                'data': self.data,
                '_version': 1.0}  # Add version so that event processing code can handle multiple formats

    def __eq__(self, other):
        # type: (Any) -> bool
        return isinstance(other, GatewayEvent) \
            and self.type == other.type \
            and self.data == other.data

    def __repr__(self):
        # type: () -> str
        return '<GatewayEvent {} {}>'.format(self.type, self.data)

    def __str__(self):
        # type: () -> str
        return json.dumps(self.serialize())

    @staticmethod
    def deserialize(data):
        # type: (Dict[str,Any]) -> GatewayEvent
        return GatewayEvent(event_type=data['type'],
                            data=data['data'])
