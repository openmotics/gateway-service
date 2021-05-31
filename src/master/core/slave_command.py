# Copyright (C) 2020 OpenMotics BV
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
SlaveCommandSpec defines payload handling; (de)serialization
"""
from __future__ import absolute_import
import logging
from master.core.fields import Field, PaddingField, AddressField
from serial_utils import Printable

if False:  # MYPY
    from typing import Optional, List, Dict, Any, Union, Callable


logger = logging.getLogger(__name__)


class Instruction(object):
    def __init__(self, instruction, padding=0):  # type: (str, int) -> None
        self.instruction = instruction
        self.padding = padding


class SlaveCommandSpec(object):
    """
    Defines payload handling and de(serialization)
    """

    REQUEST_PREFIX = b'ST'
    RESPONSE_PREFIX = b'RC'
    RESPONSE_SUFFIX = b'\r\n'

    def __init__(self, instruction, request_fields=None, response_fields=None):  # type: (Instruction, List[Field], List[Field]) -> None
        self.instruction = instruction
        self.address = None  # type: Optional[bytearray]
        self.expected_response_hash = None  # type: Optional[int]
        self._address_field = AddressField('destination')

        self._request_fields = [] if request_fields is None else request_fields
        self.response_fields = [] if response_fields is None else response_fields

        self.header_length = 6  # Literal 'ST/RC' + 4 address bytes
        self._instruction_length = len(self.instruction.instruction)
        self._request_padded_suffix = bytearray([0] * self.instruction.padding) + b'\r\n'
        self._response_prefix_length = len(SlaveCommandSpec.RESPONSE_PREFIX)
        self._response_footer_length = 3 + len(SlaveCommandSpec.RESPONSE_SUFFIX)  # Literal 'C' + 2 CRC bytes + RESPONSE_SUFFIX
        if any(not isinstance(field.length, int) for field in self.response_fields):
            raise RuntimeError('SlaveCommandSpec expects fields with integer lengths')
        self.response_length = (
            self.header_length +
            self._instruction_length +
            sum(field.length for field in self.response_fields if isinstance(field.length, int)) +
            self._response_footer_length
        )

    def set_address(self, address):  # type: (str) -> None
        self.address = self._address_field.encode(address)
        self.expected_response_hash = SlaveCommandSpec.hash(self.address + self.instruction.instruction.encode())

    def create_request_payload(self, fields):  # type: (Dict[str, Any]) -> bytearray
        """ Create the request payloads for slaves using this spec and the provided fields. """
        if self.address is None:
            raise RuntimeError('Cannot create request payload when address is not set.')
        prefix = bytearray(SlaveCommandSpec.REQUEST_PREFIX)
        payload = self.address + self.instruction.instruction.encode()
        for field in self._request_fields:
            payload += field.encode(fields.get(field.name))
        checksum = bytearray(b'C') + SlaveCommandSpec.calculate_crc(payload)
        return prefix + payload + checksum + self._request_padded_suffix

    def consume_response_payload(self, payload):  # type: (bytearray) -> Optional[Dict[str, Any]]
        """ Consumes the payload bytes """
        crc = SlaveCommandSpec.decode_crc(payload[-(self._response_footer_length - 1):-len(SlaveCommandSpec.RESPONSE_SUFFIX)])
        expected_crc = SlaveCommandSpec.decode_crc(SlaveCommandSpec.calculate_crc(payload[self._response_prefix_length:-self._response_footer_length]))
        if crc != expected_crc:
            logger.warning('Unexpected CRC (%s vs expected %s): %s', crc, expected_crc, Printable(payload))
            return None
        payload_data = payload[self.header_length + self._instruction_length:-self._response_footer_length]
        return self._parse_payload(payload_data)

    def _parse_payload(self, payload_data):  # type: (bytearray) -> Dict[str, Any]
        result = {}
        payload_length = len(payload_data)
        for field in self.response_fields:
            if field.length is None:
                continue
            field_length = field.length  # type: Union[int, Callable[[int], int]]
            if callable(field_length):
                field_length = field_length(payload_length)
            if len(payload_data) < field_length:
                logger.warning('Payload did not contain all the expected data: %s', Printable(payload_data))
                break
            data = payload_data[:field_length]  # type: bytearray
            if not isinstance(field, PaddingField):
                result[field.name] = field.decode(data)
            payload_data = payload_data[field_length:]
        return result

    def extract_hash_from_payload(self, payload):  # type: (bytearray) -> Optional[int]
        if len(payload) < self.header_length + self._instruction_length:
            return None
        address = payload[self._response_prefix_length:self._response_prefix_length + 4]
        instruction = payload[self.header_length:self.header_length + self._instruction_length]
        return SlaveCommandSpec.hash(address + instruction)

    @staticmethod
    def calculate_crc(data):  # type: (bytearray) -> bytearray
        crc = 0
        for data_byte in data:
            crc += data_byte
        crc = crc % 65536
        return bytearray([crc // 256, crc % 256])

    @staticmethod
    def decode_crc(crc):  # type: (bytearray) -> List[int]
        return [crc[0], crc[1]]

    @staticmethod
    def hash(entries):  # type: (bytearray) -> int
        times = 1
        result = 0
        for entry in entries:
            result += (entry * 256 * times)
            times += 1
        return result
