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
from hypothesis.strategies import booleans

from tests.hardware import shutters

if False:  # MYPY
    from tests.toolbox import Toolbox
    from tests.hardware_layout import Shutter

logger = logging.getLogger(__name__)


@pytest.mark.smoke
@hypothesis.given(shutters(), booleans(), booleans())
def test_shutter_moving(toolbox, shutter, primary_direction, inverted):
    # type: (Toolbox, Shutter) -> None

    direction = 'up' if primary_direction else 'down'
    inverted_direction = 'down' if primary_direction else 'up'

    logger.info('Testing {} with primary direction {}, {}inverted'.format(
        shutter, primary_direction, '' if inverted else 'not '
    ))

    toolbox.configure_shutter(shutter, {'timer_up': 10,
                                        'timer_down': 10,
                                        'up_down_config': 0 if inverted else 255})
    logger.debug('shutter {} stopping'.format(shutter))
    toolbox.set_shutter(shutter=shutter, direction='stop')
    toolbox.assert_shutter_status(shutter=shutter, status='stopped', timeout=15, inverted=inverted)

    logger.debug('shutter {} going {} (validate automatic stop)'.format(shutter, direction))
    toolbox.set_shutter(shutter=shutter, direction=direction)
    toolbox.assert_shutter_changed(shutter=shutter, from_status='stopped', to_status='going_{}'.format(direction), timeout=3, inverted=inverted)
    toolbox.tester.reset()
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_{}'.format(direction), to_status='stopped', timeout=13, inverted=inverted)
    toolbox.tester.reset()

    logger.debug('shutter {} going {} (manual stop)'.format(shutter, direction))
    toolbox.set_shutter(shutter=shutter, direction=direction)
    toolbox.assert_shutter_changed(shutter=shutter, from_status='stopped', to_status='going_{}'.format(direction), timeout=3, inverted=inverted)
    toolbox.tester.reset()
    toolbox.set_shutter(shutter=shutter, direction='stop')
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_{}'.format(direction), to_status='stopped', timeout=3, inverted=inverted)
    toolbox.tester.reset()

    logger.debug('shutter {} going {} -> {} (direction change)'.format(shutter, direction, inverted_direction))
    toolbox.set_shutter(shutter=shutter, direction=direction)
    toolbox.assert_shutter_changed(shutter=shutter, from_status='stopped', to_status='going_{}'.format(direction), timeout=3, inverted=inverted)
    toolbox.tester.reset()
    toolbox.set_shutter(shutter=shutter, direction=inverted_direction)
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_{}'.format(direction), to_status='going_{}'.format(inverted_direction), timeout=3, inverted=inverted)
    toolbox.tester.reset()
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_{}'.format(inverted_direction), to_status='stopped', timeout=13, inverted=inverted)
    toolbox.tester.reset()
