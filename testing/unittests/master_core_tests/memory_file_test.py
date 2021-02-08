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
from ioc import SetTestMode
from master.core.memory_file import MemoryTypes
from master.core.memory_types import MemoryAddress
from logs import Logs
from virtual_core_helper import VirtualCore


class MemoryFileTest(unittest.TestCase):
    """ Tests for MemoryFile """

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        Logs.setup_logger(log_level=logging.DEBUG)

    def test_data_consistency(self):
        virtual_core = VirtualCore()
        memory = virtual_core.memory[MemoryTypes.EEPROM]

        memory[5] = bytearray([255] * 256)
        memory[5][10] = 1
        memory[5][11] = 2
        memory[5][12] = 3
        address = MemoryAddress(memory_type=MemoryTypes.EEPROM, page=5, offset=10, length=3)

        data = virtual_core.memory_file.read([address])[address]
        self.assertEqual(bytearray([1, 2, 3]), data)
        virtual_core.memory_file.write({address: bytearray([6, 7, 8])})
        self.assertEqual(bytearray([1, 2, 3]), memory[5][10:13])
        virtual_core.memory_file.activate()  # Only save on activate
        self.assertEqual(bytearray([6, 7, 8]), memory[5][10:13])


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
