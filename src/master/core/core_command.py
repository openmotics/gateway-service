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
CoreCommandSpec defines payload handling; (de)serialization
"""
from __future__ import absolute_import
import logging
from serial_utils import printable
from master.core.fields import PaddingField
from master.core.fields import Field

if False:  # MYPY
    from typing import List, Dict, Any, Union, Callable


logger = logging.getLogger('openmotics')


class CoreCommandSpec(object):
    """
    Defines payload handling and de(serialization)
    """

    # TODO: Add validation callback which is - if not None - is called when the response payload is processed. Arguments are request and response, and it should return a bool indicating whether the validation passed or not.

    def __init__(self, instruction, request_fields=None, response_fields=None, response_instruction=None):
        # type: (str, List[Field], List[Field], str) -> None
        """
        Create a CoreCommandSpec.

        :param instruction: name of the instruction as described in the Core api.
        :param request_fields: Fields in this request
        :param response_fields: Fields in the response
        :param response_instruction: name of the instruction of the answer in case it would be different from the response
        """
        self.instruction = bytearray([ord(c) for c in instruction])
        self.request_fields = [] if request_fields is None else request_fields
        self.response_fields = [] if response_fields is None else response_fields
        self.response_instruction = bytearray([ord(c) for c in response_instruction]) if response_instruction is not None else self.instruction

    def create_request_payload(self, fields):  # type: (Dict[str, Any]) -> bytearray
        """
        Create the request payload for the Core using this spec and the provided fields.

        :param fields: dictionary with values for the fields
        """
        payload = bytearray()
        for field in self.request_fields:
            payload += field.encode(fields.get(field.name))
        return payload

    def consume_response_payload(self, payload):  # type: (bytearray) -> Dict[str, Any]
        """
        Consumes the payload bytes

        :param payload Payload from the Core response
        :returns: Dictionary containing the parsed response
        """
        payload_length = len(payload)
        result = {}
        for field in self.response_fields:
            if field.length is None:
                continue
            field_length = field.length  # type: Union[int, Callable[[int], int]]
            if callable(field_length):
                field_length = field_length(payload_length)
            if len(payload) < field_length:
                logger.warning('Payload for instruction {0} did not contain all the expected data: {1}'.format(self.instruction, printable(payload)))
                break
            data = payload[:field_length]
            if not isinstance(field, PaddingField):
                result[field.name] = field.decode(data)
            payload = payload[field_length:]
        if payload != '':
            logger.warning('Payload for instruction {0} could not be consumed completely: {1}'.format(self.instruction, printable(payload)))
        return result

    def __eq__(self, other):
        return self.instruction == other.instruction \
            and self.response_instruction == other.response_instruction

    def __repr__(self):
        # type: () -> str
        return '<CoreCommandSpec {}>'.format(self.instruction)

