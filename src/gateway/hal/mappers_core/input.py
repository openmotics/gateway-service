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
from master.core.basic_action import BasicAction
from master.core.memory_models import InputConfiguration

if False:  # MYPY
    from typing import List, Dict, Any, Optional, Tuple


class InputMapper(object):
    # Limitations:
    #  * Double press isn't supported on Classic
    #  * Core doesn't support actions after 3, 4, 5 seconds and Classic doesn't support actions after 1 second
    #  * Currently no "basic actions" are supported except for long-press action types and "execute group action"

    @staticmethod
    def orm_to_dto(orm_object):  # type: (InputConfiguration) -> InputDTO
        device_type_mapping = {'b': 'O'}  # 'b' is used for CAN-inputs
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
    def dto_to_orm(input_dto, fields):  # type: (InputDTO, List[str]) -> InputConfiguration
        new_data = {'id': input_dto.id}  # type: Dict[str, Any]
        if 'name' in fields:
            new_data['name'] = input_dto.name
        if 'action' in fields and 'basic_actions' in fields:
            new_data.update(InputMapper.classic_actions_to_core_input_configuration(input_dto.action,
                                                                                    input_dto.basic_actions))
        if 'invert' in fields:
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
                if not orm_object.basic_action_press.is_execute_group_action:
                    raise ValueError('Actions are limited to executing GroupActions')
                basic_actions += [2, orm_object.basic_action_press.device_nr]
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
        raise ValueError('Only 2s presses are supported')

    @staticmethod
    def classic_actions_to_core_input_configuration(action, basic_actions):
        # type: (Optional[int], List[int]) -> Dict[str, Any]
        data = {'input_link': {'output_id': 1023,
                               'enable_press_and_release': True,
                               'enable_1s_press': True,
                               'enable_2s_press': True,
                               'enable_double_press': True}}  # type: Dict[str, Any]
        if action is None or action == 255:
            return data
        data['input_link'].update({'enable_press_and_release': False,
                                   'enable_1s_press': False,
                                   'enable_2s_press': False,
                                   'enable_double_press': False})
        if action < 240:
            data['input_link']['output_id'] = action
            return data
        action_types = set(basic_actions[i] for i in range(0, len(basic_actions), 2))
        if 207 in action_types:
            if len(basic_actions) != 2:
                raise ValueError('Timing settings cannot be combined with other actions')
            data['input_link']['enable_2s_press'] = True
            data['basic_action_2s_press'] = BasicAction(action_type=19, action=0,
                                                        device_nr=basic_actions[1])
            return data
        if action_types - {2, 236}:
            raise ValueError('Only executing GroupActions is supported')
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
