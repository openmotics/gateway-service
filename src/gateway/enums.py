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
Generic module that houses various enums
"""

if False:  # MYPY
    from typing import Literal


class ShutterEnums(object):
    class Direction(object):
        UP = 'UP'
        DOWN = 'DOWN'
        STOP = 'STOP'

    class State(object):
        GOING_UP = 'going_up'
        GOING_DOWN = 'going_down'
        STOPPED = 'stopped'
        UP = 'up'
        DOWN = 'down'


class UserEnums(object):
    class AuthenticationErrors(object):
        INVALID_CREDENTIALS = 'invalid_credentials'
        TERMS_NOT_ACCEPTED = 'terms_not_accepted'

    class DeleteErrors(object):
        LAST_ACCOUNT = 'Cannot delete last user account'


class ThermostatMode(object):
    COOLING = 'cooling'  # type: Literal['cooling']
    HEATING = 'heating'  # type: Literal['heating']


class IndicateType(object):
    OUTPUT = 0
    INPUT = 1
    SENSOR = 2


class EnergyEnums(object):
    class Version(object):
        POWER_MODULE = 8
        ENERGY_MODULE = 12
        P1_CONCENTRATOR = 1

    NUMBER_OF_PORTS = {Version.POWER_MODULE: 8,
                       Version.ENERGY_MODULE: 12,
                       Version.P1_CONCENTRATOR: 8}
    LARGEST_MODULE_TYPE = Version.ENERGY_MODULE  # Update if needed
