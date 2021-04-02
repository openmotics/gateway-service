#!/bin/python2
# Copyright (C) 2021 OpenMotics BV
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

import fcntl
import struct
import sys
from serial import Serial

TIOCSRS485 = 0x542F
SER_RS485_ENABLED = 0b00000001
SER_RS485_RTS_ON_SEND = 0b00000010


def watch(port):
    try:
        serial = Serial(port, 115200, timeout=None)
        fileno = serial.fileno()
        if fileno is not None:
            flags_rs485 = SER_RS485_ENABLED | SER_RS485_RTS_ON_SEND
            serial_rs485 = struct.pack('hhhhhhhh', flags_rs485, 0, 0, 0, 0, 0, 0, 0)
            fcntl.ioctl(fileno, TIOCSRS485, serial_rs485)
        buffer = ''
        while True:
            buffer += serial.read(1)
            _print(buffer)
            if buffer == 'ping\r':
                _print(buffer)
                serial.write('pong\r\n')
                buffer = ''
    except KeyboardInterrupt:
        print('Exit')


def _print(buffer):
    byte_notation = ' '.join(['{0: >3}'.format(ord(c)) for c in buffer])
    string_notation = ''.join([c if 32 < ord(c) <= 126 else '.' for c in buffer])
    print('{0}    {1}'.format(byte_notation, string_notation))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Replies with `pong` when `ping` is received using an RS485-to-USB converter')
        print('Usage: ./rs485_pingpong.py port')
        sys.exit(1)
    watch(sys.argv[1])
