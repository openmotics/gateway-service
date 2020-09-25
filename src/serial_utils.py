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
Serial tools contains the RS485 wrapper, printable and CommunicationTimedOutException.
"""

from __future__ import absolute_import

import fcntl
import struct
from threading import Thread

from six.moves.queue import Queue
from gateway.hal.master_controller import CommunicationFailure

if False:  # MYPY
    from serial import Serial


class CommunicationTimedOutException(CommunicationFailure):
    """ An exception that is raised when the master did not respond in time. """
    def __init__(self, message=''):
        if not message:
            message = self.__class__.__name__
        super(CommunicationTimedOutException, self).__init__(message)


def printable(data):
    """ prints data in a human-redable way """

    if isinstance(data, list) or isinstance(data, bytearray):
        byte_notation = ' '.join(['{0: >3}'.format(i) for i in data])
        string_notation = ''.join([str(chr(i)) if 32 < i <= 126 else '.' for i in data])
    else:
        byte_notation = ' '.join(['{0: >3}'.format(ord(c)) for c in data])
        string_notation = ''.join([c if 32 < ord(c) <= 126 else '.' for c in data])
    return '{0}    {1}'.format(byte_notation, string_notation)


# FIXME this shouldn't use strings
class RS485(object):
    """ Replicates the pyserial interface. """

    def __init__(self, serial):
        # type: (Serial) -> None
        """ Initialize a rs485 connection using the serial port. """
        self._serial = serial
        fileno = serial.fileno()
        if fileno is not None:
            serial_rs485 = struct.pack('hhhhhhhh', 3, 0, 0, 0, 0, 0, 0, 0)
            fcntl.ioctl(fileno, 0x542F, serial_rs485)

        self._serial.timeout = None
        self._thread = Thread(target=self._reader, name='RS485 reader')
        self._thread.daemon = True
        self.read_queue = Queue()  # type: Queue[str]

    def start(self):
        # type: () -> None
        self._thread.start()

    def write(self, data):
        # type: (str) -> None
        """ Write data to serial port """
        self._serial.write(bytearray(ord(c) for c in data))

    def _reader(self):
        # type: () -> None
        try:
            while True:
                data = self._serial.read(1)
                if len(data) == 1:
                    self.read_queue.put(chr(data[0]))
                size = self._serial.inWaiting()
                if size > 0:
                    for byte in self._serial.read(size):
                        self.read_queue.put(chr(byte))
        except Exception as ex:
            print('Error in reader: {0}'.format(ex))
