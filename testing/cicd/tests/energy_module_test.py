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
import time
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
        elements = [toolbox.dut_energy_cts[0]]  # For now, only the first CT is installed
        value = draw(one_of(list(map(just, elements))).
                     filter(lambda x: (x not in used_values)))
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
    cycles = 10
    post_boot_wait = 5  # Wait `post_boot_wait` seconds after powering up the module to start using it
    toolbox.set_output(toolbox.POWER_ENERGY_MODULE, True)
    time.sleep(post_boot_wait)
    _assert_realtime(toolbox, module_id, input_id)
    with toolbox.disabled_self_recovery():
        for cycle in range(cycles):
            logger.info('power cycle energy module e#{} ({}/{})'.format(module_id, cycle + 1, cycles))
            toolbox.power_cycle_module(toolbox.POWER_ENERGY_MODULE)
            time.sleep(post_boot_wait)
            _assert_realtime(toolbox, module_id, input_id)


def _assert_realtime(toolbox, module_id, input_id):  # type: (Toolbox, int, int) -> None
    logger.info('validating realtime data from energy module e#{}.{}'.format(module_id, input_id))
    data = toolbox.dut.get('/get_realtime_power')
    assert str(module_id) in data
    voltage, frequency, current, power = data[str(module_id)][input_id]
    assert 220 <= voltage <= 240
    assert 49 <= frequency <= 51
    assert 20 <= power <= 40
    assert 0.1 <= current <= 0.5
