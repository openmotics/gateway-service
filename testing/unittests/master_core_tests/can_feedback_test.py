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
"""
Tests for CAN feedback
"""

from __future__ import absolute_import
import unittest
from ioc import SetTestMode
from gateway.dto import OutputDTO, FeedbackLedDTO, GlobalFeedbackDTO
from master.core.can_feedback import CANFeedbackController
from master.core.basic_action import BasicAction
from master.core.group_action import GroupActionController
from master.core.memory_models import OutputConfiguration, GlobalConfiguration
from mocked_core_helper import MockedCore


class CANFeedbackTest(unittest.TestCase):
    """ Tests for CAN feedback """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.mocked_core = MockedCore()

    def test_individual_feedback_leds(self):
        output = OutputConfiguration.deserialize({'id': 0})
        # Setup basic LED feedback
        output_dto = OutputDTO(id=0,
                               can_led_1=FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                               can_led_3=FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.MB_B8_INVERTED))

        # Save led feedback config
        CANFeedbackController.save_output_led_feedback_configuration(output, output_dto, ['can_led_1', 'can_led_3'])

        # Validate correct data in created GA
        self.assertEqual(0, output.output_groupaction_follow)
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual([BasicAction(action_type=19, action=2, device_nr=0),
                          BasicAction(action_type=20, action=50, device_nr=5, extra_parameter=65280),
                          BasicAction(action_type=20, action=51, device_nr=7, extra_parameter=32514)], group_action.actions)
        self.assertEqual('Output 0', group_action.name)

        # Alter GA
        extra_bas = [BasicAction(action_type=123, action=123),  # Some random BA
                     BasicAction(action_type=19, action=2, device_nr=1),  # Another batch of feedback statements for another Output
                     BasicAction(action_type=20, action=50, device_nr=15),
                     BasicAction(action_type=20, action=51, device_nr=17)]
        group_action.actions += extra_bas
        group_action.name = 'Foobar'
        GroupActionController.save_group_action(group_action, ['name', 'actions'])

        # Validate loading data
        output_dto = OutputDTO(id=0)
        CANFeedbackController.load_output_led_feedback_configuration(output, output_dto)
        self.assertEqual(FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL), output_dto.can_led_1)
        self.assertEqual(FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.MB_B8_INVERTED), output_dto.can_led_2)  # Moved to 2

        # Change led feedback config
        output_dto.can_led_2.function = FeedbackLedDTO.Functions.ON_B8_INVERTED
        CANFeedbackController.save_output_led_feedback_configuration(output, output_dto, ['can_led_1', 'can_led_2'])

        # Validate stored led feedback data
        output_dto = OutputDTO(id=0)
        CANFeedbackController.load_output_led_feedback_configuration(output, output_dto)
        self.assertEqual(FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL), output_dto.can_led_1)
        self.assertEqual(FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.ON_B8_INVERTED), output_dto.can_led_2)

        # Validate GA changes
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(extra_bas + [BasicAction(action_type=19, action=2, device_nr=0),
                                      BasicAction(action_type=20, action=50, device_nr=5, extra_parameter=65280),
                                      BasicAction(action_type=20, action=51, device_nr=7, extra_parameter=32512)],
                         group_action.actions)
        self.assertEqual('Foobar', group_action.name)

    def test_global_feedback_leds(self):
        global_configuration = GlobalConfiguration()
        all_default_global_feedbacks = [GlobalFeedbackDTO(id=i) for i in range(32)]

        # Verify base
        self.assertEqual(65535, global_configuration.groupaction_any_output_changed)
        self.assertEqual({}, CANFeedbackController.load_global_led_feedback_configuration())

        # Store feedback "0" (nr of lights == 0)
        global_feedback_0 = GlobalFeedbackDTO(id=0,
                                              can_led_1=FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                              can_led_3=FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.ON_B8_INVERTED),
                                              can_led_4=FeedbackLedDTO(id=9, function=FeedbackLedDTO.Functions.FB_B8_NORMAL))
        CANFeedbackController.save_global_led_feedback_configuration([(global_feedback_0, ['can_led_1', 'can_led_3', 'can_led_4'])])

        #                                                                                                 +- 256 = MSB is 1 = lights
        # Validate                                                                                        |   +- 0 = Solid on, 1 = Fast blinking
        expected_basic_actions_0 = [BasicAction(action_type=20, action=73, device_nr=5, extra_parameter=256 + 0),
                                    BasicAction(action_type=20, action=73, device_nr=7, extra_parameter=256 + 0),
                                    BasicAction(action_type=20, action=73, device_nr=9, extra_parameter=256 + 1)]
        expected_global_feedback_0 = GlobalFeedbackDTO(id=0,
                                                       can_led_1=FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                                       can_led_2=FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                                       can_led_3=FeedbackLedDTO(id=9, function=FeedbackLedDTO.Functions.FB_B16_NORMAL))
        global_configuration = GlobalConfiguration()
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(0, global_configuration.groupaction_any_output_changed)
        self.assertEqual('Global feedback', group_action.name)
        self.assertEqual(expected_basic_actions_0, group_action.actions)
        self.assertEqual({0: expected_global_feedback_0}, CANFeedbackController.load_global_led_feedback_configuration())

        # Prepare feedback "3" (nr of lights > 2)
        global_feedback_3 = GlobalFeedbackDTO(id=3,
                                              can_led_1=FeedbackLedDTO(id=11, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                              can_led_3=FeedbackLedDTO(id=13, function=FeedbackLedDTO.Functions.FB_B8_INVERTED),
                                              can_led_4=FeedbackLedDTO(id=15, function=FeedbackLedDTO.Functions.ON_B8_INVERTED))
        expected_global_feedback_3 = GlobalFeedbackDTO(id=3,
                                                       can_led_1=FeedbackLedDTO(id=11, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                                       can_led_2=FeedbackLedDTO(id=13, function=FeedbackLedDTO.Functions.FB_B16_NORMAL))
        expected_basic_actions_3 = [BasicAction(action_type=20, action=71, device_nr=11, extra_parameter=512 + 0),
                                    BasicAction(action_type=20, action=71, device_nr=13, extra_parameter=512 + 1)]
        #                                                                                                |   +- 0 = Solid on, 1 = Fast blinking
        #                                                                                                +- 512 = MSB is 2 = nr of lights

        # Store in various scenarios, all should yield the same response
        save_scenarios = [[(global_feedback_3, ['can_led_1', 'can_led_3'])],
                          [(global_feedback_0, ['can_led_1', 'can_led_3', 'can_led_4']), (global_feedback_3, ['can_led_1', 'can_led_3'])]]
        for save_scenario in save_scenarios:
            CANFeedbackController.save_global_led_feedback_configuration(save_scenario)

            global_configuration = GlobalConfiguration()
            group_action = GroupActionController.load_group_action(0)
            self.assertEqual(0, global_configuration.groupaction_any_output_changed)
            self.assertEqual(expected_basic_actions_0 + expected_basic_actions_3, group_action.actions)
            self.assertEqual({0: expected_global_feedback_0,
                              3: expected_global_feedback_3}, CANFeedbackController.load_global_led_feedback_configuration())

        # Add extra BA that should not be removed by altering global feedback
        extra_basic_actions = [BasicAction(action_type=123, action=123)]
        group_action.actions += extra_basic_actions
        group_action.name = 'Foobar'
        GroupActionController.save_group_action(group_action, ['name', 'actions'])

        # Save without scenario (will re-save data, but should not alter)
        CANFeedbackController.save_global_led_feedback_configuration([])
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual('Foobar', group_action.name)
        self.assertEqual(expected_basic_actions_0 + expected_basic_actions_3 + extra_basic_actions, group_action.actions)

        # Save full scenario (will remove feedback BAs and save them again at the end of the GA)
        CANFeedbackController.save_global_led_feedback_configuration(save_scenarios[1])
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual('Foobar', group_action.name)
        self.assertEqual(extra_basic_actions + expected_basic_actions_0 + expected_basic_actions_3, group_action.actions)

        # Prepare feedbacks "16" (nr of outputs == 0) and "20" (nr of outputs > 3)
        global_feedback_16 = GlobalFeedbackDTO(id=16, can_led_1=FeedbackLedDTO(id=15, function=FeedbackLedDTO.Functions.ON_B16_NORMAL))
        global_feedback_20 = GlobalFeedbackDTO(id=20, can_led_1=FeedbackLedDTO(id=17, function=FeedbackLedDTO.Functions.ON_B16_NORMAL))
        expected_global_feedback_16 = GlobalFeedbackDTO(id=16, can_led_1=FeedbackLedDTO(id=15, function=FeedbackLedDTO.Functions.ON_B16_NORMAL))
        expected_global_feedback_20 = GlobalFeedbackDTO(id=20, can_led_1=FeedbackLedDTO(id=17, function=FeedbackLedDTO.Functions.ON_B16_NORMAL))
        expected_basic_actions_16 = [BasicAction(action_type=20, action=73, device_nr=15, extra_parameter=0 + 0)]  # 0 = MSB is 0 = outputs
        expected_basic_actions_20 = [BasicAction(action_type=20, action=70, device_nr=17, extra_parameter=768 + 0)]  # 768 = MSB is 3 = nr of outputs

        # Store
        CANFeedbackController.save_global_led_feedback_configuration([(global_feedback_0, ['can_led_1', 'can_led_3', 'can_led_4']),
                                                                      (global_feedback_3, ['can_led_1', 'can_led_3']),
                                                                      (global_feedback_16, ['can_led_1']),
                                                                      (global_feedback_20, ['can_led_1'])])

        # Validate
        global_configuration = GlobalConfiguration()
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(0, global_configuration.groupaction_any_output_changed)
        self.assertEqual(extra_basic_actions +
                         expected_basic_actions_0 +
                         expected_basic_actions_3 +
                         expected_basic_actions_16 +
                         expected_basic_actions_20, group_action.actions)
        self.assertEqual({0: expected_global_feedback_0,
                          3: expected_global_feedback_3,
                          16: expected_global_feedback_16,
                          20: expected_global_feedback_20}, CANFeedbackController.load_global_led_feedback_configuration())

        # Remove 3
        empty_global_feedback_3 = GlobalFeedbackDTO(id=3)
        CANFeedbackController.save_global_led_feedback_configuration([(empty_global_feedback_3, ['can_led_1', 'can_led_2']),
                                                                      (global_feedback_20, ['can_led_1'])])

        # Validate
        global_configuration = GlobalConfiguration()
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(0, global_configuration.groupaction_any_output_changed)
        self.assertEqual(extra_basic_actions +
                         expected_basic_actions_0 +
                         expected_basic_actions_16 +
                         expected_basic_actions_20, group_action.actions)
        self.assertEqual({0: expected_global_feedback_0,
                          16: expected_global_feedback_16,
                          20: expected_global_feedback_20}, CANFeedbackController.load_global_led_feedback_configuration())
