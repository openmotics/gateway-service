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

import unittest
from ioc import SetTestMode
from gateway.hal.mappers_core import GroupActionMapper
from master.core.basic_action import BasicAction
from mocked_core_helper import MockedCore


class GroupActionCoreMapperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.mocked_core = MockedCore()

    def test_mappings(self):
        normal_scenarios = [([160, 5], [(0, 0, 5)]),  # Turn output 5 off
                             ([161, 5], [(0, 1, 5)]),  # Turn output 5 on
                             ([162, 5], [(0, 16, 5)]),  # Toggle output 5
                             ([240, 0, 243, 5, 240, 255], [(100, 0), (100, 10, 5), (100, 255)]),  # If output 5 is on
                             ([240, 0, 247, 5, 249, 10, 240, 255], [(100, 0), (100, 19, 5, 10), (100, 255)]),  # If temp sensor 5 > 10
                             ([240, 0, 247, 37, 248, 10, 240, 255], [(100, 0), (100, 23, 5, 10), (100, 255)]),  # If hum sensor 5 == 10
                             ([240, 0, 247, 69, 250, 10, 240, 255], [(100, 0), (100, 27, 5, 10), (100, 255)]),  # If brightness sensor 5 < 10
                             ([240, 0, 247, 228, 249, 10, 240, 255], [(100, 0), (100, 40, 10), (100, 255)]),  # If hour > 10
                             ([240, 0, 247, 229, 248, 10, 240, 255], [(100, 0), (100, 44, 10), (100, 255)]),  # If minutes == 10
                             ([240, 0, 247, 230, 250, 3, 240, 255], [(100, 0), (100, 48, 3), (100, 255)]),  # If day < 3
                             ([171, 5], [(251, 0, 5, 0)]),  # Turn off all lights on floor 5
                             ([172, 5], [(251, 0, 5, 1)]),  # Turn on all lights on floor 5
                             ([173, 5], [(251, 0, 5, 2)]),   # Toggle all lights on floor 5
                             ([171, 255], [(251, 0, 65535, 0)]),  # Turn off all lights (on all floors)
                             ([172, 255], [(251, 0, 65535, 1)]),  # Turn on all lights (on all floors)
                             ([173, 255], [(251, 0, 65535, 2)])]  # Toggle all lights (on all floors)
        incompatible_scenarios = [([255, 255], [], (True, [])),  # Classic actions that are not supported on the Core
                                  (None, [(255, 255)], (False, []))]  # Core actions that are not supported on the Classic
        for scenario in normal_scenarios + incompatible_scenarios:
            classic_scenario = scenario[0]
            core_scenario = scenario[1]
            if len(scenario) == 3:
                complete_expected, classic_expected = scenario[2]
            else:
                complete_expected = True
                classic_expected = classic_scenario
            core_expected = [BasicAction(*entry) for entry in core_scenario]
            if classic_scenario is not None:
                core_result = GroupActionMapper.classic_actions_to_core_actions(classic_scenario)
                self.assertEqual(core_expected, core_result)
            complete_result, classic_result = GroupActionMapper.core_actions_to_classic_actions(core_expected)
            self.assertEqual(classic_expected, classic_result)
            self.assertEqual(complete_expected, complete_result)
