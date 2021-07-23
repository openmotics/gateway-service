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
    from typing import List

logger = logging.getLogger(__name__)


class Event(object):
    class Types(object):
        OUTPUT = 'OUTPUT'
        INPUT = 'INPUT'
        SENSOR = 'SENSOR'
        THERMOSTAT = 'THERMOSTAT'
        SYSTEM = 'SYSTEM'
        POWER = 'POWER'
        EXECUTED_BA = 'EXECUTED_BA'
        RESET_ACTION = 'RESET_ACTION'
        GENERIC_DATA = 'GENERIC_DATA'
        BUTTON_PRESS = 'BUTTON_PRESS'
        LED_ON = 'LED_ON'
        LED_BLINK = 'LED_BLINK'
        UCAN = 'UCAN'
        EXECUTE_GATEWAY_API = 'EXECUTE_GATEWAY_API'
        UNKNOWN = 'UNKNOWN'

    class IOEventTypes(object):
        STATUS = 'STATUS'
        LOCKING = 'LOCKING'

    class UCANEventTypes(object):
        POWER_OUT_ERROR = 'POWER_OUT_ERROR'
        POWER_OUT_RESTORED = 'POWER_OUT_RESTORED'
        POWER_OUT_ON = 'POWER_OUT_ON'
        POWER_OUT_OFF = 'POWER_OUT_OFF'
        I2C_ERROR = 'I2C_ERROR'
        RESTARTED = 'RESTARTED'
        UNKNOWN = 'UNKNOWN'

    class SensorType(object):
        TEMPERATURE = 'TEMPERATURE'
        HUMIDITY = 'HUMIDITY'
        BRIGHTNESS = 'BRIGHTNESS'
        CO2 = 'CO2'
        VOC = 'VOC'
        UNKNOWN = 'UNKNOWN'

    class SystemEventTypes(object):
        EEPROM_ACTIVATE = 'EEPROM_ACTIVATE'
        I2C_RESET = 'I2C_RESET'
        HEALTH = 'HEALTH'
        UNKNOWN = 'UNKNOWN'

    class GenericDataTypes(object):
        PCB_TEMPERATURE = 'PCB_TEMPERATURE'
        UNKNOWN = 'UNKNOWN'

    class SystemHealthTypes(object):
        CAN = 'CAN'
        UNKNOWN = 'UNKNOWN'

    class CANHealthTypes(object):
        NO_UCAN_OK = 'NO_UCAN_OK'
        ALL_UCAN_OK = 'ALL_UCAN_OK'
        SOME_UCAN_OK = 'SOME_UCAN_OK'
        CAN_BUS_OFF = 'CAN_BUS_OFF'
        UNKNOWN = 'UNKNOWN'

    class ResetTypes(object):
        HEALTH_CHECK = 'HEALTH_CHECK'
        CAN_STACK = 'CAN_STACK'
        PROCESSOR_RESET = 'PROCESSOR_RESET'
        UNKNOWN = 'UNKNOWN'

    class HealthResetCauses(object):
        I2C_1 = 'I2C_1'
        I2C_2 = 'I2C_2'
        CAN = 'CAN'
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
                    247: Event.Types.GENERIC_DATA,
                    248: Event.Types.SYSTEM,
                    249: Event.Types.EXECUTE_GATEWAY_API,
                    250: Event.Types.BUTTON_PRESS,
                    251: Event.Types.LED_BLINK,
                    252: Event.Types.LED_ON,
                    253: Event.Types.POWER,
                    254: Event.Types.RESET_ACTION}
        return type_map.get(self._type, Event.Types.UNKNOWN)

    @property
    def data(self):
        if self.type == Event.Types.OUTPUT:
            data = {'output': self._device_nr}
            if self._action in [0, 1]:
                timer_type = self._data[1]  # type: int
                timer_value = self._word_decode(self._data[2:]) or 0  # type: int
                timer = Timer.event_timer_type_to_seconds(timer_type, timer_value)
                data.update({'type': Event.IOEventTypes.STATUS,
                             'status': self._action == 1,
                             'dimmer_value': self._data[0],
                             'timer': timer})
            else:
                data.update({'type': Event.IOEventTypes.LOCKING,
                             'locked': self._data[0] == 1})
            return data
        if self.type == Event.Types.INPUT:
            data = {'input': self._device_nr}
            if self._action in [0, 1]:
                data.update({'type': Event.IOEventTypes.STATUS,
                             'status': self._action == 1})
            else:
                data.update({'type': Event.IOEventTypes.LOCKING,
                             'locked': self._data[0] == 1})
            return data
        if self.type == Event.Types.SENSOR:
            sensor_values = []
            if self._action == 0:
                sensor_values += [{'type': Event.SensorType.TEMPERATURE,
                                   'value': Temperature.system_value_to_temperature(self._data[1])}]
            elif self._action == 1:
                sensor_values += [{'type': Event.SensorType.HUMIDITY,
                                   'value': Humidity.system_value_to_humidity(self._data[1])}]
            elif self._action == 2:
                sensor_values += [{'type': Event.SensorType.BRIGHTNESS,
                                   'value': self._word_decode(self._data[0:2])}]
            elif self._action == 3:
                sensor_values += [{'type': Event.SensorType.CO2,
                                   'value': self._word_decode(self._data[0:2])},
                                  {'type': Event.SensorType.VOC,
                                   'value': self._word_decode(self._data[2:4])}]
            return {'sensor': self._device_nr,
                    'values': sensor_values}
        if self.type == Event.Types.THERMOSTAT:
            origin_map = {0: Event.ThermostatOrigins.SLAVE,
                          1: Event.ThermostatOrigins.MASTER}
            return {'origin': origin_map.get(self._action, Event.ThermostatOrigins.UNKNOWN),
                    'thermostat': self._device_nr,
                    'mode': self._data[0],
                    'setpoint': self._data[1]}
        if self.type == Event.Types.UCAN:
            data = {'address': self._address_helper.decode(bytearray([self._device_nr & 0xFF]) + self._data[0:2])}
            if self._data[2] == 0 and self._data[3] == 0:
                data['type'] = Event.UCANEventTypes.POWER_OUT_ERROR
            elif self._data[2] == 0 and self._data[3] == 1:
                data['type'] = Event.UCANEventTypes.POWER_OUT_RESTORED
            elif self._data[2] == 0 and self._data[3] == 2:
                data['type'] = Event.UCANEventTypes.POWER_OUT_OFF
            elif self._data[2] == 2 and self._data[3] == 3:
                data['type'] = Event.UCANEventTypes.POWER_OUT_ON
            elif self._data[2] == 3:
                data['type'] = Event.UCANEventTypes.RESTARTED
            elif self._data[2] == 1:
                data.update({'type': Event.UCANEventTypes.I2C_ERROR,
                             'i2c_address': self._data[3]})
            else:
                data.update({'type': Event.UCANEventTypes.UNKNOWN,
                             'data': self._data[2:4]})
            return data
        if self.type == Event.Types.EXECUTED_BA:
            return {'basic_action': BasicAction(action_type=self._data[0],
                                                action=self._data[1],
                                                device_nr=self._device_nr,
                                                extra_parameter=self._word_decode(self._data[2:4]))}
        if self.type == Event.Types.GENERIC_DATA:
            if self._action == 0:
                return {'action': Event.GenericDataTypes.PCB_TEMPERATURE,
                        'temperature': self._device_nr & 0xFF}
            return {'action': Event.GenericDataTypes.UNKNOWN,
                    'device_nr': self._device_nr,
                    'data': self._data}
        if self.type == Event.Types.SYSTEM:
            if self._action == 0:
                return {'type': Event.SystemEventTypes.EEPROM_ACTIVATE}
            if self._action == 2:
                return {'type': Event.SystemEventTypes.I2C_RESET,
                        'cause': self._data[0]}
            if self._action == 3:
                data = {'type': Event.SystemEventTypes.HEALTH,
                        'health_type': Event.SystemHealthTypes.UNKNOWN}
                if self._data[0] == 0:
                    can_health_map = {1: Event.CANHealthTypes.NO_UCAN_OK,
                                      2: Event.CANHealthTypes.ALL_UCAN_OK,
                                      3: Event.CANHealthTypes.SOME_UCAN_OK,
                                      4: Event.CANHealthTypes.CAN_BUS_OFF}
                    data.update({'health_type': Event.SystemHealthTypes.CAN,
                                 'current': can_health_map.get(self._data[1], Event.CANHealthTypes.UNKNOWN),
                                 'previous': can_health_map.get(self._data[2], Event.CANHealthTypes.UNKNOWN)})
                return data
            return {'type': Event.SystemEventTypes.UNKNOWN}
        if self.type == Event.Types.EXECUTE_GATEWAY_API:
            return {'action': self._data[3],
                    'device_nr': self._device_nr,
                    'extra_parameter': self._word_decode(self._data[0:2])}
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
        if self.type == Event.Types.RESET_ACTION:
            data = {'type': Event.ResetTypes.UNKNOWN,
                    'version': self._address_helper.decode(self._data[1:4])}
            if self._action == 2:
                data.update({'type': Event.ResetTypes.HEALTH_CHECK,
                             'cause': {1: Event.HealthResetCauses.I2C_1,
                                       2: Event.HealthResetCauses.I2C_2,
                                       3: Event.HealthResetCauses.CAN}.get(self._data[0], Event.HealthResetCauses.UNKNOWN)})
            elif self._action == 253:
                data.update({'type': Event.ResetTypes.CAN_STACK})
            elif self._action == 254:
                data.update({'type': Event.ResetTypes.PROCESSOR_RESET})
            return data
        return None

    def _word_decode(self, data):  # type: (List[int]) -> int
        return self._word_helper.decode(bytearray(data[0:2]))

    def __str__(self):
        return '{0} ({1})'.format(self.type, self.data if self.type != Event.Types.UNKNOWN else self._type)
