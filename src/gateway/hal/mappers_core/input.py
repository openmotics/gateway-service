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
from enums import HardwareType

if False:  # MYPY
    from typing import List, Dict, Any, Optional, Tuple


class InputMapper(object):
    # Limitations:
    #  * Double press isn't supported on Classic
    #  * Core doesn't support actions after 3, 4, 5 seconds and Classic doesn't support actions after 1 second
    #  * Only simple "single instruction" basic actions are supported

    @staticmethod
    def orm_to_dto(orm_object):  # type: (InputConfiguration) -> InputDTO
        module_type = orm_object.module.device_type
        if orm_object.module.hardware_type == HardwareType.EMULATED:
            module_type = 'I'  # Emulated inputs are returned as physical/real
        elif orm_object.module.hardware_type == HardwareType.INTERNAL:
            module_type = 'I'  # Internal inputs are returned as physical/real
        action, basic_actions = InputMapper.core_input_configuration_to_classic_actions(orm_object)
        return InputDTO(id=orm_object.id,
                        name=orm_object.name,
                        module_type=module_type,
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
        if orm_object.input_link.enable_press_and_release or orm_object.input_link.enable_2s_press:
            basic_actions = []  # type: List[int]
            if orm_object.input_link.enable_press_and_release:
                if orm_object.basic_action_press.in_use:
                    _, actions = GroupActionMapper.core_actions_to_classic_actions([orm_object.basic_action_press])
                    basic_actions += actions
                    if len(basic_actions) == 2 and basic_actions[0] in [163, 164]:
                        return 242 if basic_actions[0] == 163 else 241, []
                if orm_object.basic_action_release.is_execute_group_action:
                    basic_actions += [236, 0, 2, orm_object.basic_action_release.device_nr, 236, 255]
            if orm_object.input_link.enable_2s_press:
                if orm_object.basic_action_2s_press.is_execute_group_action:
                    basic_actions = [207, orm_object.basic_action_2s_press.device_nr] + basic_actions
            if basic_actions:
                return 240, basic_actions
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

        # The input is configured, changing defaults
        data['input_link'].update({'dimming_up': False,
                                   'enable_press_and_release': False,
                                   'enable_1s_press': False,
                                   'enable_2s_press': False,
                                   'not_used': False,
                                   'enable_double_press': False})

        # If the action is < 240, it means that the input directly controls an output
        if action < 240:
            data['input_link']['output_id'] = action
            return data

        # Process special actions 241 and 242:
        # * 241 = Turn off all lights + outputs
        # * 242 = Turn off all lights
        if action in [241, 242]:
            data['input_link']['enable_press_and_release'] = True
            data['basic_action_press'] = BasicAction(action_type=0, action=255,
                                                     device_nr=2 if action == 241 else 1)
            return data

        # The input is configured as "execute a list of basic actions" which is not supported
        # on the Core. This means that below code will do a best-effort to translate the configured
        # actions into something that is supported by the Core input configurations.
        # TODO: Convert any list of actions to one or more group actions and use these instead

        # Process single "execute group action" scenarios
        # * 2 = Execute group action
        # * 207 = Execute group action when pressed more than 2s
        if len(basic_actions) == 2 and basic_actions[0] in [2, 207]:
            if basic_actions[0] == 2:
                enabled_link = 'enable_press_and_release'
                press_action = 'basic_action_press'
            else:
                enabled_link = 'enable_2s_press'
                press_action = 'basic_action_2s_press'
            data['input_link'][enabled_link] = True
            data[press_action] = BasicAction(action_type=19, action=0, device_nr=basic_actions[1])
            return data

        # Process scenario where (long and/or short) press and release are configured.
        # Sequences:
        # * 207, _, 236, 0, 2, _, 236, 255 (on long press + on release)
        # * 2, _, 236, 0, 2, _, 236, 255 (on press + on release)
        # * 236, 0, 2, _, 236, 255 (only on release)
        if len(basic_actions) in [6, 8]:
            release_reference = [basic_actions[i] for i in [-6, -5, -4, -2, -1]]
            if release_reference != [236, 0, 2, 236, 255]:
                raise ValueError('Unsupported action sequence: {0}'.format(basic_actions))
            data['input_link']['enable_press_and_release'] = True
            data['basic_action_release'] = BasicAction(action_type=19, action=0, device_nr=basic_actions[-3])
            if len(basic_actions) == 8:
                if basic_actions[0] not in [2, 207]:
                    raise ValueError('Unsupported action sequence: {0}'.format(basic_actions))
                if basic_actions[0] == 2:
                    data['basic_action_press'] = BasicAction(action_type=19, action=0, device_nr=basic_actions[1])
                else:
                    data['input_link']['enable_2s_press'] = True
                    data['basic_action_2s_press'] = BasicAction(action_type=19, action=0, device_nr=basic_actions[1])
            return data

        # Process whatever is left if it's translatable to a single-press action
        actions = GroupActionMapper.classic_actions_to_core_actions(basic_actions)
        if len(actions) != 1:
            raise ValueError('Only simple input configuration are supported')
        data['input_link']['enable_press_and_release'] = True
        data['basic_action_press'] = actions[0]
        return data
