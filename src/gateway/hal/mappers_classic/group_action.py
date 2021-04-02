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
GroupAction Mapper
"""
from __future__ import absolute_import
from gateway.dto import GroupActionDTO
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import GroupActionConfiguration

if False:  # MYPY
    from typing import Dict, Any


class GroupActionMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> GroupActionDTO
        data = orm_object.serialize()
        return GroupActionDTO(id=data['id'],
                              name=data['name'],
                              actions=[] if data['actions'] == '' else [int(i) for i in data['actions'].split(',')])

    @staticmethod
    def dto_to_orm(group_action_dto):  # type: (GroupActionDTO) -> EepromModel
        data = {'id': group_action_dto.id}  # type: Dict[str, Any]
        for dto_field, data_field in {'name': 'name'}.items():
            if dto_field in group_action_dto.loaded_fields:
                data[data_field] = getattr(group_action_dto, dto_field)
        if 'actions' in group_action_dto.loaded_fields:
            data['actions'] = ','.join([str(action) for action in group_action_dto.actions])
        return GroupActionConfiguration.deserialize(data)
