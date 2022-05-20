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
from master.core.fields import ByteField, WordField, WordArrayField
from master.core.toolbox import Toolbox

if False:  # MYPY
    from typing import Optional, Any, List


class AbstractBasicAction(object):
    _word_helper = WordField('')
    _byte_helper = ByteField('')
    _word_array_helper = WordArrayField('', 0)

    def __init__(self, action_type, action, extra_parameter):
        self._action_type = self._byte_helper.encode(action_type)  # type: bytearray
        self._action = self._byte_helper.encode(action)  # type: bytearray
        self._extra_parameter = self._word_helper.encode(extra_parameter if extra_parameter is not None else 0)  # type: bytearray

    @property
    def action_type(self):  # type: () -> int
        return self._byte_helper.decode(self._action_type)

    @action_type.setter
    def action_type(self, value): # type: (int) -> None
        self._action_type = self._byte_helper.encode(value)

    @property
    def action(self):  # type: () -> int
        return self._byte_helper.decode(self._action)

    @action.setter
    def action(self, value):  # type: (int) -> None
        self._action = self._byte_helper.encode(value)

    @property
    def extra_parameter(self):  # type: () -> int
        return self._word_helper.decode(self._extra_parameter)

    @extra_parameter.setter
    def extra_parameter(self, value):  # type: (int) -> None
        self._extra_parameter = self._word_helper.encode(value)

    @property
    def extra_parameter_lsb(self):  # type: () -> int
        return self._extra_parameter[1]

    @extra_parameter_lsb.setter
    def extra_parameter_lsb(self, value):  # type: (int) -> None
        self._extra_parameter[1] = min(255, max(0, value))

    @property
    def extra_parameter_msb(self):  # type: () -> int
        return self._extra_parameter[0]

    @extra_parameter_msb.setter
    def extra_parameter_msb(self, value):  # type: (int) -> None
        self._extra_parameter[0] = min(255, max(0, value))

    @property
    def in_use(self):  # type: () -> bool
        return self.action_type != 255 or self.action != 255

    def encode(self):  # type: () -> bytearray
        raise NotImplementedError()

    @staticmethod
    def decode(data):  # type: (bytearray) -> AbstractBasicAction
        raise NotImplementedError()

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return Toolbox.hash(self.encode())

    def __str__(self):
        raise NotImplementedError()

    def __eq__(self, other):  # type: (Any) -> bool
        raise NotImplementedError()


class BasicAction(AbstractBasicAction):
    def __init__(self, action_type, action, device_nr=None, extra_parameter=None):  # type: (int, int, Optional[int], Optional[int]) -> None
        super(BasicAction, self).__init__(action_type, action, extra_parameter)
        self._device_nr = self._word_helper.encode(device_nr if device_nr is not None else 0)  # type: bytearray

    def __str__(self):
        return 'BA({0},{1},{2},{3})'.format(self.action_type, self.action, self.device_nr, self.extra_parameter)

    def __eq__(self, other):  # type: (Any) -> bool
        if not isinstance(other, BasicAction):
            return False
        return self.encode() == other.encode()

    @property
    def device_nr(self):  # type: () -> int
        return self._word_helper.decode(self._device_nr)

    @device_nr.setter
    def device_nr(self, value):  # type: (int) -> None
        self._device_nr = self._word_helper.encode(value)

    @property
    def is_execute_group_action(self):  # type: () -> bool
        return self.action_type == 19 and self.action == 0

    def encode(self):  # type: () -> bytearray
        return self._action_type + self._action + self._device_nr + self._extra_parameter

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


class BasicActionSeries(AbstractBasicAction):
    def __init__(self, action_type, action, device_nrs=None, extra_parameter=None):  # type: (int, int, Optional[List[int]], Optional[int]) -> None
        super(BasicActionSeries, self).__init__(action_type, action, extra_parameter)
        self._device_nrs = self._word_array_helper.encode(device_nrs if device_nrs is not None else [])  # type: bytearray

    @property
    def device_nrs(self):  # type: () -> List[int]
        return self._word_array_helper.decode(self._device_nrs)

    @device_nrs.setter
    def device_nrs(self, value):  # type: (List[int]) -> None
        self._device_nrs = self._word_array_helper.encode(value)

    def encode(self):  # type: () -> bytearray
        return self._action_type + self._action + self._extra_parameter + self._device_nrs

    @staticmethod
    def decode(data):  # type: (bytearray) -> BasicActionSeries
        basic_action_series = BasicActionSeries(action_type=data[0],
                                                action=data[1])
        basic_action_series._extra_parameter = data[2:4]
        basic_action_series._device_nrs = data[4:]
        return basic_action_series

    def __str__(self):
        return 'ES({0},{1},{2},{3})'.format(self.action_type, self.action, self.device_nrs, self.extra_parameter)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):  # type: (Any) -> bool
        if not isinstance(other, BasicActionSeries):
            return False
        return self.encode() == other.encode()

    def __hash__(self):
        return Toolbox.hash(self.encode())
