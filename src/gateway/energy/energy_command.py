# Copyright (C) 2016 OpenMotics BV
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
Contains EnergyCommandClass that describes a command to the power modules. The EnergyCommand
class is used to create the EnergyAPI.
"""

from __future__ import absolute_import

import struct
import sys

if False:  # MYPY
    from typing import Any, Optional, Tuple, Union
    DataType = Union[float, int, str]

STR = bytearray(b'STR')
RTR = bytearray(b'RTR')
CRNL = bytearray(b'\r\n')

CRC_TABLE = [0, 49, 98, 83, 196, 245, 166, 151, 185, 136, 219, 234, 125, 76, 31, 46, 67, 114, 33,
             16, 135, 182, 229, 212, 250, 203, 152, 169, 62, 15, 92, 109, 134, 183, 228, 213, 66,
             115, 32, 17, 63, 14, 93, 108, 251, 202, 153, 168, 197, 244, 167, 150, 1, 48, 99, 82,
             124, 77, 30, 47, 184, 137, 218, 235, 61, 12, 95, 110, 249, 200, 155, 170, 132, 181,
             230, 215, 64, 113, 34, 19, 126, 79, 28, 45, 186, 139, 216, 233, 199, 246, 165, 148,
             3, 50, 97, 80, 187, 138, 217, 232, 127, 78, 29, 44, 2, 51, 96, 81, 198, 247, 164, 149,
             248, 201, 154, 171, 60, 13, 94, 111, 65, 112, 35, 18, 133, 180, 231, 214, 122, 75, 24,
             41, 190, 143, 220, 237, 195, 242, 161, 144, 7, 54, 101, 84, 57, 8, 91, 106, 253, 204,
             159, 174, 128, 177, 226, 211, 68, 117, 38, 23, 252, 205, 158, 175, 56, 9, 90, 107, 69,
             116, 39, 22, 129, 176, 227, 210, 191, 142, 221, 236, 123, 74, 25, 40, 6, 55, 100, 85,
             194, 243, 160, 145, 71, 118, 37, 20, 131, 178, 225, 208, 254, 207, 156, 173, 58, 11,
             88, 105, 4, 53, 102, 87, 192, 241, 162, 147, 189, 140, 223, 238, 121, 72, 27, 42, 193,
             240, 163, 146, 5, 52, 103, 86, 120, 73, 26, 43, 188, 141, 222, 239, 130, 179, 224, 209,
             70, 119, 36, 21, 59, 10, 89, 104, 255, 206, 157, 172]


def crc7(to_send):
    # type: (bytearray) -> int
    """
    Calculate the crc7 checksum of a string.
    """
    ret = 0
    for part in to_send:
        ret = CRC_TABLE[ret ^ part]
    return ret


def crc8(to_send):
    # type: (bytearray) -> int
    """
    Calculate the crc8 checksum of a string.
    """
    def _add_crc(crc, data):
        for bitnumber in range(0, 8):
            if (data ^ crc) & 0x80:
                crc = (crc << 1) ^ 0x31
            else:
                crc = (crc << 1)
            data = data << 1
        return crc & 0xFF

    ret = 0
    for part in to_send:
        ret = _add_crc(ret, part)
    return ret


class EnergyModuleType(object):
    E = bytearray(b'E')
    C = bytearray(b'C')


class EnergyCommand(object):
    """
    A EnergyCommand is an command that can be send to a Power Module over RS485. The commands
    look like this: 'STR' 'E' Address CID Mode(G/S) Type LEN Data CRC7/8 '\r\n'.
    """

    def __init__(self, mode, command, input_format, output_format,
                 module_type=EnergyModuleType.E):
        # type: (str, str, str, Optional[str], bytearray) -> None
        """
        Create EnergyCommand using the fixed fields of the input command and the format of the
        command returned by the power module.
        :param module_type: 1 character, E (energy/power module) or C (P1 concentrator)
        :param mode: 1 character, S or G
        :param command: 3 byte string, command itself
        :param input_format: the format of the data in the command
        :param output_format: the format of the data returned by the power module
        """
        self.mode = bytearray(ord(c) for c in mode)
        self.command = bytearray(ord(c) for c in command)
        self.input_format = input_format
        self.output_format = output_format if output_format is not None else ""
        self.module_type = module_type

    @staticmethod
    def get_crc(header, payload):
        # type: (bytearray) -> int
        if header[:1] == EnergyModuleType.E:
            return crc7(header + payload)
        else:
            return crc8(payload)

    def create_input(self, address, cid, *data):
        # type: (int, int, *DataType) -> bytearray
        """
        Create an input string for the power module using this command and the provided fields.
        :param address: 1 byte, the address of the module
        :param cid: 1 byte, communication id
        :param data: data to send to the power module
        """
        buffer = bytearray(struct.pack(self.input_format, *data))
        header = self.module_type + bytearray([address, cid]) + self.mode + self.command
        payload = bytearray([len(buffer)]) + buffer
        crc = EnergyCommand.get_crc(header, payload)
        return STR + header + payload + bytearray([crc]) + CRNL

    def create_output(self, address, cid, *data):
        # type: (int, int, *DataType) -> bytearray
        """
        Create an output command from the power module using this command and the provided
        fields. --- Only used for testing !
        :param address: 1 byte, the address of the module
        :param cid: 1 byte, communication id
        :param data: data to send to the power module
        """
        buffer = bytearray(struct.pack(self.output_format, *data))
        header = self.module_type + bytearray([address, cid]) + self.mode + self.command
        payload = bytearray([len(buffer)]) + buffer
        crc = EnergyCommand.get_crc(header, payload)
        return RTR + header + payload + bytearray([crc]) + CRNL

    def check_header(self, header, address, cid):
        # type: (bytearray, int, int) -> bool
        """
        Check if the response header matches the command,
        when an address and cid are provided. """
        return header[:-1] == self.module_type + bytearray([address, cid]) + self.mode + self.command

    def is_nack(self, header, address, cid):
        # type: (bytearray, int, int) -> bool
        """
        Check if the response header is a nack to the command, when an address and cid are
        provided. """
        return header[:-1] == self.module_type + bytearray([address, cid]) + self.command

    def check_header_partial(self, header):
        # type: (bytearray) -> bool
        """ Check if the header matches the command, does not check address and cid. """
        return header[:1] == self.module_type \
            and header[3:-1] == self.mode + self.command

    def read_output(self, data):
        # type: (Any) -> Tuple[Any, ...]
        """
        Parse the output using the output_format.
        :param data: string containing the data.
        """
        if sys.version_info[:3] <= (2, 7, 3):
            data = str(data)
        if self.output_format is None:
            return struct.unpack('%dB' % len(data), data)
        else:
            return struct.unpack(self.output_format, data)

    def __eq__(self, other):
        if not isinstance(other, EnergyCommand):
            return False
        return self.mode == other.mode \
            and self.command == other.command \
            and self.input_format == other.input_format \
            and self.output_format == other.output_format \
            and self.module_type == other.module_type

    def __repr__(self):
        return '<EnergyCommand {} {} {} {} {}>'.format(self.mode, self.command, self.input_format, self.output_format, self.module_type)
