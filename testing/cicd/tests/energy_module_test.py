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
from tests.hardware import cts, CT

if False:
    from .toolbox import Toolbox

logger = logging.getLogger('openmotics')


@pytest.mark.smoke
@pytest.mark.skip(reason='Unstable module discovery')
@hypothesis.given(cts())
def test_realtime_power(toolbox, ct):  # type: (Toolbox, CT) -> None
    _assert_realtime(toolbox, ct)


@pytest.mark.slow
@pytest.mark.skip(reason='Unstable module discovery')
@hypothesis.given(cts())
def test_power_cycle(toolbox, ct):  # type: (Toolbox, CT) -> None
    cycles = 10
    post_boot_wait = 5  # Wait `post_boot_wait` seconds after powering up the module to start using it
    toolbox.set_output(toolbox.POWER_ENERGY_MODULE, True)
    time.sleep(post_boot_wait)
    _assert_realtime(toolbox, ct)
    with toolbox.disabled_self_recovery():
        for cycle in range(cycles):
            logger.info('power cycle energy module e#{} ({}/{})'.format(ct.module_id, cycle + 1, cycles))
            toolbox.power_cycle_module(toolbox.POWER_ENERGY_MODULE)
            time.sleep(post_boot_wait)
            _assert_realtime(toolbox, ct)


def _assert_realtime(toolbox, ct):  # type: (Toolbox, CT) -> None
    logger.info('validating realtime data from energy module e#{}.{}'.format(ct.module_id, ct.ct_id))
    data = toolbox.dut.get('/get_realtime_power')
    assert str(ct.module_id) in data
    voltage, frequency, current, power = data[str(ct.module_id)][ct.ct_id]
    assert 220 <= voltage <= 240
    assert 49 <= frequency <= 51
    assert 20 <= power <= 40
    assert 0.1 <= current <= 0.5
