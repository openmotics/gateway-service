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
import ujson as json
from hypothesis.strategies import booleans
from pytest import fixture, mark

from tests.hardware_layout import INPUT_MODULE_LAYOUT, OUTPUT_MODULE_LAYOUT, Output, Module

logger = logging.getLogger('openmotics')


VIRTUAL_MODULES = 10
DEFAULT_INPUT_CONFIG = {'invert': 255}


@fixture(scope='session')
def add_virtual_modules(request, toolbox_session):
    toolbox = toolbox_session

    data = toolbox.dut.get('/get_modules')
    virtual_outputs = VIRTUAL_MODULES - sum(1 for x in data['outputs'] if x == 'o')
    virtual_inputs = VIRTUAL_MODULES - sum(1 for x in data['inputs'] if x == 'i')

    module_amounts = {'o': max(virtual_outputs, 0), 'i': max(virtual_inputs, 0)}
    logger.info('adding extra virtual modules %s', module_amounts)
    toolbox.add_virtual_modules(module_amounts=module_amounts)
    time.sleep(10)

    virtual_module = Module(name='virtual module', mtype='o')
    statuses = toolbox.dut.get('/get_output_status')['status']
    max_id = max(x['id'] for x in statuses)
    if next(x['status'] == 0 for x in statuses if x['id'] == max_id):
        logger.info('setting all outputs to on')
        for status in statuses:
            if status['status'] == 0:
                output = Output(output_id=status['id'], module=virtual_module)
                toolbox.set_output(output, True)
    time.sleep(10)


@mark.unstable
@hypothesis.given(booleans())
def test_master_events(toolbox, add_virtual_modules, _status):
    _ = add_virtual_modules
    inputs = []
    for module in INPUT_MODULE_LAYOUT:
        inputs += module.inputs
    outputs = []
    for module in OUTPUT_MODULE_LAYOUT:
        outputs += module.outputs
    for (_input, output) in zip(inputs, outputs):
        input_config = {'id': _input.input_id, 'action': output.output_id}
        input_config.update(DEFAULT_INPUT_CONFIG)
        toolbox.dut.get('/set_input_configuration', {'config': json.dumps(input_config)})
    time.sleep(10)

    for _ in range(32):
        for _input in inputs:
            toolbox.press_input(_input)
