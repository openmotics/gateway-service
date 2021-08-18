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
from functools import reduce

if False:  # MYPY
    from typing import Literal


class BaseEnum(object):
    _flat_elements = None

    @classmethod
    def contains(cls, item):
        if cls._flat_elements is None:
            cls._flat_elements = [(elem, value) for elem, value in cls.__dict__.items() if not elem.startswith('__') and not callable(getattr(cls, elem))]
            cls._flat_elements = reduce(lambda x, y: x+y, cls._flat_elements)
        return item in cls._flat_elements


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


class HardwareType(object):
    VIRTUAL = 'virtual'
    PHYSICAL = 'physical'
    EMULATED = 'emulated'
    INTERNAL = 'internal'


class ModuleType(object):
    SENSOR = 'sensor'
    INPUT = 'input'
    OUTPUT = 'output'
    SHUTTER = 'shutter'
    DIM_CONTROL = 'dim_control'
    CAN_CONTROL = 'can_control'
    OPEN_COLLECTOR = 'open_collector'
    ENERGY = 'energy'
    POWER = 'power'
    P1_CONCENTRATOR = 'p1_concentrator'
    UNKNOWN = 'unknown'


class Leds(object):
    EXPANSION = 'EXPANSION'
    STATUS_GREEN = 'STATUS_GREEN'
    STATUS_RED = 'STATUS_RED'
    CAN_STATUS_GREEN = 'CAN_STATUS_GREEN'
    CAN_STATUS_RED = 'CAN_STATUS_RED'
    CAN_COMMUNICATION = 'CAN_COMMUNICATION'
    P1 = 'P1'
    LAN_GREEN = 'LAN_GREEN'
    LAN_RED = 'LAN_RED'
    CLOUD = 'CLOUD'
    SETUP = 'SETUP'
    RELAYS_1_8 = 'RELAYS_1_8'
    RELAYS_9_16 = 'RELAYS_9_16'
    OUTPUTS_DIG_1_4 = 'OUTPUTS_DIG_1_4'
    OUTPUTS_DIG_5_7 = 'OUTPUTS_DIG_5_7'
    OUTPUTS_ANA_1_4 = 'OUTPUTS_ANA_1_4'
    INPUTS = 'INPUTS'
    POWER = 'POWER'
    ALIVE = 'ALIVE'
    VPN = 'VPN'
    COMMUNICATION_1 = 'COMMUNICATION_1'
    COMMUNICATION_2 = 'COMMUNICATION_2'


class LedStates(object):
    OFF = 'OFF'
    BLINKING_25 = 'BLINKING_25'
    BLINKING_50 = 'BLINKING_50'
    BLINKING_75 = 'BLINKING_75'
    SOLID = 'SOLID'


class Buttons(object):
    SELECT = 'SELECT'
    SETUP = 'SETUP'
    ACTION = 'ACTION'
    CAN_POWER = 'CAN_POWER'


class ButtonStates(object):
    PRESSED = 'PRESSED'
    RELEASED = 'RELEASED'


class SerialPorts(object):
    MASTER_API = 'MASTER_API'
    ENERGY = 'ENERGY'
    P1 = 'P1'
    EXPANSION = 'EXPANSION'


class Languages(BaseEnum):
    """ languages, ISO 639-1 format"""
    # only the current supported languages are included
    EN = 'en'
    DE = 'DE'
    NL = 'nl'
    FR = 'fr'
