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
Serial tools contains the RS485 wrapper, Printable` and CommunicationTimedOutException.
"""

from __future__ import absolute_import

import fcntl
import struct

from six.moves.queue import Queue

from gateway.daemon_thread import BaseThread
from gateway.exceptions import CommunicationFailure

if False:  # MYPY
    from typing import Literal, Any
    from serial import Serial


class CommunicationTimedOutException(CommunicationFailure):
    """ An exception that is raised when the master did not respond in time. """
    def __init__(self, message=''):
        if not message:
            message = self.__class__.__name__
        super(CommunicationTimedOutException, self).__init__(message)


class CommunicationStatus(object):
    SUCCESS = 'success'  # type: Literal['success', 'unstable', 'failure']
    UNSTABLE = 'unstable'  # type: Literal['success', 'unstable', 'failure']
    FAILURE = 'failure'  # type: Literal['success', 'unstable', 'failure']


class Printable(object):

    def __init__(self, data):  # type: (Any) -> None
        self.data = data

    def __str__(self):
        """ prints data in a human-redable way """

        if isinstance(self.data, list) or isinstance(self.data, bytearray):
            byte_notation = ' '.join(['{0: >3}'.format(i) for i in self.data])
            string_notation = ''.join([str(chr(i)) if 32 < i <= 126 else '.' for i in self.data])
        else:
            byte_notation = ' '.join(['{0: >3}'.format(ord(c)) for c in self.data])
            string_notation = ''.join([c if 32 < ord(c) <= 126 else '.' for c in self.data])
        return '{0}    {1}'.format(byte_notation, string_notation)


TIOCSRS485 = 0x542F
SER_RS485_ENABLED = 0b00000001
SER_RS485_RTS_ON_SEND = 0b00000010


class RS485(object):
    """ Replicates the pyserial interface. """

    def __init__(self, serial):
        # type: (Serial) -> None
        """ Initialize a rs485 connection using the serial port. """
        self._serial = serial
        fileno = serial.fileno()
        if fileno is not None:
            flags_rs485 = SER_RS485_ENABLED | SER_RS485_RTS_ON_SEND
            serial_rs485 = struct.pack('hhhhhhhh', flags_rs485, 0, 0, 0, 0, 0, 0, 0)
            fcntl.ioctl(fileno, TIOCSRS485, serial_rs485)

        self._serial.timeout = None
        self._running = False
        self._thread = BaseThread(name='rS485read', target=self._reader)
        self._thread.daemon = True
        # TODO why does this stream byte by byte?
        self.read_queue = Queue()  # type: Queue[bytearray]

    def start(self):
        # type: () -> None
        if not self._running:
            self._running = True
            self._thread.start()

    def stop(self):
        # type: () -> None
        self._running = False

    def write(self, data):
        # type: (bytes) -> None
        """ Write data to serial port """
        self._serial.write(data)

    def _reader(self):
        # type: () -> None
        try:
            while self._running:
                data = bytearray(self._serial.read(1))
                if len(data) == 1:
                    self.read_queue.put(data[:1])
                size = self._serial.inWaiting()
                if size > 0:
                    data = bytearray(self._serial.read(size))
                    for i in range(size):
                        self.read_queue.put(data[i:i + 1])
        except Exception as ex:
            print('Error in reader: {0}'.format(ex))
