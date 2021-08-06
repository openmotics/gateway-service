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
from master.core.ucan_command import UCANCommandSpec, UCANPalletCommandSpec, SID, PalletType, Instruction
from master.core.fields import AddressField, ByteField, WordField, VersionField, StringField, UInt32Field, ByteArrayField, LiteralBytesField


class UCANAPI(object):

    @staticmethod
    def ping(sid=SID.NORMAL_COMMAND):  # type: (int) -> UCANCommandSpec
        """ Basic action spec """
        return UCANCommandSpec(sid=sid,
                               identifier=AddressField('ucan_address', 3),
                               instructions=[Instruction(instruction=[0, 96])],
                               request_fields=[[ByteField('data')]],
                               response_instructions=[Instruction(instruction=[1, 96], checksum_byte=6)],
                               response_fields=[ByteField('data')])

    @staticmethod
    def read_ucan_config():  # type: () -> UCANCommandSpec
        """ Reads the full uCAN config """
        return UCANCommandSpec(sid=SID.NORMAL_COMMAND,
                               identifier=AddressField('ucan_address', 3),
                               instructions=[Instruction(instruction=[0, 199])],
                               response_instructions=[Instruction(instruction=[i, 199], checksum_byte=7) for i in range(1, 14)],
                               response_fields=[ByteField('input_link_0'), ByteField('input_link_1'), ByteField('input_link_2'),
                                                ByteField('input_link_3'), ByteField('input_link_4'), ByteField('input_link_5'),
                                                ByteField('sensor_link_0'), ByteField('sensor_link_1'), ByteField('sensor_type'),
                                                VersionField('firmware_version'), ByteField('bootloader'), ByteField('new_indicator'),
                                                ByteField('min_led_brightness'), ByteField('max_led_brightness'),
                                                WordField('adc_input_2'), WordField('adc_input_3'), WordField('adc_input_4'),
                                                WordField('adc_input_5'), WordField('adc_dc_input')])

    @staticmethod
    def get_version():  # type: () -> UCANCommandSpec
        """ Gets a uCAN version """
        return UCANCommandSpec(sid=SID.NORMAL_COMMAND,
                               identifier=AddressField('ucan_address', 3),
                               instructions=[Instruction(instruction=[0, 198]), Instruction(instruction=[0, 198])],
                               request_fields=[[LiteralBytesField(5)], [LiteralBytesField(6)]],
                               response_instructions=[Instruction(instruction=[5, 199], checksum_byte=7),
                                                      Instruction(instruction=[6, 199], checksum_byte=7)],
                               response_fields=[ByteField('sensor_type'), VersionField('firmware_version')])

    @staticmethod
    def set_min_led_brightness():  # type: () -> UCANCommandSpec
        """ Sets the minimum brightness for a uCAN led """
        return UCANCommandSpec(sid=SID.NORMAL_COMMAND,
                               identifier=AddressField('ucan_address', 3),
                               instructions=[Instruction(instruction=[0, 246])],
                               request_fields=[[ByteField('brightness')]])

    @staticmethod
    def set_max_led_brightness():  # type: () -> UCANCommandSpec
        """ Sets the maximum brightness for a uCAN led """
        return UCANCommandSpec(sid=SID.NORMAL_COMMAND,
                               identifier=AddressField('ucan_address', 3),
                               instructions=[Instruction(instruction=[0, 247])],
                               request_fields=[[ByteField('brightness')]])

    @staticmethod
    def set_bootloader_timeout(sid=SID.NORMAL_COMMAND):  # type: (int) -> UCANCommandSpec
        """ Sets the bootloader timeout """
        return UCANCommandSpec(sid=sid,
                               identifier=AddressField('ucan_address', 3),
                               instructions=[Instruction(instruction=[0, 123])],
                               request_fields=[[ByteField('timeout')]],
                               response_instructions=[Instruction(instruction=[123, 123], checksum_byte=6)],
                               response_fields=[ByteField('timeout')])

    @staticmethod
    def reset(sid=SID.NORMAL_COMMAND):  # type: (int) -> UCANCommandSpec
        """ Resets the uCAN """
        return UCANCommandSpec(sid=sid,
                               identifier=AddressField('ucan_address', 3),
                               instructions=[Instruction(instruction=[0, 94])],
                               response_instructions=[Instruction(instruction=[94, 94], checksum_byte=6)],
                               response_fields=[ByteField('application_mode')])

    @staticmethod
    def set_bootloader_safety_counter():  # type: () -> UCANCommandSpec
        """ Sets the bootloader's safety flag """
        return UCANCommandSpec(sid=SID.BOOTLOADER_COMMAND,
                               identifier=AddressField('ucan_address', 3),
                               instructions=[Instruction(instruction=[0, 125])],
                               request_fields=[[ByteField('safety_counter')]],
                               response_instructions=[Instruction(instruction=[125, 125], checksum_byte=6)],
                               response_fields=[ByteField('safety_counter')])

    @staticmethod
    def get_mcu_id():  # type: () -> UCANCommandSpec
        """
        Gets the uCAN mcu ID
        Note: uCAN needs to be in bootloader
        """
        return UCANPalletCommandSpec(identifier=AddressField('ucan_address', 3),
                                     pallet_type=PalletType.MCU_ID_REQUEST,
                                     response_fields=[StringField('mcu_id')])

    @staticmethod
    def get_bootloader_version():  # type: () -> UCANCommandSpec
        """
        Gets the uCAN bootloader version
        Note: uCAN needs to be in bootloader
        """
        return UCANPalletCommandSpec(identifier=AddressField('ucan_address', 3),
                                     pallet_type=PalletType.BOOTLOADER_ID_REQUEST,
                                     response_fields=[ByteField('major'), ByteField('minor')])

    @staticmethod
    def write_flash(data_length):  # type: (int) -> UCANCommandSpec
        """
        Writes uCAN flash
        Note: uCAN needs to be in bootloader
        """
        return UCANPalletCommandSpec(identifier=AddressField('ucan_address', 3),
                                     pallet_type=PalletType.FLASH_WRITE_REQUEST,
                                     request_fields=[UInt32Field('start_address'), ByteArrayField('data', data_length)],
                                     response_fields=[ByteField('success')])

    @staticmethod
    def read_flash(data_length):  # type: (int) -> UCANCommandSpec
        """
        Reads uCAN flash
        Note: uCAN needs to be in bootloader
        """
        return UCANPalletCommandSpec(identifier=AddressField('ucan_address', 3),
                                     pallet_type=PalletType.FLASH_READ_REQUEST,
                                     request_fields=[UInt32Field('start_address'), ByteField('data_length')],
                                     response_fields=[ByteArrayField('data', data_length)])

    @staticmethod
    def erase_flash():  # type: () -> UCANCommandSpec
        """
        Erases uCAN flash
        Note: uCAN needs to be in bootloader
        """
        return UCANPalletCommandSpec(identifier=AddressField('ucan_address', 3),
                                     pallet_type=PalletType.FLASH_ERASE_REQUEST,
                                     response_fields=[ByteField('success')])
