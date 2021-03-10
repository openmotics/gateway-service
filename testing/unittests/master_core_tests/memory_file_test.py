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
Tests for the memory_file module
"""

from __future__ import absolute_import
import unittest
import xmlrunner
import logging
import mock
import threading
from threading import Thread
from ioc import SetTestMode
from master.core.memory_file import MemoryTypes
from master.core.memory_types import MemoryAddress
from logs import Logs
from mocked_core_helper import MockedCore


class MemoryFileTest(unittest.TestCase):
    """ Tests for MemoryFile """

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        Logs.setup_logger(log_level=logging.DEBUG)

    def test_data_consistency(self):
        mocked_core = MockedCore()
        memory = mocked_core.memory[MemoryTypes.EEPROM]

        memory[5] = bytearray([255] * 256)
        memory[5][10] = 1
        memory[5][11] = 2
        memory[5][12] = 3
        address = MemoryAddress(memory_type=MemoryTypes.EEPROM, page=5, offset=10, length=3)

        data = mocked_core.memory_file.read([address])[address]
        self.assertEqual(bytearray([1, 2, 3]), data)
        mocked_core.memory_file.write({address: bytearray([6, 7, 8])})
        self.assertEqual(bytearray([1, 2, 3]), memory[5][10:13])
        mocked_core.memory_file.activate()  # Only save on activate
        self.assertEqual(bytearray([6, 7, 8]), memory[5][10:13])

    def test_locking(self):
        mocked_core = MockedCore()
        memory = mocked_core.memory[MemoryTypes.EEPROM]
        memory_file = mocked_core.memory_file

        memory[5] = bytearray([255] * 256)
        memory[5][2] = 0
        address_0 = MemoryAddress(memory_type=MemoryTypes.EEPROM, page=5, offset=0, length=3)
        address_1 = MemoryAddress(memory_type=MemoryTypes.EEPROM, page=5, offset=2, length=3)  # Overlap on byte 2

        self.assertEqual({address_0: bytearray([255, 255, 0]),
                          address_1: bytearray([0, 255, 255])},
                         memory_file.read([address_0, address_1]))

        # Prepare thread mocks
        thread_0 = mock.Mock(Thread())
        with mock.patch.object(threading, 'current_thread', thread_0):
            self.assertIsNotNone(threading.current_thread().ident)
        thread_1 = mock.Mock(Thread())
        with mock.patch.object(threading, 'current_thread', thread_1):
            self.assertIsNotNone(threading.current_thread().ident)

        # Execute two simultaneous writes
        with mock.patch.object(threading, 'current_thread', thread_0):
            memory_file.write({address_0: bytearray([10, 11, 12])})
        with mock.patch.object(threading, 'current_thread', thread_1):
            memory_file.write({address_1: bytearray([20, 21, 22])})

        # Activate should only activate the current thread's write cache - nothing in this case
        memory_file.activate()
        self.assertEqual({address_0: bytearray([255, 255, 0]),
                          address_1: bytearray([0, 255, 255])},
                         memory_file.read([address_0, address_1]))

        # Activate from within thread 0
        with mock.patch.object(threading, 'current_thread', thread_0):
            memory_file.activate()
        self.assertEqual({address_0: bytearray([10, 11, 12]),
                          address_1: bytearray([12, 255, 255])},
                         memory_file.read([address_0, address_1]))

        # Activate from within thread 1
        with mock.patch.object(threading, 'current_thread', thread_1):
            memory_file.activate()
        self.assertEqual({address_0: bytearray([10, 11, 20]),
                          address_1: bytearray([20, 21, 22])},
                         memory_file.read([address_0, address_1]))


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
