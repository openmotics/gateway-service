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
Tests for MasterCommand module.

@author: fryckbos
"""

from __future__ import absolute_import
import unittest
import xmlrunner

import master.classic.master_api as master_api
from master.classic.master_command import MasterCommandSpec, Field, OutputFieldType, DimmerFieldType, \
                                  ErrorListFieldType


class MasterCommandSpecTest(unittest.TestCase):
    """ Tests for :class`MasterCommandSpec` """

    def setUp(self):
        self.master_version = (3, 143, 103)

    def test_encode_byte_field(self):
        """ Test for Field.byte.encode """
        self.assertEqual(bytearray([0]), Field.byte('test').encode(0))
        self.assertEqual(bytearray([1]), Field.byte('test').encode(1))
        self.assertEqual(bytearray([255]), Field.byte('test').encode(255))

        with self.assertRaises(ValueError):
            Field.byte('test').encode(-1)
        with self.assertRaises(ValueError):
            Field.byte('test').encode(1024)

    def test_decode_byte_field(self):
        """ Test for Field.byte.decode """
        self.assertEqual(0, Field.byte('test').decode(bytearray([0])))
        self.assertEqual(1, Field.byte('test').decode(bytearray([1])))
        self.assertEqual(255, Field.byte('test').decode(bytearray([255])))

        with self.assertRaises(ValueError):
            Field.byte('test').decode('ab')

    def test_encode_int_field(self):
        """ Test for Field.int.encode """
        self.assertEqual(bytearray([0, 0]), Field.integer('test').encode(0))
        self.assertEqual(bytearray([0, 1]), Field.integer('test').encode(1))
        self.assertEqual(bytearray([1, 17]), Field.integer('test').encode(1*256 + 17))
        self.assertEqual(bytearray([255, 255]), Field.integer('test').encode(255*256 + 255))

        with self.assertRaises(ValueError):
            Field.integer('test').encode(-1)
        with self.assertRaises(ValueError):
            Field.integer('test').encode(102400)

    def test_decode_int_field(self):
        """ Test for Field.int.decode """
        self.assertEqual(0, Field.integer('test').decode(bytearray([0, 0])))
        self.assertEqual(1, Field.integer('test').decode(bytearray([0, 1])))
        self.assertEqual(256 + 17, Field.integer('test').decode(bytearray([1, 17])))
        self.assertEqual(255 * 256 + 255, Field.integer('test').decode(bytearray([255, 255])))

        with self.assertRaises(ValueError):
            Field.integer('test').decode(bytearray(b'123'))

    def test_encode_str_field(self):
        """ Test for Field.str.encode """
        self.assertEqual(bytearray(b''), Field.string('test', 0).encode(''))
        self.assertEqual(bytearray(b'hello'), Field.string('test', 5).encode('hello'))
        self.assertEqual(bytearray(b'worlds'), Field.string('test', 6).encode('worlds'))

        with self.assertRaises(ValueError):
            Field.string(bytearray(b'test'), 10).encode('nope')

    def test_decode_str_field(self):
        """ Test for Field.str.decode """
        self.assertEqual('hello', Field.string('test', 5).decode(bytearray(b'hello')))
        self.assertEqual('', Field.string('test', 0).decode(bytearray(b'')))

        with self.assertRaises(ValueError):
            Field.string('test', 2).decode(bytearray(b'nope'))

    def test_encode_padding_field(self):
        """ Test for Field.padding.encode """
        self.assertEqual(bytearray(b''), Field.padding(0).encode(None))
        self.assertEqual(bytearray(b'\x00\x00'), Field.padding(2).encode(None))

    def test_decode_padding_field(self):
        """ Test for Field.padding.decode """
        self.assertEqual('', Field.padding(1).decode(bytearray(b'\x00')))

        with self.assertRaises(ValueError):
            Field.padding(1).decode(bytearray(b'\x00\x00'))

    def test_encode_var_string(self):
        """ Test for VarStringFieldType.encode """
        self.assertEqual(bytearray(b'\x00' + b' ' * 10), Field.varbytes('bankdata', 10).encode(bytearray(b'')))
        self.assertEqual(bytearray(b'\x05hello' + b' ' * 5), Field.varbytes('bankdata', 10).encode(bytearray(b'hello')))
        self.assertEqual(bytearray(b'\x0Ahelloworld'), Field.varbytes('bankdata', 10).encode(bytearray(b'helloworld')))

        with self.assertRaises(ValueError):
            Field.varbytes('bankdata', 2).encode('toolarggge')

    def test_svt(self):
        """ Test for SvtFieldType.encode and SvtFieldType.decode """
        svt_field_type = Field.svt('test')
        self.assertEqual(bytearray([int((1.0 + 32) * 2)]), svt_field_type.encode(master_api.Svt.temp(1.0)))
        self.assertEqual(64.0, svt_field_type.decode(svt_field_type.encode(master_api.Svt.temp(64.0))).get_temperature())

    def test_dimmer(self):
        """ Test for DimmerFieldType.encode and DimmerFieldType.decode """
        dimmer_type = DimmerFieldType()
        for value in range(0, 64):
            val = bytearray([value])
            self.assertEqual(dimmer_type.encode(dimmer_type.decode(val)), val)

    def test_output_wiht_crc(self):
        """ Test crc and is_crc functions. """
        field = Field.crc()

        self.assertEqual('crc', field.name)
        self.assertTrue(Field.is_crc(field))

        field = Field.padding(1)
        self.assertFalse(Field.is_crc(field))

    def test_create_input(self):
        """ Test for MasterCommandSpec.create_input """
        basic_action = MasterCommandSpec('BA',
                                         [Field.byte('actionType'),
                                          Field.byte('actionNumber'),
                                          Field.padding(11)],
                                         [])
        ba_input = basic_action.create_input(1, {"actionType": 2, "actionNumber": 4})

        self.assertEqual(21, len(ba_input))
        self.assertEqual(bytearray(b'STRBA\x01\x02\x04' + (b'\x00' * 11) + b'\r\n'), ba_input)

    def test_create_basic_action(self):
        """ Test for MasterCommandSpec.basic_action """
        self.master_version = (3, 143, 113)
        basic_action = MasterCommandSpec('BA',
                                         [Field.byte('actionType'),
                                          Field.byte('actionNumber'),
                                          Field.byte('parameter'),
                                          Field.padding(10)],
                                         [])
        ba_input = basic_action.create_input(1, {"actionType": 2, "actionNumber": 4, "parameter": 9})

        self.assertEqual(21, len(ba_input))
        self.assertEqual(bytearray(b'STRBA\x01\x02\x04\x09' + (b'\x00' * 10) + b'\r\n'), ba_input)

    def test_old_create_basic_action(self):
        """ Test for MasterCommandSpec.basic_action """
        self.master_version = (3, 143, 103)
        basic_action = MasterCommandSpec('BA',
                                         [Field.byte('actionType'),
                                          Field.byte('actionNumber'),
                                          Field.padding(11)],
                                         [])
        ba_input = basic_action.create_input(1, {"actionType": 2, "actionNumber": 4})

        self.assertEqual(21, len(ba_input))
        self.assertEqual(bytearray(b'STRBA\x01\x02\x04' + (b'\x00' * 11) + b'\r\n'), ba_input)

    def test_input_with_crc(self):
        """ Test encoding with crc. """
        spec = MasterCommandSpec('TE',
                    [Field.byte('one'), Field.byte('two'), Field.crc()], [])
        spec_input = spec.create_input(1, {"one": 255, "two": 128})

        self.assertEqual(13, len(spec_input))
        self.assertEqual(bytearray(b'STRTE\x01\xff\x80C\x01\x7f\r\n'), spec_input)

    def test_consume_output(self):
        """ Test for MasterCommandSpec.consume_output """
        basic_action = MasterCommandSpec('BA',
                                         [],
                                         [Field.string('response', 2),
                                          Field.padding(11),
                                          Field.lit('\r\n')])

        # Simple case, full string without offset at once
        (bytes_consumed, result, done) = basic_action.consume_output(
            bytearray(b'OK' + (b'\x00' * 11) + b'\r\n'), None
        )

        self.assertEqual((15, True), (bytes_consumed, done))
        self.assertEqual('OK', result["response"])

        # Full string with extra padding in the back
        (bytes_consumed, result, done) = basic_action.consume_output(
            bytearray(b'OK' + (b'\x00' * 11) + b'\r\nSome\x04Junk'), None
        )

        self.assertEqual((15, True), (bytes_consumed, done))
        self.assertEqual('OK', result["response"])

        # String in 2 pieces
        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'OK' + (b'\x00' * 5)), None)

        self.assertEqual((7, False), (bytes_consumed, done))
        self.assertEqual(bytearray(b'\x00' * 5), result.pending_bytes)

        (bytes_consumed, result, done) = basic_action.consume_output(bytearray((b'\x00' * 6) + b'\r\n'), result)

        self.assertEqual((8, True), (bytes_consumed, done))
        self.assertEqual('OK', result["response"])

        # String in 2 pieces with extra padding in back
        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'OK' + (b'\x00' * 5)), None)

        self.assertEqual((7, False), (bytes_consumed, done))
        self.assertEqual(bytearray(b'\x00' * 5), result.pending_bytes)

        (bytes_consumed, result, done) = basic_action.consume_output(bytearray((b'\x00' * 6) + b'\r\nWorld'), result)

        self.assertEqual((8, True), (bytes_consumed, done))
        self.assertEqual('OK', result["response"])

        # String in 3 pieces
        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'OK' + (b'\x00' * 5)), None)

        self.assertEqual((7, False), (bytes_consumed, done))
        self.assertEqual(bytearray(b'\x00' * 5), result.pending_bytes)

        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'\x00' * 3), result)

        self.assertEqual((3, False), (bytes_consumed, done))
        self.assertEqual(bytearray(b'\x00' * 8), result.pending_bytes)

        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'\x00' * 3), result)

        self.assertEqual((3, False), (bytes_consumed, done))
        self.assertEqual(bytearray(b''), result.pending_bytes)

        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'\r\n'), result)

        self.assertEqual((2, True), (bytes_consumed, done))
        self.assertEqual('OK', result["response"])

    def test_consume_output_varlength(self):
        """ Test for MasterCommandSpec.consume_output with a variable length output field. """
        def dim(byte_value):
            """ Convert a dimmer byte value to the api value. """
            return int(byte_value * 10.0 / 6.0)

        basic_action = MasterCommandSpec('OL',
                                         [],
                                         [Field('outputs', OutputFieldType()),
                                          Field.lit('\r\n\r\n')])

        # Empty outputs
        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'\x00\r\n\r\n'), None)

        self.assertEqual((5, True), (bytes_consumed, done))
        self.assertEqual([], result["outputs"])

        # One output
        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'\x01\x05\x10\r\n\r\n'), None)

        self.assertEqual((7, True), (bytes_consumed, done))
        self.assertEqual([(5, dim(16))], result["outputs"])

        # Split up in multiple parts
        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'\x03'), None)

        self.assertEqual((1, False), (bytes_consumed, done))

        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'\x05\x10'), result)

        self.assertEqual((2, False), (bytes_consumed, done))

        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'\x01\x02\x03\x04\r\n'), result)

        self.assertEqual((6, False), (bytes_consumed, done))

        (bytes_consumed, result, done) = basic_action.consume_output(bytearray(b'\r\n'), result)

        self.assertEqual((2, True), (bytes_consumed, done))

        self.assertEqual([(5, dim(16)), (1, dim(2)), (3, dim(4))], result["outputs"])

    def test_error_list_field_type(self):
        """ Tests for the ErrorListFieldType. """
        field_type = ErrorListFieldType()
        # Test with one output module
        field_value = bytearray(b'\x01O\x14\x00\x01')

        decoded = field_type.decode(field_value)
        self.assertEqual([('O20', 1)], decoded)

        self.assertEqual(field_value, field_type.encode(decoded))

        # Test with multiple modules
        field_value = bytearray(b'\x03O\x14\x00\x01I\x20\x01\x01O\x08\x00\x00')

        decoded = field_type.decode(field_value)
        self.assertEqual([('O20', 1), ('I32', 257), ('O8', 0)], decoded)

        self.assertEqual(field_value, field_type.encode(decoded))

    def test_output_has_crc(self):
        """ Test for MasterCommandSpec.output_has_crc. """
        self.assertFalse(master_api.basic_action(self.master_version).output_has_crc())
        self.assertTrue(master_api.read_output().output_has_crc())


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
