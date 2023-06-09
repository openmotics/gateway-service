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
Contains the definition of the Core API
"""

from __future__ import absolute_import
from master.core.core_command import CoreCommandSpec
from master.core.fields import (ByteField, WordField, ByteArrayField, WordArrayField, LiteralBytesField,
                                AddressField, CharField, PaddingField, VersionField, TemperatureArrayField,
                                HumidityArrayField, RawByteArrayField, SerialNumberField, Field, UInt32Field)


class CoreAPI(object):

    # TODO: Use property

    class SlaveBusMode(object):
        LIVE = 0
        INIT = DISCOVERY = 1
        TRANSPARENT = 2

    # Direct control

    @staticmethod
    def basic_action():  # type: () -> CoreCommandSpec
        """ Basic action spec """
        return CoreCommandSpec(instruction='BA',
                               request_fields=[ByteField('type'), ByteField('action'), WordField('device_nr'), WordField('extra_parameter')],
                               response_fields=[ByteField('type'), ByteField('action'), WordField('device_nr'), WordField('extra_parameter')])

    @staticmethod
    def execute_basic_action_series(length):  # type: (int) -> CoreCommandSpec
        """ Executes a Basic action on multiple devices """
        if not 2 <= length <= 40:
            raise ValueError('Amount of device numbers should be 2 <= n <= 40')
        return CoreCommandSpec(instruction='ES',
                               request_fields=[ByteField('type'), ByteField('action'), WordField('extra_parameter'), WordArrayField('device_nrs', length)],
                               response_fields=[ByteField('type'), ByteField('action'), WordField('extra_parameter')])

    # Events and other messages from Core to Gateway

    @staticmethod
    def event_information():  # type: () -> CoreCommandSpec
        """ Event information """
        return CoreCommandSpec(instruction='EV',
                               response_fields=[ByteField('type'), ByteField('action'), WordField('device_nr'), RawByteArrayField('data', 4)])

    @staticmethod
    def error_information():  # type: () -> CoreCommandSpec
        """ Error information """
        return CoreCommandSpec(instruction='ER',
                               response_fields=[ByteField('type'), ByteField('parameter_a'), WordField('parameter_b'), WordField('parameter_c')])

    @staticmethod
    def firmware_information():  # type: () -> CoreCommandSpec
        """ Firmware information """
        return CoreCommandSpec(instruction='FW',
                               response_fields=[AddressField('address'), VersionField('version')])

    @staticmethod
    def module_added():  # type: () -> CoreCommandSpec
        """ A module was added """
        return CoreCommandSpec(instruction='AM',
                               response_fields=[ByteField('module_type'), ByteField('line_number'), AddressField('address')])

    # Generic information and configuration

    @staticmethod
    def device_information_list_outputs():  # type: () -> CoreCommandSpec
        """ Device information list for output """
        return CoreCommandSpec(instruction='DL',
                               request_fields=[LiteralBytesField(0)],
                               response_fields=[ByteField('type'), ByteArrayField('information', lambda length: length - 1)])

    @staticmethod
    def device_information_list_inputs():  # type: () -> CoreCommandSpec
        """ Device information list for inputs """
        return CoreCommandSpec(instruction='DL',
                               request_fields=[LiteralBytesField(1)],
                               response_fields=[ByteField('type'), ByteArrayField('information', lambda length: length - 1)])

    @staticmethod
    def general_configuration_max_specs():  # type: () -> CoreCommandSpec
        """ Receives general configuration regarding maximum specifications (e.g. max number of input modules, max number of basic actions, ...) """
        return CoreCommandSpec(instruction='GC',
                               request_fields=[LiteralBytesField(1)],
                               response_fields=[ByteField('type'), ByteField('output'), ByteField('input'), ByteField('sensor'),
                                                ByteField('ucan'), WordField('groups'), WordField('basic_actions'),
                                                ByteField('shutters'), ByteField('shutter_groups')])

    @staticmethod
    def module_information():  # type: () -> CoreCommandSpec
        """ Receives module information """
        return CoreCommandSpec(instruction='MC',
                               request_fields=[ByteField('module_nr'), ByteField('module_family')],
                               response_fields=[ByteField('module_nr'), ByteField('module_family'), ByteField('module_type'),
                                                AddressField('address'), WordField('bus_errors'), ByteField('module_status')])

    @staticmethod
    def get_master_modes():  # type: () -> CoreCommandSpec
        """ Receives various master modes (rs485 bus mode, BA debug mode) """
        return CoreCommandSpec(instruction='ST',
                               request_fields=[LiteralBytesField(0)],
                               response_fields=[ByteField('info_type'), ByteField('rs485_mode'), ByteField('ba_debug_mode')])

    @staticmethod
    def get_firmware_version():  # type: () -> CoreCommandSpec
        """ Receives the Core firmware version """
        return CoreCommandSpec(instruction='ST',
                               request_fields=[LiteralBytesField(1)],
                               response_fields=[ByteField('info_type'), VersionField('version')])

    @staticmethod
    def request_slave_firmware_versions():  # type: () -> CoreCommandSpec
        """ Requests the slave firmware versions, which will be send to the GW in separate FW calls """
        return CoreCommandSpec(instruction='ST',
                               request_fields=[LiteralBytesField(2)],
                               response_fields=[ByteField('info_type'),
                                                ByteField('amount_output_modules'), ByteField('amount_input_modules'),
                                                ByteField('amount_sensor_modules'), ByteField('amount_can_control_modules')])

    @staticmethod
    def get_date_time():  # type: () -> CoreCommandSpec
        """ Reads the date/time from the Core """
        return CoreCommandSpec(instruction='TR',
                               request_fields=[LiteralBytesField(0)],
                               response_fields=[ByteField('info_type'),
                                                ByteField('hours'), ByteField('minutes'), ByteField('seconds'),
                                                ByteField('weekday'), ByteField('day'), ByteField('month'), ByteField('year')])

    @staticmethod
    def set_date_time():  # type: () -> CoreCommandSpec
        """ Writes the date/time from the Core """
        return CoreCommandSpec(instruction='TW',
                               request_fields=[LiteralBytesField(0),
                                               ByteField('hours'), ByteField('minutes'), ByteField('seconds'),
                                               ByteField('weekday'), ByteField('day'), ByteField('month'), ByteField('year')],
                               response_fields=[ByteField('info_type'),
                                                ByteField('hours'), ByteField('minutes'), ByteField('seconds'),
                                                ByteField('weekday'), ByteField('day'), ByteField('month'), ByteField('year')])

    # States

    @staticmethod
    def output_detail():  # type: () -> CoreCommandSpec
        """ Received output detail information """
        return CoreCommandSpec(instruction='OD',
                               request_fields=[WordField('device_nr')],
                               response_fields=[WordField('device_nr'), ByteField('status'),
                                                ByteField('dimmer'), ByteField('dimmer_min'), ByteField('dimmer_max'),
                                                ByteField('timer_type'), ByteField('timer_type_standard'),
                                                WordField('timer'), WordField('timer_standard'),
                                                WordField('group_action'), ByteField('dali_output'),
                                                ByteField('output_lock')])

    @staticmethod
    def sensor_temperature_values():  # type: () -> CoreCommandSpec
        """ Receive sensor temperature values """
        return CoreAPI._sensor_values(0, TemperatureArrayField('values', length=8))

    @staticmethod
    def sensor_humidity_values():  # type: () -> CoreCommandSpec
        """ Receive sensor humidity values """
        return CoreAPI._sensor_values(1, HumidityArrayField('values', length=8))

    @staticmethod
    def sensor_brightness_values():  # type: () -> CoreCommandSpec
        """ Receive sensor brightness values """
        return CoreAPI._sensor_values(2, WordArrayField('values', length=8))

    @staticmethod
    def sensor_co2_values():  # type: () -> CoreCommandSpec
        """ Receive sensor CO2 values """
        return CoreAPI._sensor_values(3, WordArrayField('values', length=8))

    @staticmethod
    def sensor_voc_values():  # type: () -> CoreCommandSpec
        """ Receive sensor VOC values """
        return CoreAPI._sensor_values(4, WordArrayField('values', length=8))

    @staticmethod
    def sensor_extra_values():  # type: () -> CoreCommandSpec
        """ Receive sensor extra values """
        return CoreAPI._sensor_values(5, WordArrayField('values', length=8))

    @staticmethod
    def _sensor_values(instruction, field):  # type: (int, Field) -> CoreCommandSpec
        """ Receive sensor byte values """
        return CoreCommandSpec(instruction='SI',
                               request_fields=[ByteField('module_nr'), LiteralBytesField(instruction)],
                               response_fields=[ByteField('module_nr'), PaddingField(1), field])

    @staticmethod
    def pulse_counter_values():  # type: () -> CoreCommandSpec
        """ Receives pulse counter values for a given module """
        return CoreCommandSpec(instruction='PC',
                               request_fields=[ByteField('series'), LiteralBytesField(0)],
                               response_fields=[ByteField('series'), PaddingField(1),
                                                UInt32Field('counter_0'), UInt32Field('counter_1'), UInt32Field('counter_2'), UInt32Field('counter_3'),
                                                UInt32Field('counter_4'), UInt32Field('counter_5'), UInt32Field('counter_6'), UInt32Field('counter_7'),
                                                WordField('crc16')])

    # Memory (EEPROM/FRAM) actions

    @staticmethod
    def memory_read():  # type: () -> CoreCommandSpec
        """ Reads memory """
        return CoreCommandSpec(instruction='MR',
                               request_fields=[CharField('type'), WordField('page'), ByteField('start'), ByteField('length')],
                               response_fields=[CharField('type'), WordField('page'), ByteField('start'), RawByteArrayField('data', lambda length: length - 4)])

    @staticmethod
    def memory_write(length):  # type: (int) -> CoreCommandSpec
        """ Writes memory """
        return CoreCommandSpec(instruction='MW',
                               request_fields=[CharField('type'), WordField('page'), ByteField('start'), RawByteArrayField('data', length)],
                               response_fields=[CharField('type'), WordField('page'), ByteField('start'), ByteField('length'), CharField('result')])

    # Slave bus

    @staticmethod
    def set_slave_bus_mode():  # type: () -> CoreCommandSpec
        """ Sets the slave bus to a different mode"""
        return CoreCommandSpec(instruction='SM',
                               request_fields=[ByteField('mode')],
                               response_fields=[ByteField('mode')])

    @staticmethod
    def slave_tx_transport_message(length):  # type: (int) -> CoreCommandSpec
        """ Slave transport layer packages """
        return CoreCommandSpec(instruction='TC',
                               request_fields=[RawByteArrayField('payload', length)],
                               response_fields=[ByteField('length')])

    @staticmethod
    def slave_rx_transport_message():  # type: () -> CoreCommandSpec
        """ Slave transport layer packages """
        return CoreCommandSpec(instruction='TM',
                               response_fields=[RawByteArrayField('payload', lambda length: length)])

    # CAN

    @staticmethod
    def get_amount_of_ucans():  # type: () -> CoreCommandSpec
        """ Receives amount of uCAN modules """
        return CoreCommandSpec(instruction='FS',
                               request_fields=[AddressField('cc_address'), LiteralBytesField(0), LiteralBytesField(0)],
                               response_fields=[AddressField('cc_address'), PaddingField(2), ByteField('amount'), PaddingField(2)])

    @staticmethod
    def get_ucan_address():  # type: () -> CoreCommandSpec
        """ Receives the uCAN address of a specific uCAN """
        return CoreCommandSpec(instruction='FS',
                               request_fields=[AddressField('cc_address'), LiteralBytesField(1), ByteField('ucan_nr')],
                               response_fields=[AddressField('cc_address'), PaddingField(2), AddressField('ucan_address', 3)])

    @staticmethod
    def ucan_tx_transport_message():  # type: () -> CoreCommandSpec
        """ uCAN transport layer packages """
        return CoreCommandSpec(instruction='FM',
                               request_fields=[AddressField('cc_address'), ByteField('nr_can_bytes'), ByteField('sid'), RawByteArrayField('payload', 8)],
                               response_fields=[AddressField('cc_address')])

    @staticmethod
    def ucan_rx_transport_message():  # type: () -> CoreCommandSpec
        """ uCAN transport layer packages """
        return CoreCommandSpec(instruction='FM',
                               response_fields=[AddressField('cc_address'), ByteField('nr_can_bytes'), ByteField('sid'), RawByteArrayField('payload', 8)])

    @staticmethod
    def request_ucan_module_information():  # type: () -> CoreCommandSpec
        """ Requests information for all uCAN modules """
        return CoreCommandSpec(instruction='CD',
                               request_fields=[LiteralBytesField(0)],
                               response_fields=[PaddingField(1), ByteField('amount_of_ucans')])

    @staticmethod
    def ucan_module_information():  # type: () -> CoreCommandSpec
        """ Receives information from a uCAN module """
        return CoreCommandSpec(instruction='CD',
                               response_fields=[AddressField('ucan_address', 3), WordArrayField('input_links', 6),
                                                ByteArrayField('sensor_links', 2), ByteField('sensor_type'), VersionField('version'),
                                                ByteField('bootloader'), CharField('new_indicator'),
                                                ByteField('min_led_brightness'), ByteField('max_led_brightness'),
                                                ByteField('hardware_revision'), SerialNumberField('serial_number'),
                                                WordField('dc_voltage'), ByteArrayField('can_speed_parameters', 5)])
