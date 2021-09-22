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
from gateway.enums import ModuleType
from master.core.fields import WordField, AddressField
from master.core.system_value import Temperature, Humidity, Timer
from master.core.basic_action import BasicAction

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
        MODULE_DISCOVERY = 'MODULE_DISCOVERY'
        SLAVE_SEARCH = 'SLAVE_SEARCH'
        BUTTON_PRESS = 'BUTTON_PRESS'
        LED_ON = 'LED_ON'
        LED_BLINK = 'LED_BLINK'
        UCAN = 'UCAN'
        EXECUTE_GATEWAY_API = 'EXECUTE_GATEWAY_API'
        MODULE_NOT_RESPONDING = 'MODULE_NOT_RESPONDING'
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
        STARTUP_COMPLETED = 'STARTUP_COMPLETED'
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

    class DiscoveryTypes(object):
        NEW = 'NEW'
        EXISTING = 'EXISTING'
        DUPLICATE = 'DUPLICATE'
        UNKNOWN = 'UNKNOWN'

    class SearchType(object):
        ACTIVE = 'ACTIVE'
        STOPPED = 'STOPPED'
        DISABLED = 'DISABLED'
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

    TYPE_MAP = {0: Types.OUTPUT,
                1: Types.INPUT,
                2: Types.SENSOR,
                20: Types.THERMOSTAT,
                21: Types.UCAN,
                22: Types.EXECUTED_BA,
                23: Types.MODULE_NOT_RESPONDING,
                24: Types.MODULE_NOT_RESPONDING,
                245: Types.MODULE_DISCOVERY,
                246: Types.SLAVE_SEARCH,
                247: Types.GENERIC_DATA,
                248: Types.SYSTEM,
                249: Types.EXECUTE_GATEWAY_API,
                250: Types.BUTTON_PRESS,
                251: Types.LED_BLINK,
                252: Types.LED_ON,
                253: Types.POWER,
                254: Types.RESET_ACTION}

    def __init__(self, data):
        self._type = data['type']
        self.type = Event.TYPE_MAP.get(self._type, Event.Types.UNKNOWN)
        self.data = self._parse_data(action=data['action'],
                                     device_nr=data['device_nr'],
                                     data=data['data'])

    @staticmethod
    def build(event_type, event_data):
        event = Event(data={'type': None,
                            'action': None,
                            'device_nr': None,
                            'data': None})
        event.type = event_type
        event.data = event_data
        return event

    def _parse_data(self, action, device_nr, data):
        word_helper = WordField('')
        ucan_address_helper = AddressField('', length=3)
        address_helper = AddressField('', length=4)

        if self.type == Event.Types.OUTPUT:
            parsed_data = {'output': device_nr}
            if action in [0, 1]:
                timer_type = data[1]  # type: int
                print(data[2:])
                timer_value = word_helper.decode(bytearray(data[2:])) or 0  # type: int
                timer = Timer.event_timer_type_to_seconds(timer_type, timer_value)
                parsed_data.update({'type': Event.IOEventTypes.STATUS,
                                    'status': action == 1,
                                    'dimmer_value': data[0],
                                    'timer': timer})
            else:
                parsed_data.update({'type': Event.IOEventTypes.LOCKING,
                                    'locked': data[0] == 1})
            return parsed_data
        if self.type == Event.Types.INPUT:
            parsed_data = {'input': device_nr}
            if action in [0, 1]:
                parsed_data.update({'type': Event.IOEventTypes.STATUS,
                                    'status': action == 1})
            else:
                parsed_data.update({'type': Event.IOEventTypes.LOCKING,
                                    'locked': data[0] == 1})
            return parsed_data
        if self.type == Event.Types.SENSOR:
            sensor_values = []
            if action == 0:
                sensor_values += [{'type': Event.SensorType.TEMPERATURE,
                                   'value': Temperature.system_value_to_temperature(data[1])}]
            elif action == 1:
                sensor_values += [{'type': Event.SensorType.HUMIDITY,
                                   'value': Humidity.system_value_to_humidity(data[1])}]
            elif action == 2:
                sensor_values += [{'type': Event.SensorType.BRIGHTNESS,
                                   'value': word_helper.decode(bytearray(data[0:2]))}]
            elif action == 3:
                sensor_values += [{'type': Event.SensorType.CO2,
                                   'value': word_helper.decode(bytearray(data[0:2]))},
                                  {'type': Event.SensorType.VOC,
                                   'value': word_helper.decode(bytearray(data[2:4]))}]
            return {'sensor': device_nr,
                    'values': sensor_values}
        if self.type == Event.Types.THERMOSTAT:
            origin_map = {0: Event.ThermostatOrigins.SLAVE,
                          1: Event.ThermostatOrigins.MASTER}
            return {'origin': origin_map.get(action, Event.ThermostatOrigins.UNKNOWN),
                    'thermostat': device_nr,
                    'mode': data[0],
                    'setpoint': data[1]}
        if self.type == Event.Types.UCAN:
            parsed_data = {'address': ucan_address_helper.decode(bytearray([device_nr & 0xFF]) + data[0:2])}
            if data[2] == 0 and data[3] == 0:
                parsed_data['type'] = Event.UCANEventTypes.POWER_OUT_ERROR
            elif data[2] == 0 and data[3] == 1:
                parsed_data['type'] = Event.UCANEventTypes.POWER_OUT_RESTORED
            elif data[2] == 0 and data[3] == 2:
                parsed_data['type'] = Event.UCANEventTypes.POWER_OUT_OFF
            elif data[2] == 0 and data[3] == 3:
                parsed_data['type'] = Event.UCANEventTypes.RESTARTED
            elif data[2] == 2 and data[3] == 3:
                parsed_data['type'] = Event.UCANEventTypes.POWER_OUT_ON
            elif data[2] == 1:
                parsed_data.update({'type': Event.UCANEventTypes.I2C_ERROR,
                                    'i2c_address': data[3]})
            else:
                parsed_data.update({'type': Event.UCANEventTypes.UNKNOWN,
                                    'data': data[2:4]})
            return parsed_data
        if self.type == Event.Types.EXECUTED_BA:
            return {'basic_action': BasicAction(action_type=data[0],
                                                action=data[1],
                                                device_nr=device_nr,
                                                extra_parameter=word_helper.decode(bytearray(data[2:4])))}
        if self.type == Event.Types.MODULE_NOT_RESPONDING:
            if self._type == 23:
                return {'bus': Event.Bus.CAN,
                        'address': ucan_address_helper.decode(bytearray([device_nr & 0xFF]) + data[0:2])}
            return {'bus': Event.Bus.RS485,
                    'address': address_helper.decode(bytearray([device_nr & 0xFF]) + data[0:3])}
        if self.type == Event.Types.MODULE_DISCOVERY:
            types_map = {5: (Event.DiscoveryTypes.EXISTING, ModuleType.OUTPUT),
                         6: (Event.DiscoveryTypes.EXISTING, ModuleType.INPUT),
                         7: (Event.DiscoveryTypes.EXISTING, ModuleType.SENSOR),
                         8: (Event.DiscoveryTypes.EXISTING, ModuleType.CAN_CONTROL),
                         9: (Event.DiscoveryTypes.DUPLICATE, ModuleType.OUTPUT),
                         10: (Event.DiscoveryTypes.DUPLICATE, ModuleType.INPUT),
                         11: (Event.DiscoveryTypes.DUPLICATE, ModuleType.SENSOR),
                         12: (Event.DiscoveryTypes.DUPLICATE, ModuleType.CAN_CONTROL)}
            types = types_map.get(device_nr & 0xFF, (Event.DiscoveryTypes.UNKNOWN, ModuleType.UNKNOWN))
            return {'discovery_type': types[0],
                    'module_type': types[1],
                    'address': address_helper.decode(data),
                    'module_number': None}
        if self.type == Event.Types.SLAVE_SEARCH:
            type_map = {0: Event.SearchType.DISABLED,
                        1: Event.SearchType.ACTIVE,
                        2: Event.SearchType.STOPPED}
            return {'type': type_map.get(data[0], Event.SearchType.UNKNOWN),
                    'setting': data[1]}
        if self.type == Event.Types.GENERIC_DATA:
            if action == 0:
                return {'action': Event.GenericDataTypes.PCB_TEMPERATURE,
                        'temperature': device_nr & 0xFF}
            return {'action': Event.GenericDataTypes.UNKNOWN,
                    'device_nr': device_nr,
                    'data': data}
        if self.type == Event.Types.SYSTEM:
            if action == 0:
                parsed_data = {'type': Event.SystemEventTypes.EEPROM_ACTIVATE}
                if data[0] == 0:
                    parsed_data['type'] = Event.SystemEventTypes.STARTUP_COMPLETED
                return parsed_data
            if action == 2:
                return {'type': Event.SystemEventTypes.I2C_RESET,
                        'cause': data[0]}
            if action == 3:
                parsed_data = {'type': Event.SystemEventTypes.HEALTH,
                               'health_type': Event.SystemHealthTypes.UNKNOWN}
                if data[0] == 0:
                    can_health_map = {1: Event.CANHealthTypes.NO_UCAN_OK,
                                      2: Event.CANHealthTypes.ALL_UCAN_OK,
                                      3: Event.CANHealthTypes.SOME_UCAN_OK,
                                      4: Event.CANHealthTypes.CAN_BUS_OFF}
                    parsed_data.update({'health_type': Event.SystemHealthTypes.CAN,
                                        'current': can_health_map.get(data[1], Event.CANHealthTypes.UNKNOWN),
                                        'previous': can_health_map.get(data[2], Event.CANHealthTypes.UNKNOWN)})
                return parsed_data
            return {'type': Event.SystemEventTypes.UNKNOWN}
        if self.type == Event.Types.EXECUTE_GATEWAY_API:
            return {'action': data[3],
                    'device_nr': device_nr,
                    'extra_parameter': word_helper.decode(bytearray(data[0:2]))}
        if self.type == Event.Types.BUTTON_PRESS:
            return {'button': device_nr,
                    'state': data[0]}
        if self.type == Event.Types.LED_BLINK:
            word_25 = device_nr
            word_50 = word_helper.decode(bytearray(data[0:2]))
            word_75 = word_helper.decode(bytearray(data[2:4]))
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
            return {'chip': device_nr,
                    'leds': leds}
        if self.type == Event.Types.LED_ON:
            word_on = word_helper.decode(bytearray(data[0:2]))
            leds = {}
            for i in range(16):
                leds[i] = Event.LedStates.ON if word_on & (1 << i) else Event.LedStates.OFF
            return {'chip': device_nr,
                    'leds': leds}
        if self.type == Event.Types.POWER:
            return {'bus': Event.Bus.RS485 if device_nr == 0 else Event.Bus.CAN,
                    'power': data[0 > 1]}
        if self.type == Event.Types.RESET_ACTION:
            parsed_data = {'type': Event.ResetTypes.UNKNOWN,
                           'version': ucan_address_helper.decode(bytearray(data[1:4]))}
            if action == 2:
                parsed_data.update({'type': Event.ResetTypes.HEALTH_CHECK,
                                    'cause': {1: Event.HealthResetCauses.I2C_1,
                                              2: Event.HealthResetCauses.I2C_2,
                                              3: Event.HealthResetCauses.CAN}.get(data[0], Event.HealthResetCauses.UNKNOWN)})
            elif action == 253:
                parsed_data.update({'type': Event.ResetTypes.CAN_STACK})
            elif action == 254:
                parsed_data.update({'type': Event.ResetTypes.PROCESSOR_RESET})
            return parsed_data
        return None

    def __str__(self):
        return '{0} ({1})'.format(self.type, self.data if self.type != Event.Types.UNKNOWN else self._type)
