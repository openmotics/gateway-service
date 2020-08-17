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
from gateway.hal.mappers_core.group_action import GroupActionMapper

if False:  # MYPY
    from typing import List, Dict, Any, Optional, Tuple


class InputMapper(object):
    # TODO and current issues:
    #  * Double press isn't supported on Classic. Ignore those settings translating back and forth?
    #  * On Classic, press/release actions can be inside the input configuration, on Core they are a separate GroupActions. How to solve?
    #  * Core doesn't support actions after 3, 4, 5 seconds and Classic doesn't support actions after 1 second

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
                        can=orm_object.module.device_type == 'b',
                        event_enabled=False)  # TODO: Migrate to ORM

    @staticmethod
    def dto_to_orm(input_dto, fields):  # type: (InputDTO, List[str]) -> InputConfiguration
        new_data = {'id': input_dto.id}  # type: Dict[str, Any]
        if 'name' in fields:
            new_data['name'] = input_dto.name
        if 'action' in fields and 'basic_actions' in fields:
            new_data.update(
                InputMapper.classic_actions_to_core_input_configuration(input_dto.action, input_dto.basic_actions)
            )
        if 'invert' in fields:
            new_data['normal_open'] = not input_dto.invert
        # TODO event_enabled
        return InputConfiguration.deserialize(new_data)

    @staticmethod
    def core_input_configuration_to_classic_actions(orm_object):
        # type: (InputConfiguration) -> Tuple[int, List[int]]
        if False:
            return 255, []  # TODO: Detect disabled input
        if not orm_object.input_link.enable_specific_actions:
            # No specific actions; this Input is directly linked to an Output
            return orm_object.input_link.output_id, []
        action = 240
        basic_actions = []
        if orm_object.input_link.enable_2s_press:
            ba_2s_press = orm_object.basic_action_2s_press
            if ba_2s_press.action_type == 19 and ba_2s_press.action == 0:
                # 207: When current input is pressed for more than 2 seconds, execute group action x
                basic_actions += [207, ba_2s_press.device_nr]
        if orm_object.basic_action_release.in_use:
            # 236: Execute all next actions at button release (x=0), x=255 -> All next instructions will be executed normally
            basic_actions += [236, 0]
            basic_actions += GroupActionMapper.core_actions_to_classic_actions([orm_object.basic_action_release])
            basic_actions += [236, 255]
        if orm_object.basic_action_press:
            basic_actions += GroupActionMapper.core_actions_to_classic_actions([orm_object.basic_action_press])
        return action, basic_actions

    @staticmethod
    def classic_actions_to_core_input_configuration(action, basic_actions):
        # type: (Optional[int], List[int]) -> Dict[str, Any]
        if action is None or action == 255:
            return {}  # TODO: Disable input
        if action < 240:
            return {'input_link': {'output_id': action,
                                   'enable_specific_actions': False}}
        data = {'input_link': {'enable_specific_actions': True}}  # type: Dict[str, Any]
        release_actions = []
        release_code = False
        for i in range(0, len(basic_actions), 2):
            action_type = basic_actions[i]
            action_number = basic_actions[i + 1]
            if action_type == 207:
                data['input_link']['enable_2s_press'] = True
                data['basic_action_2s_press'] = BasicAction(action_type=19, action=0,
                                                            device_nr=action_number)
            elif action_type == 236 and action_number == 0:
                release_code = True
            elif action_type == 236 and action_number == 255:
                release_code = False
            elif release_code:
                release_actions += [action_type, action_number]
        if len(release_actions) == 2 and release_actions[0] == 2:
            data['basic_action_release'] = BasicAction(action_type=19, action=0,
                                                       device_nr=release_actions[1])
        return data
