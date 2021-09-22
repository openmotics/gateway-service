# Copyright (C) 2020 OpenMotics BV
#
# This program is free software, you can redistribute it and/or modify
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
Tests for the fields module
"""

from __future__ import absolute_import
import unittest
import xmlrunner
import logging
from master.core.fields import *
from master.core.serial_number import SerialNumber
from logs import Logs


class APIFieldsTest(unittest.TestCase):
    """ Tests for fields """

    @classmethod
    def setUpClass(cls):
        Logs.setup_logger(log_level_override=logging.DEBUG)

    # Every test validates a given field instance against a list of scenarios.
    # A scenario is a list of 2 or 3 values:
    # * The first value will be a value that will be encoded
    # * This encoded value will be compared against the second value;
    #   * This is either an exception that will be raised while encoding
    #   * Or a bytearray, the encoded value
    # * This encoded value will be decoded again and will be compared
    #   * To the third value
    #   * To the first value, if only 2 values are provided

    def test_byte_field(self):
        self._test_field(ByteField('x'), [[-1, ValueError],
                                          [0, bytearray([0])],
                                          [5, bytearray([5])],
                                          [254, bytearray([254])],
                                          [255, bytearray([255])],
                                          [256, ValueError]])

    def test_char_field(self):
        self._test_field(CharField('x'), [[-1, ValueError],
                                          ['\x00', bytearray([0])],
                                          ['A', bytearray([65])],
                                          ['\xFF', bytearray([255])],
                                          ['\x00\x00', ValueError]])

    def test_temperature_field(self):
        self._test_field(TemperatureField('x'), [[-32.5, ValueError],
                                                 [-32, bytearray([0])],
                                                 [0, bytearray([64])],
                                                 [0.1, bytearray([64]), 0],
                                                 [0.5, bytearray([65])],
                                                 [95, bytearray([254])],
                                                 [95.5, ValueError],
                                                 [None, bytearray([255])]])

    def test_humidity_field(self):
        self._test_field(HumidityField('x'), [[-1, ValueError],
                                              [0, bytearray([0])],
                                              [0.1, bytearray([0]), 0],
                                              [0.5, bytearray([1])],
                                              [100, bytearray([200])],
                                              [101, ValueError],
                                              [None, bytearray([255])]])

    def test_word_field(self):
        self._test_field(WordField('x'), [[-1, ValueError],
                                          [0, bytearray([0, 0])],
                                          [255, bytearray([0, 255])],
                                          [256, bytearray([1, 0])],
                                          [65535, bytearray([255, 255])],
                                          [65536, ValueError]])

    def test_uint32_field(self):
        self._test_field(UInt32Field('x'), [[-1, ValueError],
                                            [0, bytearray([0, 0, 0, 0])],
                                            [256, bytearray([0, 0, 1, 0])],
                                            [4294967295, bytearray([255, 255, 255, 255])],
                                            [4294967296, ValueError]])

    def test_bytearray_field(self):
        self._test_field(ByteArrayField('x', 3), [[[-1, 0, 0], ValueError],
                                                  [[0, 0, 0], bytearray([0, 0, 0])],
                                                  [[255, 255, 1], bytearray([255, 255, 1])],
                                                  [[255, 255, 256], ValueError],
                                                  [[0, 0], ValueError]])

    def test_temperaturearray_field(self):
        self._test_field(TemperatureArrayField('x', 3), [[[-32.5, 0, 0], ValueError],
                                                         [[0, 0, 0.5], bytearray([64, 64, 65])],
                                                         [[95, None, 1], bytearray([254, 255, 66])],
                                                         [[0, 0], ValueError]])

    def test_humidityarray_field(self):
        self._test_field(HumidityArrayField('x', 3), [[[-1, 0, 0], ValueError],
                                                      [[0, 0, 0.5], bytearray([0, 0, 1])],
                                                      [[99, None, 1], bytearray([198, 255, 2])],
                                                      [[0, 0], ValueError]])

    def test_wordarray_field(self):
        self._test_field(WordArrayField('x', 3), [[[-1, 0, 0], ValueError],
                                                  [[0, 0, 256], bytearray([0, 0, 0, 0, 1, 0])],
                                                  [[65536, 0, 0], ValueError],
                                                  [[0, 0], ValueError]])

    def test_serial_number_field(self):
        self._test_field(SerialNumberField('x'), [['foo', ValueError],
                                                  [SerialNumber(2021, 9, 1, 0, 65536), bytearray([21, 9, 1, 0, 1, 0, 0])]])

    def test_address_field(self):
        self._test_field(AddressField('x'), [['-1.0.0.0', ValueError],
                                             ['0.0.0.0', bytearray([0, 0, 0, 0]), '000.000.000.000'],
                                             ['0.05.255.50', bytearray([0, 5, 255, 50]), '000.005.255.050'],
                                             ['0.256.0.0', ValueError, '000.256.000.000'],
                                             ['0.0.0', ValueError],
                                             ['0,0,0,0', ValueError],
                                             ['0.0', ValueError],
                                             ['foobar', ValueError]])
        self._test_field(AddressField('x', 2), [['-1.0', ValueError],
                                                ['0.0', bytearray([0, 0]), '000.000'],
                                                ['255.50', bytearray([255, 50]), '255.050'],
                                                ['0.256', ValueError, '000.256'],
                                                ['0', ValueError],
                                                ['0,0', ValueError],
                                                ['foobar', ValueError]])

    def test_string_field(self):
        self._test_field(StringField('x'), [['abc', bytearray([97, 98, 99, 0])],
                                            ['', bytearray([0])],
                                            ['abc\x00d', bytearray([97, 98, 99, 0, 100, 0])]])

    def test_padding_field(self):
        field = PaddingField(3)
        self.assertEqual(bytearray([0, 0, 0]), field.encode(0))
        self.assertEqual(bytearray([0, 0, 0]), field.encode(5))
        self.assertEqual('...', field.decode(bytearray([0])))
        self.assertEqual('...', field.decode(bytearray([0, 0, 0])))
        self.assertEqual('...', field.decode(bytearray([0, 0, 0, 0, 0])))

    def test_literalbytes_field(self):
        field = LiteralBytesField(0)
        with self.assertRaises(ValueError):
            field.encode(255)
        self.assertEqual(bytearray([0]), field.encode(None))
        with self.assertRaises(ValueError):
            _ = LiteralBytesField(256)
        field = LiteralBytesField(10, 10)
        self.assertEqual(bytearray([10, 10]), field.encode(None))
        with self.assertRaises(ValueError):
            field.decode(bytearray([0]))
        with self.assertRaises(ValueError):
            field.decode(None)

    def _test_field(self, field, scenario):
        for item in scenario:
            if len(item) == 2:
                value, expected_bytes = item
                expected_value = value
            else:
                value, expected_bytes, expected_value = item
            if expected_bytes == ValueError:
                with self.assertRaises(expected_bytes):
                    field.encode(value)
                continue
            result_bytes = field.encode(value)
            self.assertEqual(expected_bytes, result_bytes)
            result_value = field.decode(result_bytes)
            self.assertEqual(expected_value, result_value)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
