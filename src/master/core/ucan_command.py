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
UCANCommandSpec defines payload handling; (de)serialization
"""
from __future__ import absolute_import
import logging
import math
from master.core.fields import Field, PaddingField, UInt32Field, StringField
from master.core.toolbox import Toolbox
from serial_utils import printable

if False:  # MYPY
    from typing import Optional, List, Dict, Any, Iterator, Union, Callable


logger = logging.getLogger('openmotics')


class SID(object):
    NORMAL_COMMAND = 5
    BOOTLOADER_COMMAND = 1
    BOOTLOADER_PALLET = 0


class PalletType(object):
    MCU_ID_REQUEST = 0x00
    MCU_ID_REPLY = 0x01
    BOOTLOADER_ID_REQUEST = 0x02
    BOOTLOADER_ID_REPLY = 0x03
    FLASH_WRITE_REQUEST = 0x04
    FLASH_WRITE_REPLY = 0x05
    FLASH_READ_REQUEST = 0x06
    FLASH_READ_REPLY = 0x07
    EEPROM_WRITE_REQUEST = 0x08
    EEPROM_WRITE_REPLY = 0x09
    EEPROM_READ_REQUEST = 0x0A
    EEPROM_READ_REPLY = 0x0B
    RESET_REQUEST = 0x0C
    RESET_REPLY = 0x0D
    FLASH_ERASE_REQUEST = 0x0E
    FLASH_ERASE_REPLY = 0x0F
    INVALID_PALETTE_TYPE = 0x10


class Instruction(object):
    def __init__(self, instruction, checksum_byte=None):  # type: (List[int], Optional[int]) -> None
        self.instruction = bytearray(instruction)
        self.checksum_byte = checksum_byte


class UCANCommandSpec(object):
    """
    Defines payload handling and de(serialization)
    """

    def __init__(self, sid, identifier, instructions, request_fields=None, response_instructions=None, response_fields=None):
        # type: (int, Field, Optional[List[Instruction]], Optional[List[List[Field]]], Optional[List[Instruction]], Optional[List[Field]]) -> None
        """
        Create a UCANCommandSpec.

        :param sid: SID
        :param instructions: Instruction objects for this command
        :param identifier: The field to be used as extra identifier
        :param request_fields: Fields in this request
        :param response_instructions: List of all the response instruction bytes
        :param response_fields: Fields in the response
        """
        self.sid = sid
        self.instructions = instructions
        self._identifier = identifier

        self._request_fields = [[]] if request_fields is None else request_fields  # type: List[List[Field]]
        self._response_fields = [] if response_fields is None else response_fields
        self.response_instructions = [] if response_instructions is None else response_instructions

        if not isinstance(self._identifier.length, int):
            raise RuntimeError('Identifier length should be an integer')
        self.header_length = 2 + self._identifier.length
        self.headers = []  # type: List[int]
        self._response_instruction_by_hash = {}  # type: Dict[int, Instruction]

    def set_identity(self, identity):  # type: (str) -> None
        self.headers = []
        self._response_instruction_by_hash = {}
        destination_address = self._identifier.encode(identity)
        for instruction in self.response_instructions:
            hash_value = Toolbox.hash(instruction.instruction + destination_address)
            self.headers.append(hash_value)
            self._response_instruction_by_hash[hash_value] = instruction

    def create_request_payloads(self, identity, fields):  # type: (str, Dict[str, Any]) -> Iterator[bytearray]
        """
        Create the request payloads for the uCAN using this spec and the provided fields.

        :param identity: The actual identity
        :param fields: dictionary with values for the fields
        """
        if self.instructions is None or len(self.instructions) == 0:
            raise RuntimeError('Cannot generate payloads for an empty instruction')
        destination_address = self._identifier.encode(identity)
        for index, instruction in enumerate(self.instructions):
            payload = instruction.instruction + destination_address
            for field in self._request_fields[index]:
                payload += field.encode(fields.get(field.name))
            payload.append(UCANCommandSpec.calculate_crc(payload))
            yield payload

    def consume_response_payload(self, payload):  # type: (Union[bytearray, Dict[int, bytearray]]) -> Optional[Dict[str, Any]]
        """
        Consumes the payload bytes

        :param payload Payload from the uCAN responses
        :returns: Dictionary containing the parsed response
        """
        if isinstance(payload, bytearray):
            raise RuntimeError('An UCANCommandSpec cannot consume bytearray payloads')
        payload_data = bytearray()
        for response_hash in self.headers:
            # Headers are ordered
            if response_hash not in payload:
                logger.warning('Payload did not contain all the expected data: {0}'.format(printable(payload)))
                return None
            response_instruction = self._response_instruction_by_hash[response_hash]
            payload_entry = payload[response_hash]
            if response_instruction.checksum_byte is None:
                raise RuntimeError('Unknown checksum byte')
            crc = payload_entry[response_instruction.checksum_byte]
            expected_crc = UCANCommandSpec.calculate_crc(payload_entry[:response_instruction.checksum_byte])
            if crc != expected_crc:
                logger.info('Unexpected CRC ({0} vs expected {1}): {2}'.format(crc, expected_crc, printable(payload_entry)))
                return None
            usefull_payload = payload_entry[self.header_length:response_instruction.checksum_byte]
            payload_data += usefull_payload
        return self._parse_payload(payload_data)

    def _parse_payload(self, payload_data):  # type: (bytearray) -> Dict[str, Any]
        result = {}
        payload_length = len(payload_data)
        for field in self._response_fields:
            if isinstance(field, StringField):
                field_length = list(payload_data).index(0) + 1  # type: Union[int, Callable[[int], int]]
            elif field.length is not None:
                field_length = field.length
            else:
                continue
            if callable(field_length):
                field_length = field_length(payload_length)
            if len(payload_data) < field_length:
                logger.warning('Payload did not contain all the expected data: {0}'.format(printable(payload_data)))
                break
            data = payload_data[:field_length]
            if not isinstance(field, PaddingField):
                result[field.name] = field.decode(data)
            payload_data = payload_data[field_length:]
        return result

    @staticmethod
    def calculate_crc(data):  # type: (bytearray) -> int
        """
        Calculate the CRC of the data.

        :param data: Data for which to calculate the CRC
        :returns: CRC
        """
        crc = 0
        for data_byte in data:
            crc += data_byte
        return crc % 256

    def extract_hash(self, payload):
        return Toolbox.hash(payload[0:self.header_length])


class UCANPalletCommandSpec(UCANCommandSpec):
    """
    Defines payload handling and de(serialization)
    """

    def __init__(self, identifier, pallet_type, request_fields=None, response_fields=None):
        # type: (Field, int, Optional[List[Field]], Optional[List[Field]]) -> None
        """
        Create a UCANCommandSpec.

        :param identifier: The field to be used as extra identifier
        :param pallet_type: The type of the pallet
        :param request_fields: Fields in this request
        :param response_fields: Fields in the response
        """
        super(UCANPalletCommandSpec, self).__init__(sid=SID.BOOTLOADER_PALLET,
                                                    identifier=identifier,
                                                    instructions=None,
                                                    request_fields=[request_fields] if request_fields is not None else None,
                                                    response_instructions=[],
                                                    response_fields=response_fields)
        self._pallet_type = pallet_type
        self._uint32_helper = UInt32Field('')

    def set_identity(self, identity):
        _ = identity  # Not used for pallet communications
        pass

    def create_request_payloads(self, identity, fields):  # type: (str, Dict[str, Any]) -> Iterator[bytearray]
        """
        Create the request payloads for the uCAN using this spec and the provided fields.

        :param identity: The actual identity
        :param fields: dictionary with values for the fields
        """
        destination_address = self._identifier.encode(identity)
        source_address = self._identifier.encode('000.000.000')
        payload = source_address + destination_address + bytearray([self._pallet_type])
        for field in self._request_fields[0]:
            payload += field.encode(fields.get(field.name))
        payload += self._uint32_helper.encode(UCANPalletCommandSpec.calculate_crc(payload))
        segments = int(math.ceil(len(payload) / 7.0))
        first = True
        while len(payload) > 0:
            header = ((1 if first else 0) << 7) + (segments - 1)
            sub_payload = bytearray([header]) + payload[:7]
            payload = payload[7:]
            yield sub_payload
            first = False
            segments -= 1

    def consume_response_payload(self, payload):  # type: (Union[bytearray, Dict[int, bytearray]]) -> Optional[Dict[str, Any]]
        """
        Consumes the payload bytes

        :param payload Payload from the uCAN responses
        :returns: Dictionary containing the parsed response
        """
        if not isinstance(payload, bytearray):
            raise RuntimeError('UCANPalletCommandSpec can only consume bytearray payloads')
        crc = UCANPalletCommandSpec.calculate_crc(payload)
        if crc != 0:
            logger.info('Unexpected pallet CRC ({0} != 0): {1}'.format(crc, printable(payload)))
            return None
        return self._parse_payload(payload[7:-4])

    @staticmethod
    def calculate_crc(data, remainder=0):  # type: (bytearray, int) -> int
        """
        Calculates the CRC of data. The algorithm is designed to make sure flowing statement is True:
        > crc(data + crc(data)) == 0

        :param data: Data for which to calculate the CRC
        :param remainder: Optional initial remainder of CRC calculation
        :returns: CRC
        """
        width = 32
        topbit = 1 << (width - 1)
        polynomial = 0x04C11DB7
        for data_item in data:
            remainder ^= data_item << (width - 8)
            remainder &= 0xFFFFFFFF
            for _ in range(7, -1, -1):
                if remainder & topbit:
                    remainder = (remainder << 1) ^ polynomial
                    remainder &= 0xFFFFFFFF
                else:
                    remainder = (remainder << 1)
                    remainder &= 0xFFFFFFFF
        return remainder
