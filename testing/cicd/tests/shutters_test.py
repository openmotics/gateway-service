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
import hypothesis
import pytest

from tests.hardware import shutters

if False:  # MYPY
    from tests.toolbox import Toolbox
    from tests.hardware_layout import Shutter

logger = logging.getLogger(__name__)


@pytest.mark.smoke
@hypothesis.given(shutters())
def test_shutter_moving(toolbox, shutter):
    # type: (Toolbox, Shutter) -> None
    toolbox.configure_shutter(shutter, {'timer_up': 10,
                                        'timer_down': 10,
                                        'up_down_config': 255})
    logger.debug('shutter {} stopping'.format(shutter))
    toolbox.set_shutter(shutter, 'stop')
    toolbox.assert_shutter_status(shutter, 'stopped', timeout=15)

    logger.debug('shutter {} going up (validate automatic stop)'.format(shutter))
    toolbox.set_shutter(shutter, 'up')
    toolbox.assert_shutter_changed(shutter, from_status='stopped', to_status='going_up', timeout=3)
    toolbox.tester.reset()
    toolbox.assert_shutter_changed(shutter, from_status='going_up', to_status='stopped', timeout=13)
    toolbox.tester.reset()

    logger.debug('shutter {} going down (validate automatic stop'.format(shutter))
    toolbox.set_shutter(shutter, 'down')
    toolbox.assert_shutter_changed(shutter, from_status='stopped', to_status='going_down', timeout=3)
    toolbox.tester.reset()
    toolbox.assert_shutter_changed(shutter, from_status='going_down', to_status='stopped', timeout=13)
    toolbox.tester.reset()

    logger.debug('shutter {} going up (manual stop)'.format(shutter))
    toolbox.set_shutter(shutter, 'up')
    toolbox.assert_shutter_changed(shutter, from_status='stopped', to_status='going_up', timeout=3)
    toolbox.tester.reset()
    toolbox.set_shutter(shutter, 'stop')
    toolbox.assert_shutter_changed(shutter, from_status='going_up', to_status='stopped', timeout=3)
    toolbox.tester.reset()

    logger.debug('shutter {} going down (manual stop'.format(shutter))
    toolbox.set_shutter(shutter, 'down')
    toolbox.assert_shutter_changed(shutter, from_status='stopped', to_status='going_down', timeout=3)
    toolbox.tester.reset()
    toolbox.set_shutter(shutter, 'stop')
    toolbox.assert_shutter_changed(shutter, from_status='going_down', to_status='stopped', timeout=3)
    toolbox.tester.reset()

    logger.debug('shutter {} going up -> down (direction change)'.format(shutter))
    toolbox.set_shutter(shutter, 'up')
    toolbox.assert_shutter_changed(shutter, from_status='stopped', to_status='going_up', timeout=3)
    toolbox.tester.reset()
    toolbox.set_shutter(shutter, 'down')
    toolbox.assert_shutter_changed(shutter, from_status='going_up', to_status='going_down', timeout=3)
    toolbox.tester.reset()
