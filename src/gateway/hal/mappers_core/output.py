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
Output Mapper
"""
from gateway.dto.output import OutputDTO
from master_core.memory_models import OutputConfiguration

if False:  # MYPY
    from typing import List


class OutputMapper(object):
    @staticmethod
    def orm_to_dto(orm_object):  # type: (OutputConfiguration) -> OutputDTO
        timer = 0
        if orm_object.timer_type == 2:
            timer = orm_object.timer_value
        elif orm_object.timer_type == 1:
            timer = orm_object.timer_value / 10.0
        return OutputDTO(id=orm_object.id,
                         name=orm_object.name,
                         module_type=orm_object.module.device_type,  # TODO: Proper translation
                         timer=timer,  # TODO: Proper calculation
                         output_type=orm_object.output_type)  # TODO: Proper translation

    @staticmethod
    def dto_to_orm(output_dto, fields):  # type: (OutputDTO, List[str]) -> OutputConfiguration
        new_data = {'id': output_dto.id}
        if 'name' in fields:
            new_data['name'] = output_dto.name
        # TODO: Rest of the mapping
        return OutputConfiguration.deserialize(new_data)
