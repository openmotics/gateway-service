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
        Logs.setup_logger(log_level_override=logging.DEBUG)

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
        memory[5][12] = 4
        data = mocked_core.memory_file.read([address])[address]
        self.assertEqual(bytearray([1, 2, 3]), data)
        data = mocked_core.memory_file.read([address], read_through=True)[address]
        self.assertEqual(bytearray([1, 2, 4]), data)
        mocked_core.memory_file.write({address: bytearray([6, 7, 8])})
        self.assertEqual(bytearray([1, 2, 4]), memory[5][10:13])
        mocked_core.memory_file.activate()  # Only save on activate
        self.assertEqual(bytearray([6, 7, 8]), memory[5][10:13])

    def test_locking(self):
        mocked_core = MockedCore()
        memory = mocked_core.memory[MemoryTypes.EEPROM]
        memory_file = mocked_core.memory_file

        memory[5] = bytearray([255] * 256)
        memory[5][129] = 0
        address_0 = MemoryAddress(memory_type=MemoryTypes.EEPROM, page=5, offset=126, length=4)
        address_1 = MemoryAddress(memory_type=MemoryTypes.EEPROM, page=5, offset=129, length=4)  # Overlap on byte 2

        self.assertEqual({address_0: bytearray([255, 255, 255, 0]),
                          address_1: bytearray([0, 255, 255, 255])},
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
            memory_file.write({address_0: bytearray([10, 11, 12, 13])})
        with mock.patch.object(threading, 'current_thread', thread_1):
            memory_file.write({address_1: bytearray([20, 21, 22, 23])})

        # Activate should only activate the current thread's write cache - nothing in this case
        memory_file.activate()
        self.assertEqual({address_0: bytearray([255, 255, 255, 0]),
                          address_1: bytearray([0, 255, 255, 255])},
                         memory_file.read([address_0, address_1]))

        # Activate from within thread 0
        mocked_core.write_log = []
        with mock.patch.object(threading, 'current_thread', thread_0):
            memory_file.activate()
        self.assertEqual({address_0: bytearray([10, 11, 12, 13]),
                          address_1: bytearray([13, 255, 255, 255])},
                         memory_file.read([address_0, address_1]))

        # Validate write log, since thread_0 wrote over the 127/128 byte boundary
        self.assertEqual([{'type': MemoryTypes.EEPROM, 'page': 5, 'start': 126, 'data': bytearray([10, 11])},
                          {'type': MemoryTypes.EEPROM, 'page': 5, 'start': 128, 'data': bytearray([12, 13])}],
                         mocked_core.write_log)

        # Activate from within thread 1
        mocked_core.write_log = []
        with mock.patch.object(threading, 'current_thread', thread_1):
            memory_file.activate()
        self.assertEqual({address_0: bytearray([10, 11, 12, 20]),
                          address_1: bytearray([20, 21, 22, 23])},
                         memory_file.read([address_0, address_1]))

        # Validate write log, since thread_1 did not write over the 127/128 boundary
        self.assertEqual([{'type': MemoryTypes.EEPROM, 'page': 5, 'start': 129, 'data': bytearray([20, 21, 22, 23])}],
                         mocked_core.write_log)

    def test_multichunk_write(self):
        mocked_core = MockedCore()
        memory = mocked_core.memory[MemoryTypes.EEPROM]
        memory_file = mocked_core.memory_file

        memory[5] = bytearray([255] * 256)
        address = MemoryAddress(memory_type=MemoryTypes.EEPROM, page=5, offset=16, length=64)

        self.assertEqual({address: bytearray([255] * 64)},
                         memory_file.read([address]))

        # Prepare thread mock
        thread = mock.Mock(Thread())
        with mock.patch.object(threading, 'current_thread', thread):
            self.assertIsNotNone(threading.current_thread().ident)

        # Execute write
        with mock.patch.object(threading, 'current_thread', thread):
            memory_file.write({address: bytearray([10 + i for i in range(64)])})

        # Activate from within thread
        mocked_core.write_log = []
        with mock.patch.object(threading, 'current_thread', thread):
            memory_file.activate()

        self.assertEqual({address: bytearray([10 + i for i in range(64)])},
                         memory_file.read([address]))

        # Validate write log, since thread_0 wrote over the 127/128 byte boundary
        self.assertEqual([{'type': MemoryTypes.EEPROM, 'page': 5, 'start': 16, 'data': bytearray([10 + i for i in range(32)])},
                          {'type': MemoryTypes.EEPROM, 'page': 5, 'start': 48, 'data': bytearray([10 + 32 + i for i in range(32)])}],
                         mocked_core.write_log)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
