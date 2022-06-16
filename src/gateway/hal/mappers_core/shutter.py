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
Shutter Mapper
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.dto.shutter import ShutterDTO
from master.core.memory_models import ShutterConfiguration

if False:  # MYPY
    from typing import List, Dict, Any


class ShutterMapper(object):
    WORD_MAX = 2 ** 16 - 1
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (ShutterConfiguration) -> ShutterDTO
        kwargs = {}
        for field in ['timer_up', 'timer_down']:
            kwargs[field] = Toolbox.nonify(getattr(orm_object, field), ShutterMapper.WORD_MAX)
            if kwargs[field] is not None:
                # TODO: High-level code currently assumes this is a byte
                kwargs[field] = min(ShutterMapper.BYTE_MAX, kwargs[field] // 10)
        member_groups = []
        for group_id in range(16):
            if getattr(orm_object.groups, 'group_{0}'.format(group_id)):
                member_groups.append(group_id)
        if len(member_groups) >= 1:
            kwargs['group_1'] = member_groups[0]
        if len(member_groups) >= 2:
            kwargs['group_2'] = member_groups[1]
        return ShutterDTO(id=orm_object.id,
                          name=orm_object.name,
                          **kwargs)

    @staticmethod
    def dto_to_orm(shutter_dto):  # type: (ShutterDTO) -> ShutterConfiguration
        new_data = {'id': shutter_dto.id}  # type: Dict[str, Any]
        if 'name' in shutter_dto.loaded_fields:
            new_data['name'] = Toolbox.shorten_name(shutter_dto.name, maxlength=16)
        for field in ['timer_up', 'timer_down']:
            dto_value = getattr(shutter_dto, field)
            if dto_value is None:
                new_data[field] = ShutterMapper.WORD_MAX
            else:
                new_data[field] = dto_value * 10
        groups = {}
        for group_id in range(16):
            group_name = 'group_{0}'.format(group_id)
            groups[group_name] = False
            if group_id in [shutter_dto.group_1, shutter_dto.group_2]:
                groups[group_name] = True
        new_data['groups'] = groups
        return ShutterConfiguration.deserialize(new_data)
