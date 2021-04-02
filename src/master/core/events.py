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
Module to handle Events from the Core
"""

from __future__ import absolute_import
import logging
from master.core.fields import WordField, AddressField
from master.core.system_value import Temperature, Humidity, Timer
from master.core.basic_action import BasicAction

if False:  # MYPY
    from typing import List, Optional

logger = logging.getLogger('openmotics')


class Event(object):
    class Types(object):
        OUTPUT = 'OUTPUT'
        INPUT = 'INPUT'
        SENSOR = 'SENSOR'
        THERMOSTAT = 'THERMOSTAT'
        SYSTEM = 'SYSTEM'
        POWER = 'POWER'
        EXECUTED_BA = 'EXECUTED_BA'
        BUTTON_PRESS = 'BUTTON_PRESS'
        LED_ON = 'LED_ON'
        LED_BLINK = 'LED_BLINK'
        UCAN = 'UCAN'
        UNKNOWN = 'UNKNOWN'

    class SensorType(object):
        TEMPERATURE = 'TEMPERATURE'
        HUMIDITY = 'HUMIDITY'
        BRIGHTNESS = 'BRIGHTNESS'
        UNKNOWN = 'UNKNOWN'

    class SystemEventTypes(object):
        EEPROM_ACTIVATE = 'EEPROM_ACTIVATE'
        ONBOARD_TEMP_CHANGED = 'ONBOARD_TEMP_CHANGED'
        UNKNOWN = 'UNKNOWN'

    class ThermostatOrigins(object):
        SLAVE = 'SLAVE'
        MASTER = 'MASTER'
        UNKNOWN = 'UNKNOWN'

    class Bus(object):
        RS485 = 'RS485'
        CAN = 'CAN'

    class Leds(object):
        LED_0 = 0
        LED_1 = 1
        LED_2 = 2
        LED_3 = 3
        LED_4 = 4
        LED_5 = 5
        LED_6 = 6
        LED_7 = 7
        LED_8 = 8
        LED_9 = 9
        LED_10 = 10
        LED_11 = 11
        LED_12 = 12
        LED_13 = 13
        LED_14 = 14
        LED_15 = 15

    class LedStates(object):
        OFF = 'OFF'
        ON = 'ON'

    class LedFrequencies(object):
        BLINKING_25 = 'BLINKING_25'
        BLINKING_50 = 'BLINKING_50'
        BLINKING_75 = 'BLINKING_75'
        SOLID = 'SOLID'

    class Buttons(object):
        SETUP = 0
        ACTION = 1
        CAN_POWER = 2
        SELECT = 3

    class ButtonStates(object):
        RELEASED = 0
        PRESSED = 1
        PRESSED_5S = 2
        PRESSED_LONG = 3

    def __init__(self, data):
        self._type = data['type']
        self._action = data['action']
        self._device_nr = data['device_nr']
        self._data = data['data']
        self._word_helper = WordField('')
        self._address_helper = AddressField('', length=3)

    @property
    def type(self):
        type_map = {0: Event.Types.OUTPUT,
                    1: Event.Types.INPUT,
                    2: Event.Types.SENSOR,
                    20: Event.Types.THERMOSTAT,
                    21: Event.Types.UCAN,
                    22: Event.Types.EXECUTED_BA,
                    250: Event.Types.BUTTON_PRESS,
                    251: Event.Types.LED_BLINK,
                    252: Event.Types.LED_ON,
                    253: Event.Types.POWER,
                    254: Event.Types.SYSTEM}
        return type_map.get(self._type, Event.Types.UNKNOWN)

    @property
    def data(self):
        if self.type == Event.Types.OUTPUT:
            timer_type = self._data[1]  # type: int
            timer_value = self._word_decode(self._data[2:]) or 0  # type: int
            timer = Timer.event_timer_type_to_seconds(timer_type, timer_value)
            return {'output': self._device_nr,
                    'status': self._action == 1,
                    'dimmer_value': self._data[0],
                    'timer': timer}
        if self.type == Event.Types.INPUT:
            return {'input': self._device_nr,
                    'status': self._action == 1}
        if self.type == Event.Types.SENSOR:
            sensor_type = Event.SensorType.UNKNOWN
            sensor_value = None
            if self._action == 0:
                sensor_type = Event.SensorType.TEMPERATURE
                sensor_value = Temperature.system_value_to_temperature(self._data[1])
            elif self._action == 1:
                sensor_type = Event.SensorType.HUMIDITY
                sensor_value = Humidity.system_value_to_humidity(self._data[1])
            elif self._action == 2:
                sensor_type = Event.SensorType.BRIGHTNESS
                sensor_value = self._word_decode(self._data[0:2])
            return {'sensor': self._device_nr,
                    'type': sensor_type,
                    'value': sensor_value}
        if self.type == Event.Types.THERMOSTAT:
            origin_map = {0: Event.ThermostatOrigins.SLAVE,
                          1: Event.ThermostatOrigins.MASTER}
            return {'origin': origin_map.get(self._action, Event.ThermostatOrigins.UNKNOWN),
                    'thermostat': self._device_nr,
                    'mode': self._data[0],
                    'setpoint': self._data[1]}
        if self.type == Event.Types.BUTTON_PRESS:
            return {'button': self._device_nr,
                    'state': self._data[0]}
        if self.type == Event.Types.LED_BLINK:
            word_25 = self._device_nr
            word_50 = self._word_decode(self._data[0:2])
            word_75 = self._word_decode(self._data[2:4])
            leds = {}
            for i in range(16):
                if word_25 & (1 << i):
                    leds[i] = Event.LedFrequencies.BLINKING_25
                elif word_50 & (1 << i):
                    leds[i] = Event.LedFrequencies.BLINKING_50
                elif word_75 & (1 << i):
                    leds[i] = Event.LedFrequencies.BLINKING_75
                else:
                    leds[i] = Event.LedFrequencies.SOLID
            return {'chip': self._device_nr,
                    'leds': leds}
        if self.type == Event.Types.LED_ON:
            word_on = self._word_decode(self._data[0:2])
            leds = {}
            for i in range(16):
                leds[i] = Event.LedStates.ON if word_on & (1 << i) else Event.LedStates.OFF
            return {'chip': self._device_nr,
                    'leds': leds}
        if self.type == Event.Types.POWER:
            return {'bus': Event.Bus.RS485 if self._device_nr == 0 else Event.Bus.CAN,
                    'power': self._data[0 > 1]}
        if self.type == Event.Types.SYSTEM:
            type_map = {0: Event.SystemEventTypes.EEPROM_ACTIVATE,
                        1: Event.SystemEventTypes.ONBOARD_TEMP_CHANGED}
            event_type = type_map.get(self._action, Event.SystemEventTypes.UNKNOWN)
            event_data = {'type': event_type}
            if event_type == Event.SystemEventTypes.ONBOARD_TEMP_CHANGED:
                event_data['temperature'] = self._data[0]
            return event_data
        if self.type == Event.Types.UCAN:
            return {'address': self._address_helper.decode(bytearray([self._device_nr & 0xFF]) + self._data[0:2]),
                    'data': self._data[2:4]}
        if self.type == Event.Types.EXECUTED_BA:
            return {'basic_action': BasicAction(action_type=self._data[0],
                                                action=self._data[1],
                                                device_nr=self._device_nr,
                                                extra_parameter=self._word_decode(self._data[2:4]))}
        return None

    def _word_decode(self, data):  # type: (List[int]) -> int
        return self._word_helper.decode(bytearray(data[0:2]))

    def __str__(self):
        return '{0} ({1})'.format(self.type, self.data if self.type != Event.Types.UNKNOWN else self._type)
