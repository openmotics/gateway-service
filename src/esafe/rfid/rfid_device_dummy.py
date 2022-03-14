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
"""
Dummy rebus implementation
"""
import errno
import logging
import os
from threading import Thread

from esafe.rfid import RfidDevice

if False:  # MyPy
    from typing import Optional, TextIO

logger = logging.getLogger(__name__)


class RfidDeviceDummy(RfidDevice):

    PIPE_END_MSG = 'PIPE_END_MSG'
    PIPE_NAME = 'RFID'

    def __init__(self, callback=None):
        super().__init__(callback)
        self.reader_thread = Thread(target=self.reader_runner, name='reader-thread', daemon=False)
        self.running = False

    def start(self):
        # create the fifo pipe
        try:
            os.mkfifo(RfidDeviceDummy.PIPE_NAME)
        except OSError as oe:
            if oe.errno != errno.EEXIST:
                raise
        self.running = True
        self.reader_thread.start()

    def stop(self):
        self.running = False
        self.write_to_pipe(RfidDeviceDummy.PIPE_END_MSG)

    def reader_runner(self):
        while self.running:
            result = self.read_from_pipe()
            if result == RfidDeviceDummy.PIPE_END_MSG:
                continue
            self.callback(result)

    def read_from_pipe(self):
        _ = self
        with open(RfidDeviceDummy.PIPE_NAME) as fifo:
            data = fifo.readline()[:-1]  # chop of the new line
            print('Read: "{0}"'.format(data))
            return data

    def write_to_pipe(self, msg):
        _ = self
        with open(RfidDeviceDummy.PIPE_NAME) as fifo:
            result = fifo.write(msg)
            print('wrote # {} bytes'.format(result))

    # Able to set a callback and call this function when a new
    # rfid badge is scanned in
    def set_new_scan_callback(self, callback):
        self.callback = callback
