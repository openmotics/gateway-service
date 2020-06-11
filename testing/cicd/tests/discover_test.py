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

import pytest


@pytest.fixture
def discover_mode(request, toolbox):
    try:
        toolbox.module_discover_start()
        yield
    finally:
        toolbox.module_discover_stop()


@pytest.mark.smoke
def test_output_module(toolbox, discover_mode):
    toolbox.tester.toggle_output(toolbox.DEBIAN_DISCOVER_OUTPUT)
    modules = toolbox.assert_modules(1)
    assert ['WARN', 'Existing output module found.'] in modules


@pytest.mark.smoke
def test_input_module(toolbox, discover_mode):
    toolbox.tester.toggle_output(toolbox.DEBIAN_DISCOVER_INPUT)
    modules = toolbox.assert_modules(1)
    assert ['WARN', 'Existing input module found.'] in modules


@pytest.mark.smoke
def test_can_control(toolbox, discover_mode):
    toolbox.tester.toggle_output(toolbox.DEBIAN_DISCOVER_UCAN)
    modules = toolbox.assert_modules(2)
    assert ['WARN', 'Existing CAN control module found.'] in modules
