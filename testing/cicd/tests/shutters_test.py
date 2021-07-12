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

import time
import logging
import hypothesis
import pytest
from hypothesis.strategies import booleans

from tests.hardware import shutters

if False:  # MYPY
    from typing import Any
    from tests.toolbox import Toolbox
    from tests.hardware_layout import Shutter

logger = logging.getLogger(__name__)


@pytest.fixture(scope='module')
def clean_shutters(toolbox_session):
    toolbox = toolbox_session
    toolbox.dirty_shutters = []
    yield
    for shutter in toolbox.dirty_shutters:
        toolbox.configure_shutter(shutter, {'timer_up': 0, 'timer_down': 0, 'up_down_config': 1})


@pytest.mark.smoke
@hypothesis.given(shutters(), booleans(), booleans())
def test_shutter_moving(toolbox, clean_shutters, shutter, primary_direction, inverted):
    # type: (Toolbox, Any, Shutter, bool, bool) -> None
    _ = clean_shutters

    direction = 'up' if primary_direction else 'down'
    inverted_direction = 'down' if primary_direction else 'up'

    logger.info('Testing {} with primary direction {}, {}inverted'.format(
        shutter, direction, '' if inverted else 'not '
    ))

    toolbox.dirty_shutters.append(shutter)
    toolbox.configure_shutter(shutter, {'timer_up': 10,
                                        'timer_down': 10,
                                        'up_down_config': 0 if inverted else 1})
    logger.debug('Shutter {} stopping'.format(shutter))
    toolbox.set_shutter(shutter=shutter, direction='stop')
    toolbox.assert_shutter_status(shutter=shutter, status='stopped', timeout=15, inverted=inverted)

    logger.debug('Shutter {} going {} (validate automatic stop)'.format(shutter, direction))
    toolbox.set_shutter(shutter=shutter, direction=direction)
    toolbox.assert_shutter_changed(shutter=shutter, from_status='stopped', to_status='going_{}'.format(direction), timeout=3, inverted=inverted)
    toolbox.tester.reset()
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_{}'.format(direction), to_status='stopped', timeout=13, inverted=inverted)
    toolbox.tester.reset()

    logger.debug('Shutter {} going {} (manual stop)'.format(shutter, direction))
    toolbox.set_shutter(shutter=shutter, direction=direction)
    toolbox.assert_shutter_changed(shutter=shutter, from_status='stopped', to_status='going_{}'.format(direction), timeout=3, inverted=inverted)
    toolbox.tester.reset()
    toolbox.set_shutter(shutter=shutter, direction='stop')
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_{}'.format(direction), to_status='stopped', timeout=3, inverted=inverted)
    toolbox.tester.reset()

    logger.debug('Shutter {} going {} -> {} (direction change)'.format(shutter, direction, inverted_direction))
    toolbox.set_shutter(shutter=shutter, direction=direction)
    toolbox.assert_shutter_changed(shutter=shutter, from_status='stopped', to_status='going_{}'.format(direction), timeout=3, inverted=inverted)
    toolbox.tester.reset()
    toolbox.set_shutter(shutter=shutter, direction=inverted_direction)
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_{}'.format(direction), to_status='going_{}'.format(inverted_direction), timeout=3, inverted=inverted)
    toolbox.tester.reset()
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_{}'.format(inverted_direction), to_status='stopped', timeout=13, inverted=inverted)
    toolbox.tester.reset()


@pytest.mark.smoke
@hypothesis.given(shutters())
def test_shutter_lock(toolbox, clean_shutters, shutter):
    # type: (Toolbox, Any, Shutter) -> None
    _ = clean_shutters

    logger.info('Testing {} lock'.format(shutter))

    toolbox.dirty_shutters.append(shutter)
    toolbox.configure_shutter(shutter, {'timer_up': 10,
                                        'timer_down': 10,
                                        'up_down_config': 1})
    logger.debug('Shutter {} stopping'.format(shutter))
    toolbox.set_shutter(shutter=shutter, direction='stop')
    toolbox.assert_shutter_status(shutter=shutter, status='stopped', timeout=15)

    logger.debug('Shutter {} going up (manual stop)'.format(shutter))
    toolbox.set_shutter(shutter=shutter, direction='up')
    toolbox.assert_shutter_changed(shutter=shutter, from_status='stopped', to_status='going_up', timeout=3)
    toolbox.tester.reset()
    toolbox.set_shutter(shutter=shutter, direction='stop')
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_up', to_status='stopped', timeout=3)
    toolbox.tester.reset()

    toolbox.lock_shutter(shutter=shutter, locked=True)

    logger.debug('Shutter {} going down (manual stop)'.format(shutter))
    toolbox.set_shutter(shutter=shutter, direction='down')
    toolbox.assert_shutter_status(shutter=shutter, status='stopped', timeout=3)
    time.sleep(3)
    toolbox.assert_shutter_status(shutter=shutter, status='stopped', timeout=3)

    toolbox.lock_shutter(shutter=shutter, locked=False)

    logger.debug('Shutter {} going down (manual stop)'.format(shutter))
    toolbox.set_shutter(shutter=shutter, direction='down')
    toolbox.assert_shutter_changed(shutter=shutter, from_status='stopped', to_status='going_down', timeout=3)
    toolbox.tester.reset()
    toolbox.set_shutter(shutter=shutter, direction='stop')
    toolbox.assert_shutter_changed(shutter=shutter, from_status='going_down', to_status='stopped', timeout=3)
    toolbox.tester.reset()
