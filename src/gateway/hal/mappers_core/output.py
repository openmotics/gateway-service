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
from toolbox import Toolbox
from gateway.dto.output import OutputDTO
from master.core.memory_models import OutputConfiguration
from enums import HardwareType, OutputType

if False:  # MYPY
    from typing import List, Dict, Any, Optional


class OutputMapper(object):
    # TODO: Implement missing parts
    #  * Locking
    #  * Absolute (e.g. 15:45) and float (e.g. 15.3 seconds) timers

    @staticmethod
    def orm_to_dto(orm_object):  # type: (OutputConfiguration) -> OutputDTO
        module_type = orm_object.module.device_type
        if orm_object.module.hardware_type == HardwareType.INTERNAL:
            module_type = module_type.upper()
        if module_type == 'L':
            module_type = 'O'  # Open collector is returned as normal output
        timer = None  # type: Optional[int]
        if orm_object.timer_type == OutputConfiguration.TimerType.PER_1_S:
            timer = orm_object.timer_value
        elif orm_object.timer_type == OutputConfiguration.TimerType.PER_100_MS:
            timer = int(orm_object.timer_value / 10.0)
        output_type = orm_object.output_type
        if orm_object.is_shutter:
            output_type = OutputType.SHUTTER_RELAY  # Make sure the output type is correct for shutters
        elif output_type == OutputType.SHUTTER_RELAY:
            output_type = OutputType.OUTLET
        return OutputDTO(id=orm_object.id,
                         name=orm_object.name,
                         module_type=module_type,
                         timer=timer,
                         output_type=output_type)

    @staticmethod
    def dto_to_orm(output_dto):  # type: (OutputDTO) -> OutputConfiguration
        data = {'id': output_dto.id}  # type: Dict[str, Any]
        if 'output_type' in output_dto.loaded_fields:
            data['output_type'] = output_dto.output_type
        if 'name' in output_dto.loaded_fields:
            data['name'] = Toolbox.shorten_name(output_dto.name, maxlength=16)
        if 'timer' in output_dto.loaded_fields:
            timer = output_dto.timer
            if timer is None or timer <= 0 or timer == 65535:
                data['timer_type'] = OutputConfiguration.TimerType.INACTIVE
                data['timer_value'] = 0
            elif timer <= 3:
                data['timer_type'] = OutputConfiguration.TimerType.PER_100_MS
                data['timer_value'] = timer * 10
            else:
                data['timer_type'] = OutputConfiguration.TimerType.PER_1_S
                data['timer_value'] = min(timer, 65534)
        return OutputConfiguration.deserialize(data)
