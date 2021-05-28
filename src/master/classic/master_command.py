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
MasterApi enables communication with master over serial port.
Provides a function for each API call.
"""

from __future__ import absolute_import
import math

from serial_utils import Printable

if False:  # MYPY
    from typing import Optional, Tuple, Dict, Any, List
    from master.classic.master_api import Svt


class MasterCommandSpec(object):
    """
    The input command to the master looks like this:
    'STR' [Action (2 bytes)] [cid] [fields] '\r\n'
    The first 6 and last 2 bytes are fixed, the rest should be in fields.

    The output looks like this:
    [Action (2 bytes)] [cid] [fields]
    The total length depends on the action.
    """
    def __init__(self, action, input_fields, output_fields, output_action=None):
        # type: (str, List[Field], List[Field], Optional[str]) -> None
        """ Create a MasterCommandSpec.

        :param action: name of the action as described in the Master api.
        :param input_fields: Fields in the input to the master
        :param output_fields: Fields in the output from the master
        :param output_action: name of the action of the answer, as described in the Master api. None if identical to the mainaction
        """
        self.action = bytearray([ord(c) for c in action])
        self.input_fields = input_fields
        self.output_fields = output_fields
        self.output_action = bytearray([ord(c) for c in action]
                                       if output_action is None
                                       else [ord(c) for c in output_action])

    def create_input(self, cid, fields=None, extended_crc=False):
        # type: (int, Optional[Dict[str, Any]], bool) -> bytearray
        """
        Create an input command for the master using this spec and the provided fields.

        :param cid: communication id
        :param fields: dictionary with values for the fields
        :param extended_crc: Indicates whether the action should be included in the CRC
        """
        if fields is None:
            fields = dict()

        start = bytearray(b'STR') + self.action + bytearray([cid])
        encoded_fields = bytearray()
        for field in self.input_fields:
            if Field.is_crc(field):
                if extended_crc:
                    crc = MasterCommandSpec.__calc_crc(self.action + encoded_fields)
                else:
                    crc = MasterCommandSpec.__calc_crc(encoded_fields)
                encoded_fields += crc
            else:
                encoded_fields += field.encode(fields.get(field.name))

        return start + encoded_fields + bytearray(b'\r\n')

    @staticmethod
    def __calc_crc(encoded_string):
        # type: (bytearray) -> bytearray
        """ Calculate the crc of an string. """
        crc = 0
        for byte in encoded_string:
            crc += byte

        return bytearray(b'C') + bytearray([crc // 256, crc % 256])

    def create_output(self, cid, fields):
        # type: (int, Dict[str, Any]) -> bytearray
        """
        Create an output command from the master using this spec and the provided fields.
        Only used for testing !

        :param cid: communication id
        :param fields: dictionary with values for the fields
        """
        ret = self.output_action + bytearray([cid])
        for field in self.output_fields:
            ret += field.encode(fields.get(field.name))
        return ret

    def consume_output(self, byte_str, partial_result=None):
        # type: (bytearray, Optional[Result]) -> Tuple[int, Result, bool]
        """
        When the prefix of a command is matched, consume_output is used to fill in the
        output fields. If a part of the fields was already matched, the parial_result should
        be provided. The output of this method indicates how many bytes were consumed, the
        result and if the consumption was done.

        :param byte_str Output from the master
        :param partial_result: In case we already have data for this unfinished communication.
        """
        if partial_result is None:
            from_pending = 0
            partial_result = Result()
        else:
            from_pending = len(partial_result.pending_bytes)
            byte_str = partial_result.pending_bytes + byte_str
            partial_result.pending_bytes = bytearray()

        def decode_field(index_, byte_str_, field_, num_bytes):
            """
            Decode one field, returns index for the next field if successful,
            returns a tuple with decode information if not successful.
            """
            if index_ + num_bytes <= len(byte_str_):
                try:
                    decoded = field_.decode(byte_str[index_:index_ + num_bytes])
                except NeedMoreBytesException as nmbe:
                    return decode_field(index_, byte_str_, field_, nmbe.bytes_required)
                else:
                    partial_result[field_.name] = decoded
                    partial_result.field_index += 1
                    partial_result.pending_bytes = bytearray()
                    index_ += num_bytes
                    return index_
            else:
                partial_result.pending_bytes += byte_str[index:]
                return len(byte_str) - from_pending, partial_result, False

        # Found beginning, start decoding
        index = 0
        for field in self.output_fields[partial_result.field_index:]:
            index = decode_field(index, byte_str, field, field.get_min_decode_bytes())
            if not isinstance(index, int):
                # We ran out of bytes
                return index

        partial_result.complete = True
        partial_result.actual_bytes = byte_str[:index]
        return index - from_pending, partial_result, True

    def output_has_crc(self):
        """ Check if the MasterCommandSpec output contains a crc field. """
        for field in self.output_fields:
            if Field.is_crc(field):
                return True

        return False

    def __repr__(self):
        # type: () ->  str
        return '<MasterCommandSpec {} {}>'.format(self.action, self.output_action)

    def __eq__(self, other):
        """ Only used for testing, equals by name. """
        return self.action == other.action and self.output_action == other.output_action


class Result(object):
    """
    Result of a communication with the master. Can be accessed as a dict,
    contains the output fields specified in the spec.
    """

    def __init__(self):
        """ Create a new incomplete result. """
        self.complete = False
        self.field_index = 0
        self.fields = {}
        self.pending_bytes = bytearray()
        self.actual_bytes = bytearray()

    def __getitem__(self, key):
        """ Implemented so class can be accessed as a dict. """
        return self.fields[key]

    def __setitem__(self, key, value):
        """ Implemented so class can be accessed as a dict. """
        self.fields[key] = value

    def get(self, k, default=None):
        return self.fields.get(k, default)

    def __str__(self):
        return str(self.fields)

    def __iter__(self):
        return self.fields.__iter__()


class Field(object):
    """ Field of a master command has a name, type.
    """
    @staticmethod
    def byte(name):
        """ Create 1-byte field with a certain name.
        The byte type takes an int as input. """
        return Field(name, IntegerType(1))

    @staticmethod
    def integer(name):
        """ Create 2-byte field with a certain name.
        The byte type takes an int as input. """
        return Field(name, IntegerType(2))

    @staticmethod
    def string(name, length):
        """ Create a string field with a certain name and length. """
        return Field(name, StringType(length))

    @staticmethod
    def bytes(name, length):
        """ Create a byte array with a certain name and length. """
        return Field(name, BytesFieldType(length))

    @staticmethod
    def padding(length):
        """ Padding, will be skipped. """
        return Field("padding", PaddingFieldType(length))

    @staticmethod
    def lit(value):
        """ Literal value """
        return Field("literal", LiteralFieldType(value))

    @staticmethod
    def varbytes(name, max_data_length):
        """ String of variable length with fixed total length """
        return Field(name, VarBytesFieldType(max_data_length))

    @staticmethod
    def svt(name):
        """ System value type """
        return Field(name, SvtFieldType())

    @staticmethod
    def dimmer(name):
        """ Dimmer type (byte in [0, 63] converted to integer in [0, 100]. """
        return Field(name, DimmerFieldType())

    @staticmethod
    def crc():
        """ Create a crc field type (3-byte string) """
        return Field.bytes('crc', 3)

    @staticmethod
    def is_crc(field):
        """ Is the field a crc field ? """
        return isinstance(field, Field) and field.name == 'crc' and isinstance(field.field_type, BytesFieldType) and field.field_type.length == 3

    def __init__(self, name, field_type):
        # type: (str, FieldType) -> None
        """
        Create a MasterComandField.

        :param name: name of the field as described in the Master api.
        :param field_type: type of the field.
        """
        self.name = name
        self.field_type = field_type

    def encode(self, field_value):
        # type: (Any) -> bytearray
        """
        Generate an encoded field.

        :param field_value: the value of the field.
        :type field_value: type of value depends on type of field.
        """
        return self.field_type.encode(field_value)

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.field_type.get_min_decode_bytes()

    def decode(self, byte_str):
        # type: (bytearray) -> Any
        """
        Decode a string of bytes. If there are not enough bytes, a `MoreBytesRequiredException` will be thrown.

        :param byte_str: data
        """
        return self.field_type.decode(byte_str)


class NeedMoreBytesException(Exception):
    """ Throw in case a decode requires more bytes then provided. """
    def __init__(self, bytes_required):
        Exception.__init__(self)
        self.bytes_required = bytes_required


class FieldType(object):
    def encode(self, field_value):
        # type: (Any) -> bytearray
        raise NotImplementedError()

    def decode(self, byte_str):
        # type: (bytearray) -> Any
        raise NotImplementedError()


class IntegerType(FieldType):
    """ Integer type """
    def __init__(self, length):
        # type: (int) -> None
        if length not in [1, 2]:
            raise ValueError('Unexpected length (should be 1 or 2)')
        self.length = length

    def encode(self, field_value):
        # type: (int) -> bytearray
        """
        Get the encoded value
        :param field_value: value of the field to encode
        """
        if self.length == 1:
            if field_value < 0 or field_value > 255:
                raise ValueError('Int does not fit in byte: %d' % field_value)
            return bytearray([field_value])
        elif self.length == 2:
            if field_value < 0 or field_value > 65535:
                raise ValueError('Int does not fit in 2 bytes: %d' % field_value)
            return bytearray([field_value // 256, field_value % 256])
        raise ValueError('Unexpected length')

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.length

    def decode(self, byte_str):
        # type: (bytearray) -> int
        """ Decode the bytes. """
        if len(byte_str) != self.length:
            raise ValueError('Byte array is not of the correct length: expected %d, got %d' % (self.length, len(byte_str)))
        elif self.length == 1:
            return byte_str[0]
        elif self.length == 2:
            return byte_str[0] * 256 + byte_str[1]
        raise ValueError('Unexpected length')


class StringType(FieldType):
    """ Describes a string type """
    def __init__(self, length):
        # type: (int) -> None
        """
        Create a string type

        :param length: length of the encoded field
        """
        self.length = length

    def encode(self, field_value):
        # type: (str) -> bytearray
        """ Get the encoded value """
        if len(field_value) != self.length:
            raise ValueError('String is not of the correct length: expected %d, got %d' % (self.length, len(field_value)))
        return bytearray(ord(c) for c in field_value)

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.length

    def decode(self, byte_str):
        # type: (bytearray) -> str
        """ Decode the bytes. """
        if len(byte_str) != self.length:
            raise ValueError('Byte array is not of the correct length: expected %d, got %d' % (self.length, len(byte_str)))
        return ''.join(chr(b) if b < 128 else ' ' for b in byte_str)


class PaddingFieldType(FieldType):
    """ Empty field. """
    def __init__(self, length):
        self.length = length

    def encode(self, _):
        # type: (Any) -> bytearray
        """ Encode returns string of \x00 """
        return bytearray([0] * self.length)

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.length

    def decode(self, byte_str):
        # type: (bytearray) -> Any
        """ Only checks if byte_str size is correct, returns None """
        if len(byte_str) != self.length:
            raise ValueError('Byte array is not of the correct length: expected %d, got %d' % (self.length, len(byte_str)))
        else:
            return ''


class BytesFieldType(FieldType):
    """ Type for an array of bytes. """
    def __init__(self, length):
        self.length = length

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.length

    @classmethod
    def encode(cls, byte_arr):
        # type: (bytearray) -> bytearray
        return byte_arr

    @classmethod
    def decode(cls, byte_str):
        # type: (bytearray) -> bytearray
        return byte_str


class LiteralFieldType(FieldType):
    """ Literal string field. """
    def __init__(self, literal):
        # type: (str) -> None
        self.literal = bytearray(literal.encode())

    def encode(self, _):
        # type: (Any) -> bytearray
        """ Returns the literal """
        return self.literal

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return len(self.literal)

    def decode(self, byte_str):
        # type: (bytearray) -> str
        """ Checks if byte_str is the literal """
        if byte_str != self.literal:
            raise ValueError('Byte array does not match literal: expected %s, got %s' % (Printable(self.literal), Printable(byte_str)))
        else:
            return ''


class SvtFieldType(FieldType):
    """
    The System Value Type is one byte. This types encodes and decodes into
    a float (degrees Celsius).
    """
    def __init__(self):
        pass

    @classmethod
    def encode(cls, field_value):
        # type: (Svt) -> bytearray
        """ Encode an instance of the Svt class to a byte. """
        return field_value.get_byte()

    @classmethod
    def get_min_decode_bytes(cls):
        """ Get the minimal amount of bytes required to start decoding. """
        return 1

    @classmethod
    def decode(cls, byte_str):
        # type: (bytearray) -> Svt
        """ Decode a svt byte string into a instance of the Svt class. """
        from . import master_api
        return master_api.Svt.from_byte(byte_str)


class VarBytesFieldType(FieldType):
    """
    The VarBytes uses 1 byte for the length, the total length of the bytes is fixed.
    Unused bytes are padded with space-equivalent.
    """
    def __init__(self, total_data_length):
        # type: (int) -> None
        self.total_data_length = total_data_length

    def encode(self, field_value):
        # type: (bytearray) -> bytearray
        """ Encode a list of bytes. """
        if len(field_value) > self.total_data_length:
            raise ValueError("Cannot handle more than %d bytes, got %d",
                             self.total_data_length, len(field_value))
        else:
            length = len(field_value)
            out = bytearray([length]) + field_value
            if length < self.total_data_length:
                out += bytearray(b' ' * (self.total_data_length - length))
            return out

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.total_data_length + 1

    @classmethod
    def decode(cls, byte_str):
        # type: (bytearray) -> bytearray
        """ Decode the data into a list of bytes (without padding) """
        length = byte_str[0]
        return byte_str[1:1 + length]


class DimmerFieldType(FieldType):
    """
    The dimmer value is a byte in [0, 63], this is converted to an integer in [0, 100] to
    provide a consistent interface with the set dimmer method. The transfer function is not
    completely linear: [0, 54] maps to [0, 90] and [54, 63] maps to [92, 100].
    """
    def __init__(self):
        pass

    @classmethod
    def encode(cls, field_value):
        # type: (int) -> bytearray
        """ Encode a dimmer value. """
        if field_value <= 90:
            return bytearray([int(math.ceil(field_value * 6.0 / 10.0))])
        return bytearray([int(53 + field_value - 90)])

    @classmethod
    def decode(cls, byte_str):
        # type: (bytearray) -> int
        """ Decode a byte [0, 63] to an integer [0, 100]. """
        dimmer_value = byte_str[0]
        if dimmer_value <= 54:
            return int(dimmer_value * 10.0 / 6.0)
        return int(90 + dimmer_value - 53)

    @classmethod
    def get_min_decode_bytes(cls):
        """ The dimmer type is always 1 byte. """
        return 1


class OutputFieldType(FieldType):
    """ Field type for OL. """
    def __init__(self):
        pass

    @classmethod
    def get_min_decode_bytes(cls):
        """ Get the minimal amount of bytes required to start decoding. """
        return 1

    @classmethod
    def decode(cls, byte_str):
        # type: (bytearray) -> List[Tuple[int, int]]
        """ Decode a byte string. """
        bytes_required = 1 + (byte_str[0] * 2)

        if len(byte_str) < bytes_required:
            raise NeedMoreBytesException(bytes_required)
        elif len(byte_str) > bytes_required:
            raise ValueError("Got more bytes than required: expected %d, got %d",
                             bytes_required, len(byte_str))
        dimmer_field_type = DimmerFieldType()
        out = []
        for i in range(byte_str[0]):
            id = byte_str[1 + (i * 2)]
            dimmer = dimmer_field_type.decode(byte_str[1 + i * 2 + 1:1 + i * 2 + 2])
            out.append((id, dimmer))
        return out

    @classmethod
    def encode(cls, field_value):
        raise NotImplementedError()


class ErrorListFieldType(FieldType):
    """ Field type for el. """
    def __init__(self):
        pass

    @classmethod
    def get_min_decode_bytes(cls):
        """ Get the minimal amount of bytes required to start decoding. """
        return 1

    @classmethod
    def encode(cls, field_value):
        # type: (List[Tuple[str, int]]) -> bytearray
        """ Encode to byte string. """
        data = bytearray([len(field_value)])
        for field in field_value:
            # field = ('T15', 1234)  # Temperature module 15 has 1234 errors
            data += (bytearray([ord(field[0][0])]) +
                     bytearray([int(field[0][1:]),
                                field[1] // 256,
                                field[1] % 256]))
        return data

    @classmethod
    def decode(cls, byte_str):
        # type: (bytearray) -> List[Tuple[str, int]]
        """ Decode a byte string. """
        nr_modules = byte_str[0]
        bytes_required = 1 + (nr_modules * 4)

        if len(byte_str) < bytes_required:
            raise NeedMoreBytesException(bytes_required)
        elif len(byte_str) > bytes_required:
            raise ValueError("Got more bytes than required: expected %d, got %d", bytes_required, len(byte_str))
        out = []
        for i in range(nr_modules):
            id = '{0}{1}'.format(chr(byte_str[i * 4 + 1]), byte_str[i * 4 + 2])
            nr_errors = byte_str[i * 4 + 3] * 256 + byte_str[i * 4 + 4]

            out.append((id, nr_errors))
        return out
