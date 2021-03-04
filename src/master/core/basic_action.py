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
Contains Basic Action related code
"""

from __future__ import absolute_import
from master.core.fields import ByteField, WordField

if False:  # MYPY
    from typing import Optional, Any


class BasicAction(object):
    def __init__(self, action_type, action, device_nr=None, extra_parameter=None):  # type: (int, int, Optional[int], Optional[int]) -> None
        self._word_helper = WordField('')
        self._byte_helper = ByteField('')
        self._action_type = self._byte_helper.encode(action_type)  # type: bytearray
        self._action = self._byte_helper.encode(action)  # type: bytearray
        self._device_nr = self._word_helper.encode(device_nr if device_nr is not None else 0)  # type: bytearray
        self._extra_parameter = self._word_helper.encode(extra_parameter if extra_parameter is not None else 0)  # type: bytearray

    @property
    def action_type(self):  # type: () -> int
        return self._byte_helper.decode(self._action_type)

    @property
    def action(self):  # type: () -> int
        return self._byte_helper.decode(self._action)

    @property
    def device_nr(self):  # type: () -> int
        return self._word_helper.decode(self._device_nr)

    @property
    def extra_parameter(self):  # type: () -> int
        return self._word_helper.decode(self._extra_parameter)

    def encode(self):  # type: () -> bytearray
        return self._action_type + self._action + self._device_nr + self._extra_parameter

    @property
    def in_use(self):  # type: () -> bool
        return self.action_type != 255 or self.action != 255

    @property
    def is_execute_group_action(self):  # type: () -> bool
        return self.action_type == 19 and self.action == 0

    @staticmethod
    def decode(data):  # type: (bytearray) -> BasicAction
        basic_action = BasicAction(action_type=data[0],
                                   action=data[1])
        basic_action._device_nr = data[2:4]
        basic_action._extra_parameter = data[4:6]
        return basic_action

    @staticmethod
    def empty():  # type: () -> BasicAction
        return BasicAction.decode(bytearray([255] * 6))

    def __str__(self):
        return 'BA({0},{1},{2},{3})'.format(self.action_type, self.action, self.device_nr, self.extra_parameter)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):  # type: (Any) -> bool
        if not isinstance(other, BasicAction):
            return False
        return self.encode() == other.encode()

    def __hash__(self):
        hash_value = 0
        for i, value in enumerate(self.encode()):
            hash_value += 256 ** i * value
        return hash_value
