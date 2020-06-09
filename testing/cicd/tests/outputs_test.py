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

import hypothesis
import pytest
import ujson as json
from hypothesis.strategies import booleans, integers, just

from .hardware import multiple_outputs, outputs

logger = logging.getLogger('openmotics')

DEFAULT_OUTPUT_CONFIG = {'type': 0, 'timer': 2**16 - 1}
DEFAULT_LIGHT_CONFIG = {'type': 255, 'timer': 2**16 - 1}


@pytest.mark.smoke
@hypothesis.given(outputs(), booleans())
def test_events(toolbox, output, to_status):
    from_status = not to_status
    logger.debug('output status {}#{}, expect event {} -> {}'.format(output.type, output.output_id, from_status, to_status))
    toolbox.ensure_output(output, from_status, DEFAULT_OUTPUT_CONFIG)

    hypothesis.note('after output {}#{} set to {}'.format(output.type, output.output_id, to_status))
    toolbox.set_output(output, to_status)
    toolbox.assert_output_changed(output, to_status)


@pytest.mark.smoke
@pytest.mark.skip(reason='fails consistently when running with the ci profile')
@hypothesis.given(outputs(), booleans())
def test_status(toolbox, output, status):
    logger.debug('output status {}#{}, expect status ? -> {}'.format(output.type, output.output_id, status))
    toolbox.configure_output(output, DEFAULT_OUTPUT_CONFIG)

    hypothesis.note('after output {}#{} set to {}'.format(output.type, output.output_id, status))
    toolbox.set_output(output, status)
    time.sleep(0.2)
    toolbox.assert_output_status(output, status)


@pytest.mark.smoke
@hypothesis.given(outputs(), just(True))
def test_timers(toolbox, output, to_status):
    from_status = not to_status
    logger.debug('output timer {}#{}, expect event {} -> {} -> {}'.format(output.type, output.output_id, from_status, to_status, from_status))

    output_config = {'type': 0, 'timer': 3}  # FIXME: event reordering with timer of <2s
    hypothesis.note('with output {}#{} configured as a timer'.format(output.type, output.output_id))
    toolbox.ensure_output(output, from_status, output_config)

    hypothesis.note('after output {}#{} set to {}'.format(output.type, output.output_id, to_status))
    toolbox.set_output(output, to_status)
    toolbox.assert_output_changed(output, to_status)
    toolbox.assert_output_changed(output, from_status, between=(3, 7))


@pytest.mark.smoke
@hypothesis.given(multiple_outputs(3), integers(min_value=0, max_value=254), just(True))
def test_floor_lights(toolbox, outputs, floor_id, output_status):
    light, other_light, other_output = outputs
    logger.debug('light {}#{} on floor {}, expect event {} -> {}'.format(light.type, light.output_id, floor_id, not output_status, output_status))

    output_config = {'floor': floor_id}
    output_config.update(DEFAULT_LIGHT_CONFIG)
    hypothesis.note('with light {}#{} on floor {}'.format(light.type, light.output_id, floor_id))
    toolbox.ensure_output(light, not output_status, output_config)
    output_config = {'floor': 255}  # no floor
    output_config.update(DEFAULT_LIGHT_CONFIG)
    hypothesis.note('with light {}#{} not on floor'.format(other_light.type, other_light.output_id))
    toolbox.ensure_output(other_light, not output_status, output_config)
    output_config = {'floor': floor_id}
    output_config.update(DEFAULT_OUTPUT_CONFIG)  # not a light
    hypothesis.note('with output {}#{} on floor {}'.format(other_output.type, other_output.output_id, floor_id))
    toolbox.ensure_output(other_output, not output_status, output_config)
    time.sleep(2)

    hypothesis.note('after "all lights on" for floor#{}'.format(floor_id))
    toolbox.dut.get('/set_all_lights_floor_on', params={'floor': floor_id})
    toolbox.assert_output_changed(light, output_status)
    toolbox.assert_output_status(other_light, not output_status)
    toolbox.assert_output_status(other_output, not output_status)

    hypothesis.note('after "all lights off" for floor#{}'.format(floor_id))
    toolbox.dut.get('/set_all_lights_floor_off', params={'floor': floor_id})
    toolbox.assert_output_changed(light, not output_status)
    toolbox.assert_output_status(other_light, not output_status)
    toolbox.assert_output_status(other_output, not output_status)


def group_action_ids():
    return integers(min_value=0, max_value=159)


@pytest.mark.smoke
@pytest.mark.skip(reason='fails consistently when running with the ci profile')
@hypothesis.given(multiple_outputs(2), group_action_ids(), booleans())
def test_group_action_toggle(toolbox, outputs, group_action_id, output_status):
    (output, other_output) = outputs
    logger.debug('group action BA#{} for {}#{} {}#{}, expect event {} -> {}'.format(
        group_action_id, output.type, output.output_id, other_output.type, other_output.output_id,
        not output_status, output_status))

    actions = ['162', str(output.output_id), '162', str(other_output.output_id)]  # toggle both outputs
    config = {'id': group_action_id, 'actions': ','.join(actions)}
    toolbox.dut.get('/set_group_action_configuration', params={'config': json.dumps(config)})
    time.sleep(2)

    toolbox.ensure_output(output, not output_status, DEFAULT_OUTPUT_CONFIG)
    toolbox.ensure_output(other_output, not output_status, DEFAULT_OUTPUT_CONFIG)

    hypothesis.note('after running "toggle both outputs" group action {}'.format(group_action_id))
    toolbox.dut.get('/do_group_action', {'group_action_id': group_action_id})
    toolbox.assert_output_changed(output, output_status)
    toolbox.assert_output_changed(other_output, output_status)
