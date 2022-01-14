# Copyright (C) 2022 OpenMotics BV
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
Generic module that houses various enums
"""


class HardwareType(object):
    VIRTUAL = 'virtual'
    PHYSICAL = 'physical'
    EMULATED = 'emulated'
    INTERNAL = 'internal'


class OutputType(object):
    OUTLET = 0
    VALVE = 1
    ALARM = 2
    APPLIANCE = 3
    PUMP = 4
    HVAC = 5
    GENERIC = 6
    MOTOR = 7
    VENTILATION = 8
    HEATER = 9
    SHUTTER_RELAY = 127
    LIGHT = 255
