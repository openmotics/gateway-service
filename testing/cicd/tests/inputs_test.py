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
import ujson as json
from hypothesis.strategies import booleans, integers, just

from tests.hardware import inputs, multiple_outputs, outputs

logger = logging.getLogger('openmotics')

DEFAULT_OUTPUT_CONFIG = {'timer': 2**16 - 1}
DEFAULT_INPUT_CONFIG = {'invert': 255}


@pytest.mark.smoke
@hypothesis.given(inputs(), outputs(), booleans())
def test_actions(toolbox, input, output, to_status):
    from_status = not to_status
    logger.debug('input action {}#{} to {}#{}, expect event {} -> {}'.format(
        input.type, input.input_id,
        output.type, output.output_id,
        from_status, to_status))

    hypothesis.note('with input {}#{} action set to {}#{}'.format(input.type, input.input_id, output.type, output.output_id))
    input_config = {'id': input.input_id, 'action': output.output_id}
    input_config.update(DEFAULT_INPUT_CONFIG)
    toolbox.dut.get('/set_input_configuration', {'config': json.dumps(input_config)})

    # NOTE ensure output status _after_ input configuration, changing
    # inputs can impact the output status for some reason.
    toolbox.ensure_output(output, from_status, DEFAULT_OUTPUT_CONFIG)

    toolbox.press_input(input)
    toolbox.assert_output_changed(output, to_status)


@pytest.mark.slow
@hypothesis.settings(max_examples=2)
@hypothesis.given(inputs(), outputs(), just(True))
def test_motion_sensor(toolbox, input, output, to_status):
    from_status = not to_status
    logger.debug('motion sensor {}#{} to {}#{}, expect event {} -> {} after 2m30s'.format(
        input.type, input.input_id,
        output.type, output.output_id,
        from_status, to_status))
    hypothesis.note('with input {}#{} action set to timeout after 2m30s'.format(input.type, input.input_id))
    actions = ['195', str(output.output_id)]  # output timeout of 2m30s
    input_config = {'id': input.input_id, 'basic_actions': ','.join(actions), 'action': 240}
    input_config.update(DEFAULT_INPUT_CONFIG)
    toolbox.dut.get('/set_input_configuration', {'config': json.dumps(input_config)})

    # NOTE ensure output status _after_ input configuration, changing
    # inputs can impact the output status for some reason.
    toolbox.ensure_output(output, from_status, DEFAULT_OUTPUT_CONFIG)

    toolbox.press_input(input)
    toolbox.assert_output_changed(output, to_status)
    logger.warning('should use a shorter timeout')
    toolbox.assert_output_changed(output, from_status, between=(130, 180))


def group_action_ids():
    return integers(min_value=0, max_value=159)


@pytest.mark.smoke
@hypothesis.given(inputs(), multiple_outputs(2), group_action_ids(), booleans())
def test_group_action_toggle(toolbox, input, outputs, group_action_id, to_status):
    output, other_output = outputs
    from_status = not to_status
    logger.debug('group action BA#{} for {}#{} to {}#{} {}#{}, expect event {} -> {}'.format(
        group_action_id,
        input.type, input.input_id,
        output.type, output.output_id,
        other_output.type, other_output.output_id,
        from_status, to_status))

    hypothesis.note('with input {}#{} action set to GA#{}'.format(input.type, input.input_id, group_action_id))
    actions = ['2', str(group_action_id)]
    input_config = {'id': input.input_id, 'basic_actions': ','.join(actions), 'action': 240}
    input_config.update(DEFAULT_INPUT_CONFIG)
    toolbox.dut.get('/set_input_configuration', {'config': json.dumps(input_config)})

    hypothesis.note('with action GA#{} configured as "toggle both outputs"'.format(group_action_id))
    actions = ['162', str(output.output_id), '162', str(other_output.output_id)]  # toggle both outputs
    config = {'id': group_action_id, 'actions': ','.join(actions)}
    toolbox.dut.get('/set_group_action_configuration', params={'config': json.dumps(config)})

    toolbox.ensure_output(output, from_status, DEFAULT_OUTPUT_CONFIG)
    toolbox.ensure_output(other_output, from_status, DEFAULT_OUTPUT_CONFIG)

    toolbox.press_input(input)
    toolbox.assert_output_changed(output, to_status)
    toolbox.assert_output_changed(other_output, to_status)
