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
from __future__ import absolute_import
from gateway.dto.output import OutputDTO
from master.core.memory_models import OutputConfiguration

if False:  # MYPY
    from typing import List, Dict, Any, Optional


class OutputMapper(object):
    # TODO: Implement missing parts
    #  * Locking
    #  * Absolute (e.g. 15:45) and float (e.g. 15.3 seconds) timers

    @staticmethod
    def orm_to_dto(orm_object):  # type: (OutputConfiguration) -> OutputDTO
        module_type = orm_object.module.device_type
        if '.000.000.' in orm_object.module.address:
            module_type = 'O'  # Internal outputs are returned as physical/real
        timer = None  # type: Optional[int]
        if orm_object.timer_type == OutputConfiguration.TimerType.PER_1_S:
            timer = orm_object.timer_value
        elif orm_object.timer_type == OutputConfiguration.TimerType.PER_100_MS:
            timer = int(orm_object.timer_value / 10.0)
        return OutputDTO(id=orm_object.id,
                         name=orm_object.name,
                         module_type=module_type,
                         timer=timer,
                         output_type=orm_object.output_type)

    @staticmethod
    def dto_to_orm(output_dto):  # type: (OutputDTO) -> OutputConfiguration
        data = {'id': output_dto.id}  # type: Dict[str, Any]
        for dto_field, data_field in {'name': 'name',
                                      'output_type': 'output_type'}.items():
            if dto_field in output_dto.loaded_fields:
                data[data_field] = getattr(output_dto, dto_field)
        if 'timer' in output_dto.loaded_fields:
            timer = output_dto.timer
            if timer is None or timer <= 0 or timer == 65535:
                data['timer_type'] = OutputConfiguration.TimerType.INACTIVE
                data['timer_value'] = 0
            else:
                data['timer_type'] = OutputConfiguration.TimerType.PER_1_S
                data['timer_value'] = min(timer, 65534)
        return OutputConfiguration.deserialize(data)
