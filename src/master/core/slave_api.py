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
Contains the definition of the Slave API
"""

from __future__ import absolute_import
from master.core.slave_command import SlaveCommandSpec, Instruction
from master.core.fields import ByteField, VersionField, ByteArrayField, WordField


class SlaveAPI(object):

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
        def code_to_enum(item):  # type: (int) -> str
            return {0: SlaveAPI.ReturnCode.BOOTLOADER_ACTIVE,
                    1: SlaveAPI.ReturnCode.UNKNOWN_COMMAND,
                    2: SlaveAPI.ReturnCode.OUT_OF_BOUNCE,
                    3: SlaveAPI.ReturnCode.WRONG_FORMAT,
                    4: SlaveAPI.ReturnCode.WRONG_CRC,
                    5: SlaveAPI.ReturnCode.WRONG_PROGRAM_CRC,
                    6: SlaveAPI.ReturnCode.SEND_ADDRESS,
                    255: SlaveAPI.ReturnCode.APPLICATION_ACTIVE}[item]

    @staticmethod
    def get_firmware_version():  # type: () -> SlaveCommandSpec
        """ Gets a slave firmware version """
        return SlaveCommandSpec(instruction=Instruction(instruction='FV', padding=9),
                                response_fields=[ByteField('return_code'), ByteField('hardware_version'),
                                                 VersionField('version'), ByteField('status')])

    @staticmethod
    def goto_bootloader():  # type: () -> SlaveCommandSpec
        """ Instructs a slave to go to bootloader """
        return SlaveCommandSpec(instruction=Instruction(instruction='FR', padding=8),
                                request_fields=[ByteField('timeout')],
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def goto_application():  # type: () -> SlaveCommandSpec
        """ Instructs a slave to go to application """
        return SlaveCommandSpec(instruction=Instruction(instruction='FG', padding=9),
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def set_firmware_version():  # type: () -> SlaveCommandSpec
        """ Sets the version of the firmware version to flash """
        return SlaveCommandSpec(instruction=Instruction(instruction='FN', padding=6),
                                request_fields=[VersionField('version')],
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def set_firmware_crc():  # type: () -> SlaveCommandSpec
        """ Sets the CRC of the loaded firmware """
        return SlaveCommandSpec(instruction=Instruction(instruction='FC', padding=5),
                                request_fields=[ByteArrayField('crc', length=4)],
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def write_firmware_block():  # type: () -> SlaveCommandSpec
        """ Writes a single 64-byte firmware block to a given address """
        return SlaveCommandSpec(instruction=Instruction(instruction='FD'),
                                request_fields=[WordField('address'), ByteArrayField('payload', length=64)],
                                response_fields=[ByteField('return_code')])

    @staticmethod
    def integrity_check():  # type: () -> SlaveCommandSpec
        """ Runs an integrity check for the firmware """
        return SlaveCommandSpec(instruction=Instruction(instruction='FE', padding=9),
                                response_fields=[ByteField('return_code')])
