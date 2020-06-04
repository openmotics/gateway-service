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
    from typing import List, Dict, Any


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
                        can=data['can'] == 'C',
                        event_enabled=data['event_enabled'])

    @staticmethod
    def dto_to_orm(input_dto, fields):  # type: (InputDTO, List[str]) -> EepromModel
        data = {'id': input_dto.id}  # type: Dict[str, Any]
        for dto_field, data_field in {'module_type': 'module_type',
                                      'name': 'name',
                                      'event_enabled': 'event_enabled'}.items():
            if dto_field in fields:
                data[data_field] = getattr(input_dto, dto_field)
        for dto_field, (data_field, default) in {'action': ('action', InputMapper.BYTE_MAX)}.items():
            if dto_field in fields:
                data[data_field] = Toolbox.denonify(getattr(input_dto, dto_field), default)
        if 'basic_actions' in fields:
            data['basic_actions'] = ','.join([str(action) for action in input_dto.basic_actions])
        if 'invert' in fields:
            data['invert'] = 0 if input_dto.invert else 255
        if 'can' in fields:
            data['can'] = 'C' if input_dto.can else ' '
        return InputConfiguration.deserialize(data)
