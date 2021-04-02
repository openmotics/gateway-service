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

"""
Input Mapper
"""
from __future__ import absolute_import
from gateway.dto.input import InputDTO
from gateway.hal.mappers_core.group_action import GroupActionMapper
from master.core.basic_action import BasicAction
from master.core.memory_models import InputConfiguration

if False:  # MYPY
    from typing import List, Dict, Any, Optional, Tuple


class InputMapper(object):
    # Limitations:
    #  * Double press isn't supported on Classic
    #  * Core doesn't support actions after 3, 4, 5 seconds and Classic doesn't support actions after 1 second
    #  * Only simple "single instruction" basic actions are supported

    @staticmethod
    def orm_to_dto(orm_object):  # type: (InputConfiguration) -> InputDTO
        device_type_mapping = {'b': 'I'}  # 'b' is used for CAN-inputs
        action, basic_actions = InputMapper.core_input_configuration_to_classic_actions(orm_object)
        return InputDTO(id=orm_object.id,
                        name=orm_object.name,
                        module_type=device_type_mapping.get(orm_object.module.device_type,
                                                            orm_object.module.device_type),
                        action=action,
                        basic_actions=basic_actions,
                        invert=not orm_object.input_config.normal_open,
                        can=orm_object.module.device_type == 'b')

    @staticmethod
    def dto_to_orm(input_dto):  # type: (InputDTO) -> InputConfiguration
        new_data = {'id': input_dto.id}  # type: Dict[str, Any]
        if 'name' in input_dto.loaded_fields:
            new_data['name'] = input_dto.name
        if 'action' in input_dto.loaded_fields:
            direct_config = input_dto.action is None or input_dto.action == 255 or input_dto.action < 240
            basic_actions_config = input_dto.action in [241, 242] or (input_dto.action == 240 and
                                                                      'basic_actions' in input_dto.loaded_fields)
            if direct_config or basic_actions_config:
                new_data.update(InputMapper.classic_actions_to_core_input_configuration(input_dto.action,
                                                                                        input_dto.basic_actions))
        if 'invert' in input_dto.loaded_fields:
            new_data['input_config'] = {'normal_open': not input_dto.invert}
        return InputConfiguration.deserialize(new_data)

    @staticmethod
    def core_input_configuration_to_classic_actions(orm_object):
        # type: (InputConfiguration) -> Tuple[int, List[int]]
        if not orm_object.in_use:
            return 255, []
        if orm_object.has_direct_output_link:
            # No specific actions; this Input is directly linked to an Output
            return orm_object.input_link.output_id, []
        if orm_object.input_link.enable_press_and_release:
            # Press/release actions are enabled
            basic_actions = []
            if orm_object.basic_action_press.in_use:
                basic_actions += GroupActionMapper.core_actions_to_classic_actions([orm_object.basic_action_press])
                if len(basic_actions) == 2 and basic_actions[0] in [163, 164]:
                    return 242 if basic_actions[0] == 163 else 241, []
            if orm_object.basic_action_release.in_use:
                if not orm_object.basic_action_release.is_execute_group_action:
                    raise ValueError('Actions are limited to executing GroupActions')
                basic_actions += [236, 0, 2, orm_object.basic_action_release.device_nr, 236, 255]
            return 240, basic_actions
        # Timing-related presses are used
        if orm_object.input_link.enable_2s_press:
            if not orm_object.basic_action_2s_press.is_execute_group_action:
                raise ValueError('Actions are limited to executing GroupActions')
            return 240, [207, orm_object.basic_action_2s_press.device_nr]
        else:
            raise ValueError('Only 2s presses can be translated')
        raise ValueError('The current configuration cannot be translated')

    @staticmethod
    def classic_actions_to_core_input_configuration(action, basic_actions):
        # type: (Optional[int], List[int]) -> Dict[str, Any]

        # Default data
        data = {'input_link': {'output_id': 1023,
                               'dimming_up': True,
                               'enable_press_and_release': True,
                               'enable_1s_press': True,
                               'enable_2s_press': True,
                               'not_used': True,
                               'enable_double_press': True},
                'basic_action_press': BasicAction.empty(),
                'basic_action_release': BasicAction.empty(),
                'basic_action_1s_press': BasicAction.empty(),
                'basic_action_2s_press': BasicAction.empty(),
                'basic_action_double_press': BasicAction.empty()}  # type: Dict[str, Any]

        # Disabled input
        if action is None or action == 255:
            return data

        # Change default data
        data['input_link'].update({'dimming_up': False,
                                   'enable_press_and_release': False,
                                   'enable_1s_press': False,
                                   'enable_2s_press': False,
                                   'not_used': False,
                                   'enable_double_press': False})

        # If theaction is < 240, it means that the input directly controls an output
        if action < 240:
            data['input_link']['output_id'] = action
            return data

        # If the action is 241 or 242
        if action in [241, 242]:
            data['input_link']['enable_press_and_release'] = True
            data['basic_action_press'] = BasicAction(action_type=0, action=255,
                                                     device_nr=2 if action == 241 else 1)
            return data

        # Otherwise, it means that the input is supposed to execute a list of basic actions
        # but this is not supported anymore on the Core.
        # TODO: Convert any list of actions to one or more group actions and use these instead

        action_types = set(basic_actions[i] for i in range(0, len(basic_actions), 2))

        # Delayed action(s)
        if 207 in action_types:
            if len(basic_actions) != 2:
                raise ValueError('Timing settings cannot be combined with other actions')
            data['input_link']['enable_2s_press'] = True
            data['basic_action_2s_press'] = BasicAction(action_type=19, action=0,
                                                        device_nr=basic_actions[1])
            return data

        # Possible single on-press actions
        if action_types - {2, 236}:
            actions = GroupActionMapper.classic_actions_to_core_actions(basic_actions)
            if len(actions) != 1:
                raise ValueError('Only simple input configrations are supported')
            data['input_link']['enable_press_and_release'] = True
            data['basic_action_press'] = actions[0]
            return data

        # Press/release actions
        release_data = False
        release_action = None  # type: Optional[int]
        press_action = None  # type: Optional[int]
        for i in range(0, len(basic_actions), 2):
            action_type = basic_actions[i]
            action_number = basic_actions[i + 1]
            if action_type == 236:
                release_data = action_number == 0
            elif release_data:
                release_action = action_number
            else:
                press_action = action_number
        if press_action is not None:
            data['input_link']['enable_press_and_release'] = True
            data['basic_action_press'] = BasicAction(action_type=19, action=0, device_nr=press_action)
        if release_action is not None:
            data['input_link']['enable_press_and_release'] = True
            data['basic_action_release'] = BasicAction(action_type=19, action=0, device_nr=release_action)
        return data
