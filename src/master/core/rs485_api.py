# Copyright (C) 2020 OpenMotics BV
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
Contains the definition of the RS485 API
"""

from __future__ import absolute_import
from master.core.rs485_command import RS485CommandSpec, Instruction
from master.core.fields import ByteField, VersionField, ByteArrayField, WordField


class RS485API(object):

    class ReturnCode(object):
        BOOTLOADER_ACTIVE = 'BOOTLOADER_ACTIVE'
        UNKNOWN_COMMAND = 'UNKNOWN_COMMAND'
        OUT_OF_BOUNCE = 'OUT_OF_BOUNCE'
        WRONG_FORMAT = 'WRONG_FORMAT'
        WRONG_CRC = 'WRONG_CRC'
        WRONG_PROGRAM_CRC = 'WRONG_PROGRAM_CRC'
        SEND_ADDRESS = 'SEND_ADDRESS'
        APPLICATION_ACTIVE = 'APPLICATION_ACTIVE'

        ERRORS = [UNKNOWN_COMMAND, OUT_OF_BOUNCE, WRONG_FORMAT, WRONG_CRC, WRONG_PROGRAM_CRC, SEND_ADDRESS]

        @staticmethod
        def code_to_enum(item):
            return {0: RS485API.ReturnCode.BOOTLOADER_ACTIVE,
                    1: RS485API.ReturnCode.UNKNOWN_COMMAND,
                    2: RS485API.ReturnCode.OUT_OF_BOUNCE,
                    3: RS485API.ReturnCode.WRONG_FORMAT,
                    4: RS485API.ReturnCode.WRONG_CRC,
                    5: RS485API.ReturnCode.WRONG_PROGRAM_CRC,
                    6: RS485API.ReturnCode.SEND_ADDRESS,
                    255: RS485API.ReturnCode.APPLICATION_ACTIVE}[item]

    @staticmethod
    def get_firmware_version():
        """ Gets a slave firmware version """
        return RS485CommandSpec(instruction=Instruction(instruction='FV', padding=9),
                                response_fields=[ByteField('return_code'), ByteField('hardware_version'),
                                                 VersionField('version'), ByteField('status')])

    @staticmethod
    def goto_bootloader():
        """ Instructs a slave to go to bootloader """
        return RS485CommandSpec(instruction=Instruction(instruction='FR', padding=8),
                                request_fields=[ByteField('timeout')],
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def goto_application():
        """ Instructs a slave to go to application """
        return RS485CommandSpec(instruction=Instruction(instruction='FG', padding=9),
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def set_firmware_version():
        """ Sets the version of the firmware version to flash """
        return RS485CommandSpec(instruction=Instruction(instruction='FN', padding=6),
                                request_fields=[VersionField('version')],
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def set_firmware_crc():
        """ Sets the CRC of the loaded firmware """
        return RS485CommandSpec(instruction=Instruction(instruction='FC', padding=5),
                                request_fields=[ByteArrayField('crc', length=4)],
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def write_firmware_block():
        """ Writes a single 64-byte firmware block to a given address """
        return RS485CommandSpec(instruction=Instruction(instruction='FD'),
                                request_fields=[WordField('address'), ByteArrayField('payload', length=64)],
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def integrity_check():
        """ Runs an integrity check for the firmware """
        return RS485CommandSpec(instruction=Instruction(instruction='FE', padding=9),
                                response_fields=[ByteField('return_code')])
