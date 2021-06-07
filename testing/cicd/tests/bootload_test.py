# Copyright (C) 2021 OpenMotics BV
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
import socket
import ssl
import time

import hypothesis
import psutil
import pytest
from hypothesis.strategies import just, one_of

logger = logging.getLogger(__name__)

firmwares = one_of([
    # just({'master': '3.143.103'}),
    just({'master': '3.143.116'}),
    just({'output': '3.1.2'}),
    just({'output': '3.1.13'}),
    just({'input': '3.1.0'}),
    just({'input': '3.1.2'}),
    just({'can': '4.1.21'}),
    just({'can': '4.1.30'}),
    just({'dimmer': '3.1.0'}),
    just({'dimmer': '3.1.5'}),
    just({'temperature': '3.1.1'}),
    just({'temperature': '3.1.5'}),
])


@pytest.mark.unstable
@hypothesis.given(firmwares)
def test_firmware_update(toolbox, firmware):
    versions = toolbox.get_firmware_versions()
    logger.info('firmware {}'.format(' '.join('{}={}'.format(k, v) for k, v in versions.items())))
    module, version = next(iter(firmware.items()))
    logger.info('Updating {} to {}...'.format(module, version))
    toolbox.dut.get('/update_firmware', firmware)
    time.sleep(5)
    toolbox.health_check(timeout=120)
