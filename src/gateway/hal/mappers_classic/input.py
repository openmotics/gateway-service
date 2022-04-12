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
from toolbox import Toolbox
from gateway.dto.input import InputDTO
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import InputConfiguration

if False:  # MYPY
    from typing import Dict, Any


class InputMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> InputDTO
        data = orm_object.serialize()
        return InputDTO(id=data['id'],
                        module_type=data['module_type'],
                        name=data['name'],
                        action=Toolbox.nonify(data['action'], InputMapper.BYTE_MAX),
                        basic_actions=[] if data['basic_actions'] == '' else [int(i) for i in data['basic_actions'].split(',')],
                        invert=data['invert'] != 255,
                        can=data['can'] == 'C')

    @staticmethod
    def dto_to_orm(input_dto):  # type: (InputDTO) -> EepromModel
        data = {'id': input_dto.id}  # type: Dict[str, Any]
        if 'name' in input_dto.loaded_fields:
            data['name'] = Toolbox.shorten_name(input_dto.name, maxlength=8)
        if 'module_type' in input_dto.loaded_fields:
            data['module_type'] = input_dto.module_type
        for dto_field, (data_field, default) in {'action': ('action', InputMapper.BYTE_MAX)}.items():
            if dto_field in input_dto.loaded_fields:
                data[data_field] = Toolbox.denonify(getattr(input_dto, dto_field), default)
        if 'basic_actions' in input_dto.loaded_fields:
            data['basic_actions'] = ','.join([str(action) for action in input_dto.basic_actions])
        if 'invert' in input_dto.loaded_fields:
            data['invert'] = 0 if input_dto.invert else 255
        if 'can' in input_dto.loaded_fields:
            data['can'] = 'C' if input_dto.can else ' '
        return InputConfiguration.deserialize(data)
