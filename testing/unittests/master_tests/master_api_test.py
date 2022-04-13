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
Tests for master_api module.

@author: fryckbos
"""

from __future__ import absolute_import
import unittest
from master.classic.master_api import Svt


class SvtTest(unittest.TestCase):
    """ Tests for :class`Svt`. """

    def test_temperature(self):
        """ Test the temperature type. """
        for temperature in [-32, 0, 18.5, 95]:
            self.assertEqual(temperature, Svt.temp(temperature).get_temperature())

        self.assertEqual(bytearray([104]), Svt.temp(20).get_byte())

    def test_time(self):
        """ Test the time type. """
        for hour in range(0, 24):
            for minute in range(0, 60, 10):
                time = "%02d:%02d" % (hour, minute)
                self.assertEqual(time, Svt.time(time).get_time())

        self.assertEqual("16:30", Svt.time("16:33").get_time())

        self.assertEqual(bytearray([99]), Svt.time("16:30").get_byte())

    def test_raw(self):
        """ Test the raw type. """
        for value in range(0, 255):
            byte_value = bytearray([value])
            self.assertEqual(byte_value, Svt.from_byte(byte_value).get_byte())
