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
    from typing import Any


class MasterEvent(object):
    """
    MasterEvent object

    Data formats:
    * EEPROM_CHANGE                   # No payload
    * OUTPUT CHANGE
      {'id': int,                     # Output ID
       'status': {'on': bool,         # On/off
                  'value': int},      # Optional, dimmer value
       'location': {'room_id': int}}  # Room ID
    * INPUT_CHANGE
      {'id': int,                     # Input ID
       'status': bool,                # Pressed or not
       'location': {'room_id': int}}  # Room ID
    """

    class Types(object):
        EEPROM_CHANGE = 'EEPROM_CHANGE'
        INPUT_CHANGE = 'INPUT_CHANGE'
        OUTPUT_CHANGE = 'OUTPUT_CHANGE'
        SHUTTER_CHANGE = 'SHUTTER_CHANGE'

    def __init__(self, event_type, data):
        self.type = event_type
        self.data = data

    def serialize(self):
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
        return MasterEvent(event_type=data['type'],
                           data=data['data'])
