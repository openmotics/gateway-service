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
import time

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture
def master_communication(toolbox):
    try:
        yield
    except Exception:
        toolbox.dut.get('/reset_master')
    finally:
        toolbox.health_check(timeout=360)


def test_communication_recovery(toolbox, master_communication):
    data = toolbox.dut.get('/get_status', success=False)
    assert data['success'], data

    # Cause master communication errors.
    toolbox.dut.get('/raw_master_action', {'action': 'ST', 'size': 10}, success=False)
    toolbox.dut.get('/raw_master_action', {'action': 'ST', 'size': 12}, success=False)
    toolbox.dut.get('/raw_master_action', {'action': 'ST', 'size': 14}, success=False)
    toolbox.dut.get('/raw_master_action', {'action': 'ST', 'size': 15}, success=False)

    toolbox.health_check(timeout=120)
    toolbox.dut.get('/get_status')


@pytest.mark.slow
def test_offline_recovery(toolbox, master_communication):
    data = toolbox.dut.get('/get_status', success=False)
    assert data['success'], data

    toolbox.dut.get('/reset_master', {'power_on': False})
    start = time.time()
    offline = False
    while time.time() < start + 60:
        data = toolbox.dut.get('/health_check')['health']
        if not data['master']['state']:
            offline = True
            break
    assert offline, 'Master is not offline after being turned off'

    toolbox.health_check(timeout=360)
    toolbox.dut.get('/get_status')
