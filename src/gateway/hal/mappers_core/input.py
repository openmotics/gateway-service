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
from master.core.memory_models import InputConfiguration

if False:  # MYPY
    from typing import List, Dict, Any


class InputMapper(object):
    @staticmethod
    def orm_to_dto(orm_object):  # type: (InputConfiguration) -> InputDTO
        return InputDTO(id=orm_object.id,
                        name=orm_object.name,
                        module_type=orm_object.module.device_type)  # TODO: Proper translation

    @staticmethod
    def dto_to_orm(input_dto, fields):  # type: (InputDTO, List[str]) -> InputConfiguration
        new_data = {'id': input_dto.id}  # type: Dict[str, Any]
        if 'name' in fields:
            new_data['name'] = input_dto.name
        return InputConfiguration.deserialize(new_data)
