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
from __future__ import absolute_import
import logging
import hypothesis
import pytest
from hypothesis.strategies import composite, just, one_of
from six.moves import map

if False:
    from typing import Tuple, Callable
    from .toolbox import Toolbox

logger = logging.getLogger('openmotics')


@composite
def next_ct(draw):
    used_values = []

    def f(toolbox):  # type: (Toolbox) -> Tuple[int, int]
        value = draw(one_of(list(map(just, toolbox.dut_energy_cts))).
                     filter(lambda x: (x[1] == 0 and  # TODO: Only the first CT can be used
                                       x not in used_values)))
        used_values.append(value)
        hypothesis.note('module e#{}.{}'.format(*value))
        return value
    return f


@pytest.mark.smoke
@hypothesis.given(next_ct())
def test_realtime_power(toolbox, next_ct):  # type: (Toolbox, Callable[[Toolbox], Tuple[int, int]]) -> None
    module_id, input_id = next_ct(toolbox)
    _assert_realtime(toolbox, module_id, input_id)


@pytest.mark.slow
@hypothesis.given(next_ct())
def test_power_cycle(toolbox, next_ct):  # type: (Toolbox, Callable[[Toolbox], Tuple[int, int]]) -> None
    module_id, input_id = next_ct(toolbox)
    for _ in range(10):
        toolbox.power_cycle_module(toolbox.POWER_ENERGY_MODULE)
        _assert_realtime(toolbox, module_id, input_id)


def _assert_realtime(toolbox, module_id, input_id):  # type: (Toolbox, int, int) -> None
    data = toolbox.dut.get('/get_realtime_power')
    assert str(module_id) in data
    voltage, frequency, current, power = data[str(module_id)][input_id]
    expected_power_min, expected_power_max = 5, 10
    assert 220 <= voltage <= 304
    assert 49 <= frequency <= 51
    assert expected_power_min <= power <= expected_power_max
    assert (expected_power_min / voltage) <= current <= (expected_power_max / voltage)
