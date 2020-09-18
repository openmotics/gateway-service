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
Communication fields
"""
from __future__ import absolute_import
import struct

if False:  # MYPY
    from typing import Any, Optional, List, Tuple, Union, Callable


class Field(object):
    """
    Field of a command
    """

    def __init__(self, name, length, limits=None):  # type: (str, Optional[Union[int, Callable[[int], int]]], Optional[Tuple[int, int]]) -> None
        self.name = name
        self.length = length
        if limits is not None:
            self.limits = limits
        elif isinstance(length, int):
            self.limits = (0, 2 ** (8 * length) - 1)
        else:
            self.limits = (0, 255)

    def encode(self, value):  # type: (Any) -> bytearray
        """
        Encodes a high-level value into a byte string
        :param value: The high-level value (e.g. 'foobar', 23475, 15, '10.2.25.6')
        :return: The bytearray (e.g. b'd%_\xf8\xa5?@_1' / [234, 12, 65, 23, 119])
        """
        raise NotImplementedError()

    def decode(self, data):  # type: (bytearray) -> Any
        """
        Decodes a low-level byte string into a high-level value
        :param data: Bytearray to decode (e.g. b'd%_\xf8\xa5?@_1' / [234, 12, 65, 23, 119])
        :returns: High-level value (e.g. 'foobar', 23475, 15, '10.2.25.6')
        """
        raise NotImplementedError()

    def _check_limits(self, value):  # type: (Union[float, int]) -> None
        if value is None or not (self.limits[0] <= value <= self.limits[1]):
            raise ValueError('Value `{0}` out of limits: {1} <= value <= {2}'.format(value, self.limits[0], self.limits[1]))

    def __str__(self):
        return '{0}({1})'.format(self.name, self.length)

    def __repr__(self):
        return str(self)


class ByteField(Field):
    def __init__(self, name):
        super(ByteField, self).__init__(name, 1)

    def encode(self, value):  # type: (int) -> bytearray
        self._check_limits(value)
        return bytearray([value])

    def decode(self, data):  # type: (bytearray) -> int
        return data[0]


class CharField(Field):
    def __init__(self, name):
        super(CharField, self).__init__(name, 1)

    def encode(self, value):  # type: (str) -> bytearray
        value = str(value)
        if len(value) != 1:
            raise ValueError('Value `{0}` must be a single-character string'.format(value))
        return bytearray([ord(value[0])])

    def decode(self, data):  # type: (bytearray) -> str
        return str(chr(data[0]))


class TemperatureField(Field):
    def __init__(self, name):
        super(TemperatureField, self).__init__(name, 1, limits=(-32, 95))

    def encode(self, value):  # type: (Optional[float]) -> bytearray
        if value is not None:
            self._check_limits(value)
        if value is None:
            return bytearray([255])
        value = int((float(value) + 32) * 2)
        return bytearray([value])

    def decode(self, data):  # type: (bytearray) -> Optional[float]
        if data[0] == 255:
            return None
        return float(data[0]) / 2 - 32


class HumidityField(Field):
    def __init__(self, name):
        super(HumidityField, self).__init__(name, 1, limits=(0, 100))

    def encode(self, value):  # type: (Optional[float]) -> bytearray
        if value is not None:
            self._check_limits(value)
        if value is None:
            return bytearray([255])
        value = int(float(value) * 2)
        return bytearray([value])

    def decode(self, data):  # type: (bytearray) -> Optional[float]
        if data[0] == 255:
            return None
        return float(data[0]) / 2


class WordField(Field):
    def __init__(self, name):
        super(WordField, self).__init__(name, 2)

    def encode(self, value):  # type: (int) -> bytearray
        self._check_limits(value)
        return bytearray(struct.pack('>H', value))

    def decode(self, data):  # type: (bytearray) -> int
        return struct.unpack('>H', data)[0]


class UInt32Field(Field):
    def __init__(self, name):
        super(UInt32Field, self).__init__(name, 4)

    def encode(self, value):  # type: (int) -> bytearray
        self._check_limits(value)
        return bytearray(struct.pack('>I', value))

    def decode(self, data):  # type: (bytearray) -> int
        return struct.unpack('>I', data)[0]


class _ArrayField(Field):
    def __init__(self, name, length, field):
        super(_ArrayField, self).__init__(name, length)
        self._field = field(name)

    def encode(self, value):  # type: (Any) -> bytearray
        if len(value) != self.length:
            raise ValueError('Value `{0}` should be an array of {1} items with {2} <= item <= {3}'.format(value,
                                                                                                          self.length,
                                                                                                          self._field.limits[0],
                                                                                                          self._field.limits[1]))
        data = bytearray()
        for item in value:
            data += self._field.encode(item)
        return data

    def decode(self, data):  # type: (bytearray) -> Any
        result = []
        for i in range(0, len(data), self._field.length):
            result.append(self._field.decode(data[i:i + self._field.length]))
        return result


class RawByteArrayField(_ArrayField):
    def __init__(self, name, length):
        super(RawByteArrayField, self).__init__(name, length, ByteField)

    def encode(self, value):  # type: (bytearray) -> bytearray
        return super(RawByteArrayField, self).encode(list(value))

    def decode(self, data):  # type: (bytearray) -> bytearray
        return bytearray(super(RawByteArrayField, self).decode(data))


class ByteArrayField(_ArrayField):
    def __init__(self, name, length, field=None):
        if field is None:
            field = ByteField
        super(ByteArrayField, self).__init__(name, length, field)

    def encode(self, value):  # type: (List[int]) -> bytearray
        return super(ByteArrayField, self).encode(value)

    def decode(self, data):  # type: (bytearray) -> List[int]
        return super(ByteArrayField, self).decode(data)


class TemperatureArrayField(ByteArrayField):
    def __init__(self, name, length):
        super(TemperatureArrayField, self).__init__(name, length, TemperatureField)


class HumidityArrayField(ByteArrayField):
    def __init__(self, name, length):
        super(HumidityArrayField, self).__init__(name, length, HumidityField)


class WordArrayField(ByteArrayField):
    def __init__(self, name, length):
        super(WordArrayField, self).__init__(name, length, WordField)


class LiteralBytesField(Field):
    def __init__(self, *data):
        super(LiteralBytesField, self).__init__('literal_bytes', len(data))
        self._data = bytearray(data)

    def encode(self, value):  # type: (None) -> bytearray
        if value is not None:
            raise ValueError('LiteralBytesField does not support value encoding')
        return self._data

    def decode(self, data):  # type: (bytearray) -> None
        raise ValueError('LiteralBytesField does not support decoding')


class AddressField(Field):
    def __init__(self, name, length=4):
        super(AddressField, self).__init__(name, length)

    def encode(self, value):  # type: (str) -> bytearray
        if not isinstance(self.length, int):
            raise RuntimeError('Field length should be an integer')
        example = '.'.join(['ID{0}'.format(i) for i in range(self.length - 1, -1, -1)])
        error_message = 'Value `{0}` should be a string in the format of {1}, where 0 <= IDx <= 255'.format(value, example)
        parts = str(value).split('.')
        if len(parts) != self.length:
            raise ValueError(error_message)
        data = []
        for part in parts:
            try:
                int_part = int(part)
            except ValueError:
                raise ValueError(error_message)
            if not (0 <= int_part <= 255):
                raise ValueError(error_message)
            data.append(int_part)
        return bytearray(data)

    def decode(self, data):  # type: (bytearray) -> str
        return '.'.join('{0:03}'.format(item) for item in data)


class StringField(Field):
    def __init__(self, name):
        super(StringField, self).__init__(name, length=None)

    def encode(self, value):  # type: (str) -> bytearray
        return bytearray([ord(c) for c in value] + [0])

    def decode(self, data):  # type: (bytearray) -> str
        return ''.join(str(chr(item)) for item in data).strip('\x00')


class VersionField(AddressField):
    def __init__(self, name):
        super(VersionField, self).__init__(name, 3)

    def encode(self, value):  # type: (str) -> bytearray
        if not isinstance(self.length, int):
            raise RuntimeError('Field length should be an integer')
        example = '.'.join(['F{0}'.format(i) for i in range(self.length)])
        error_message = 'Value `{0}` should be a string in the format of {1}, where 0 <= Fx <= 255'.format(value, example)
        parts = str(value).split('.')
        if len(parts) != self.length:
            raise ValueError(error_message)
        data = []
        for part in parts:
            try:
                int_part = int(part)
            except ValueError:
                raise ValueError(error_message)
            if not (0 <= int_part <= 255):
                raise ValueError(error_message)
            data.append(int_part)
        return bytearray(data)

    def decode(self, data):  # type: (bytearray) -> str
        return '.'.join(str(item) for item in data)


class PaddingField(Field):
    def __init__(self, length):
        super(PaddingField, self).__init__('padding', length)

    def encode(self, value):  # type: (Any) -> bytearray
        _ = value
        if not isinstance(self.length, int):
            raise RuntimeError('Field length should be an integer')
        return bytearray([0] * self.length)

    def decode(self, data):  # type: (bytearray) -> str
        _ = data
        if not isinstance(self.length, int):
            raise RuntimeError('Field length should be an integer')
        return '.' * self.length
