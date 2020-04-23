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
from hypothesis.strategies import booleans, composite, integers, just, one_of
from six.moves import map

logger = logging.getLogger('openmotics')

DEFAULT_OUTPUT_CONFIG = {'timer': 2**16 - 1}
DEFAULT_INPUT_CONFIG = {'invert': 255}


@composite
def next_input(draw):
    used_values = []
    def f(toolbox):
        value = draw(one_of(list(map(just, toolbox.dut_inputs))).filter(lambda x: x not in used_values))
        used_values.append(value)
        hypothesis.note('module i#{}'.format(value))
        return value
    return f


@composite
def next_output(draw):
    used_values = []
    def f(toolbox):
        value = draw(one_of(list(map(just, toolbox.dut_outputs))).filter(lambda x: x not in used_values))
        used_values.append(value)
        hypothesis.note('module o#{}'.format(value))
        return value
    return f


@pytest.mark.smoke
@hypothesis.given(next_input(), next_output(), booleans())
def test_actions(toolbox, next_input, next_output, output_status):
    input_id, output_id = (next_input(toolbox), next_output(toolbox))
    logger.info('input action i#{} to o#{}, expect event {} -> {}'.format(input_id, output_id, not output_status, output_status))

    input_config = {'id': input_id, 'action': output_id}
    input_config.update(DEFAULT_INPUT_CONFIG)
    toolbox.dut.get('/set_input_configuration', {'config': json.dumps(input_config)})

    # NOTE ensure output status _after_ input configuration, changing
    # inputs can impact the output status for some reason.
    toolbox.ensure_output(output_id, not output_status, DEFAULT_OUTPUT_CONFIG)

    toolbox.press_input(input_id)
    toolbox.assert_output_changed(output_id, output_status)


@pytest.mark.slow
@hypothesis.settings(max_examples=2)
@hypothesis.given(next_input(), next_output(), just(True))
def test_motion_sensor(toolbox, next_input, next_output, output_status):
    input_id, output_id = (next_input(toolbox), next_output(toolbox))

    logger.info('motion sensor i#{} to o#{}, expect event {} -> {} after 2m30s'.format(input_id, output_id, output_status, not output_status))
    actions = ['195', str(output_id)]  # output timeout of 2m30s
    input_config = {'id': input_id, 'basic_actions': ','.join(actions), 'action': 240}
    input_config.update(DEFAULT_INPUT_CONFIG)
    toolbox.dut.get('/set_input_configuration', {'config': json.dumps(input_config)})

    # NOTE ensure output status _after_ input configuration, changing
    # inputs can impact the output status for some reason.
    toolbox.ensure_output(output_id, not output_status, DEFAULT_OUTPUT_CONFIG)

    toolbox.press_input(input_id)
    toolbox.assert_output_changed(output_id, output_status)
    logger.warning('should use a shorter timeout')
    toolbox.assert_output_changed(output_id, not output_status, between=(130, 180))


@pytest.mark.smoke
@hypothesis.given(next_input(), next_output(), integers(min_value=0, max_value=159), booleans())
def test_group_action_toggle(toolbox, next_input, next_output, group_action_id, output_status):
    (input_id, output_id, other_output_id) = (next_input(toolbox), next_output(toolbox), next_output(toolbox))
    logger.info('group action a#{} for i#{} to o#{} o#{}, expect event {} -> {}'.format(group_action_id, input_id, output_id, other_output_id, not output_status, output_status))

    actions = ['2', str(group_action_id)]
    input_config = {'id': input_id, 'basic_actions': ','.join(actions), 'action': 240}
    input_config.update(DEFAULT_INPUT_CONFIG)
    toolbox.dut.get('/set_input_configuration', {'config': json.dumps(input_config)})

    actions = ['162', str(output_id), '162', str(other_output_id)]  # toggle both outputs
    config = {'id': group_action_id, 'actions': ','.join(actions)}
    toolbox.dut.get('/set_group_action_configuration', params={'config': json.dumps(config)})

    toolbox.ensure_output(output_id, not output_status, DEFAULT_OUTPUT_CONFIG)
    toolbox.ensure_output(other_output_id, not output_status, DEFAULT_OUTPUT_CONFIG)

    toolbox.press_input(input_id)
    toolbox.assert_output_changed(output_id, output_status)
    toolbox.assert_output_changed(other_output_id, output_status)
