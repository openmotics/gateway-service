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
Contains uCAN feedback related code
"""

from __future__ import absolute_import
import logging
from gateway.dto import FeedbackLedDTO, GlobalFeedbackDTO
from master.core.group_action import GroupActionController
from master.core.basic_action import BasicAction
from master.core.memory_types import MemoryActivator
from master.core.memory_models import GlobalConfiguration

if False:  # MYPY
    from typing import List, Optional, Dict, Tuple, Union
    from master.core.memory_models import OutputConfiguration
    from master.core.group_action import GroupAction
    from gateway.dto import OutputDTO

logger = logging.getLogger(__name__)


class CANFeedbackController(object):
    WORD_MAX = 2 ** 16 - 1
    FIELDS = ['can_led_1', 'can_led_2', 'can_led_3', 'can_led_4']

    @staticmethod
    def load_output_led_feedback_configuration(output, output_dto):
        # type: (OutputConfiguration, OutputDTO) -> None
        if output.output_groupaction_follow > 255:
            output_dto.can_led_1 = FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
            output_dto.can_led_2 = FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
            output_dto.can_led_3 = FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
            output_dto.can_led_4 = FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
            return
        group_action = GroupActionController.load_group_action(output.output_groupaction_follow)
        led_counter = 1
        for basic_action in group_action.actions:
            if basic_action.action_type == 20 and basic_action.action in [50, 51]:
                brightness = CANFeedbackController._byte_to_brightness_string(basic_action.extra_parameter_msb)
                blinking = CANFeedbackController._byte_to_blinking_string(basic_action.extra_parameter_lsb)
                inverted = CANFeedbackController._action_to_inverted_string(basic_action.action)
                function = '{0} {1}{2}'.format(blinking, brightness, inverted)
                setattr(output_dto, 'can_led_{0}'.format(led_counter), FeedbackLedDTO(id=basic_action.device_nr,
                                                                                      function=function))
                led_counter += 1
                if led_counter > 4:
                    break

    @staticmethod
    def save_output_led_feedback_configuration(output, output_dto, fields, activate=True):
        # type: (OutputConfiguration, OutputDTO, List[str], bool) -> None
        holds_data, holds_configuration = CANFeedbackController._available_led_data(output_dto, fields)
        if not holds_data:
            return  # No change required
        group_action_id = output.output_groupaction_follow
        group_action = None  # type: Optional[GroupAction]  # Needed for keeping Mypy happy...
        if group_action_id <= 255:
            group_action = GroupActionController.load_group_action(group_action_id)
            for basic_action in group_action.actions[:]:
                if basic_action.action_type == 20 and basic_action.action in [50, 51]:
                    group_action.actions.remove(basic_action)
        else:
            if not holds_configuration:
                return  # No GroupAction configured, and no configurion. Nothing to do.
            group_action = GroupActionController.get_unused_group_action()
            if group_action is None:
                raise ValueError('No GroupAction available to store LED feedback configuration')
        for field in CANFeedbackController.FIELDS:
            feedback_led_dto = getattr(output_dto, field)
            if field in fields and feedback_led_dto.id is not None:
                action = CANFeedbackController._inverted_string_to_action(feedback_led_dto.function)
                basic_action = BasicAction(action_type=20,
                                           action=action,
                                           device_nr=feedback_led_dto.id)
                basic_action.extra_parameter_lsb = CANFeedbackController._blinking_string_to_byte(feedback_led_dto.function)
                basic_action.extra_parameter_msb = CANFeedbackController._brightness_string_to_byte(feedback_led_dto.function)
                group_action.actions.append(basic_action)
        if group_action.actions:
            if group_action.name == '':
                group_action.name = 'Output {0}'.format(output.id)
            output.output_groupaction_follow = group_action.id
        else:
            group_action.name = ''
            output.output_groupaction_follow = CANFeedbackController.WORD_MAX
        output.save(activate=False)
        GroupActionController.save_group_action(group_action, ['name', 'actions'], activate=False)
        if activate:
            MemoryActivator.activate()

    @staticmethod
    def load_global_led_feedback_configuration():  # type: () -> Dict[int, GlobalFeedbackDTO]
        global_feedbacks = {}  # type: Dict[int, GlobalFeedbackDTO]
        global_feedback_led_counter = {}
        global_configuration = GlobalConfiguration()
        if global_configuration.groupaction_any_output_changed > 255:
            return global_feedbacks
        group_action = GroupActionController.load_group_action(global_configuration.groupaction_any_output_changed)
        for basic_action in group_action.actions:
            if basic_action.action_type != 20 or basic_action.action not in [70, 71, 73]:  # 70 = # outputs, 71 = # lights, 72 = # outputs + lights
                continue
            # For the calculation of this `global_feedback_id`, see `master.classic.eeprom_models.CanLedConfiguration` docstring
            if basic_action.action == 73:
                # 73 is the "zero-case": extra_parametery.msb = 0 -> # outputs,
                #                        extra_parametery.msb = 1 -> # lights,
                #                        extra_parametery.msb = 2 -> # outputs + lights
                appliance_type = basic_action.extra_parameter_msb
                if appliance_type not in [0, 1]:
                    continue  # Unsupported
                global_feedback_id = 0 if appliance_type == 1 else 16
            else:
                nr_of_appliances = basic_action.extra_parameter_msb
                if nr_of_appliances > 14:
                    continue  # Unsupported
                global_feedback_id = nr_of_appliances + 1 + (0 if basic_action.action == 71 else 16)
            if global_feedback_id not in global_feedbacks:
                global_feedbacks[global_feedback_id] = GlobalFeedbackDTO(id=global_feedback_id)
                global_feedback_led_counter[global_feedback_id] = 1
            global_feedback_dto = global_feedbacks[global_feedback_id]
            led_counter = global_feedback_led_counter[global_feedback_id]
            if led_counter > 4:
                continue  # No space remaining
            blinking = CANFeedbackController._byte_to_blinking_string(basic_action.extra_parameter_lsb)
            function = '{0} B16'.format(blinking)
            setattr(global_feedback_dto, 'can_led_{0}'.format(led_counter), FeedbackLedDTO(id=basic_action.device_nr,
                                                                                           function=function))
            led_counter += 1
            global_feedbacks[global_feedback_id] = global_feedback_dto
            global_feedback_led_counter[global_feedback_id] = led_counter
        return global_feedbacks

    @staticmethod
    def save_global_led_feedback_configuration(global_feedbacks, activate=True):  # type: (List[Tuple[GlobalFeedbackDTO, List[str]]], bool) -> None
        # Important assumption in the below code to make this strategy solvable: If any of the 4 feedbacks is
        # given, they all are assumed to be given.
        global_configuration = GlobalConfiguration()
        if global_configuration.groupaction_any_output_changed > 255:
            group_action = GroupActionController.get_unused_group_action()
            if group_action is None:
                raise ValueError('No GroupAction available to store LED feedback configuration')
        else:
            group_action = GroupActionController.load_group_action(global_configuration.groupaction_any_output_changed)

        for global_feedback_dto, fields in global_feedbacks:
            holds_data, holds_configuration = CANFeedbackController._available_led_data(global_feedback_dto, fields)
            if not holds_data:
                continue  # No change required
            # First, delete everything related to this global_feedback_dto
            if global_feedback_dto.id in [0, 16]:
                action = 73
                extra_parametery_msb = 0 if global_feedback_dto.id == 16 else 1
            else:
                action = 71 if 0 < global_feedback_dto.id < 16 else 70
                extra_parametery_msb = global_feedback_dto.id - (1 if global_feedback_dto.id < 16 else 17)
            for basic_action in group_action.actions[:]:
                if basic_action.action_type == 20 and basic_action.action == action:
                    if basic_action.extra_parameter_msb == extra_parametery_msb:
                        group_action.actions.remove(basic_action)
            # Then, add the relevant entries back again
            if holds_configuration:
                for field in CANFeedbackController.FIELDS:
                    feedback_led_dto = getattr(global_feedback_dto, field)
                    if field in fields and feedback_led_dto.id is not None:
                        basic_action = BasicAction(action_type=20,
                                                   action=action,
                                                   device_nr=feedback_led_dto.id)
                        basic_action.extra_parameter_msb = extra_parametery_msb
                        basic_action.extra_parameter_lsb = CANFeedbackController._blinking_string_to_byte(feedback_led_dto.function)
                        group_action.actions.append(basic_action)
        # Save changes
        if group_action.actions:
            if group_action.name == '':
                group_action.name = 'Global feedback'
            global_configuration.groupaction_any_output_changed = group_action.id
        else:
            group_action.name = ''
            global_configuration.groupaction_any_output_changed = CANFeedbackController.WORD_MAX
        global_configuration.save(activate=False)
        GroupActionController.save_group_action(group_action, ['name', 'actions'], activate=False)
        if activate:
            MemoryActivator.activate()

    @staticmethod
    def _available_led_data(dto, fields):  # type: (Union[OutputDTO, GlobalFeedbackDTO], List[str]) -> Tuple[bool, bool]
        holds_data = any(field in fields for field in CANFeedbackController.FIELDS)
        holds_configuration = any(getattr(dto, field).id is not None for field in CANFeedbackController.FIELDS)
        return holds_data, holds_configuration

    @staticmethod
    def _byte_to_blinking_string(value):  # type: (int) -> str
        return {0: 'On',
                1: 'Fast blink',
                2: 'Medium blink',
                3: 'Slow blink',
                4: 'Swinging'}.get(value, 'On')

    @staticmethod
    def _blinking_string_to_byte(function):  # type: (str) -> int
        function = function.lower()
        for speed, value in {'fast': 1, 'medium': 2, 'slow': 4, 'swinging': 4}.items():
            if speed in function:
                return value
        return 0

    @staticmethod
    def _byte_to_brightness_string(value):  # type: (int) -> str
        return 'B{0}'.format(value // 16 + 1)

    @staticmethod
    def _brightness_string_to_byte(function):  # type: (str) -> int
        function = function.lower()
        brightness = 16
        for level in range(16, 0, -1):  # Reverse, as otherwise e.g. B15 would als be mached by B1
            if 'b{0}'.format(level) in function:
                brightness = level
                break
        return int(brightness / 16.0 * 255)

    @staticmethod
    def _action_to_inverted_string(action):
        return '' if action == 50 else ' Inverted'

    @staticmethod
    def _inverted_string_to_action(function):  # type: (str) -> int
        function = function.lower()
        return 51 if 'inverted' in function else 50
