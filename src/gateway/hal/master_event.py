# Copyright (C) 2019 OpenMotics BV
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
Module for master events
"""
from __future__ import absolute_import

import ujson as json

if False:  # MYPY
    from typing import Any, Dict


class MasterEvent(object):
    """
    MasterEvent object

    Data formats:
    * EEPROM_CHANGE                   # No payload
    * MAINTENANCE_EXIT                # No payload
    * POWER_ADDRESS_EXIT              # No payload
    * MODULE_DISCOVERY                # No payload
    * OUTPUT_STATUS
      {'id': int,                     # Output ID
       'status': bool,                # On/off
       'dimmer': int}                 # Optional, dimmer value
    * INPUT_CHANGE
      {'id': int,                     # Input ID
       'status': bool,                # Pressed or not
       'location': {'room_id': int}}  # Room ID
    * SENSOR_VALUE
      {'sensor': int,                 # Sensor ID
       'type': str,                   # temperature, humidity, brightness
       'value': float}                # Current sensor value
    * EXECUTE_GATEWAY_API
      {'type': str,                   # APITypes
       'data': {...}}
      * SET_LIGHTS
        {'action': 'ON/OFF/TOGGLE',
         'floor_id': Optional[int]}
    """

    class Types(object):
        EEPROM_CHANGE = 'EEPROM_CHANGE'
        MAINTENANCE_EXIT = ' MAINTENANCE_EXIT'
        POWER_ADDRESS_EXIT = ' POWER_ADDRESS_EXIT'
        MODULE_DISCOVERY = 'MODULE_DISCOVERY'
        INPUT_CHANGE = 'INPUT_CHANGE'
        OUTPUT_CHANGE = 'OUTPUT_CHANGE'
        OUTPUT_STATUS = 'OUTPUT_STATUS'
        SHUTTER_CHANGE = 'SHUTTER_CHANGE'
        SENSOR_VALUE = 'SENSOR_VALUE'
        EXECUTE_GATEWAY_API = 'EXECUTE_GATEWAY_API'

    class APITypes(object):
        SET_LIGHTS = 'SET_LIGHTS'

    class SensorType(object):
        TEMPERATURE = 'TEMPERATURE'
        HUMIDITY = 'HUMIDITY'
        BRIGHTNESS = 'BRIGHTNESS'

    def __init__(self, event_type, data):
        # type: (str, Dict[str,Any]) -> None
        self.type = event_type
        self.data = data

    def serialize(self):
        # type: () -> Dict[str,Any]
        return {'type': self.type,
                'data': self.data}

    def __eq__(self, other):
        # type: (Any) -> bool
        return self.type == other.type \
            and self.data == other.data

    def __repr__(self):
        # type: () -> str
        return '<MasterEvent {} {}>'.format(self.type, self.data)

    def __str__(self):
        return json.dumps(self.serialize())

    @staticmethod
    def deserialize(data):
        # type: (Dict[str,Any]) -> MasterEvent
        return MasterEvent(event_type=data['type'],
                           data=data['data'])
