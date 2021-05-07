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
Schedule (de)serializer
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import ScheduleDTO, LegacyScheduleDTO, LegacyStartupActionDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class ScheduleSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(schedule_dto, fields):  # type: (ScheduleDTO, Optional[List[str]]) -> Dict
        data = {'id': schedule_dto.id,
                'name': schedule_dto.name,
                'start': schedule_dto.start,
                'repeat': schedule_dto.repeat,
                'duration': schedule_dto.duration,
                'end': schedule_dto.end,
                'schedule_type': schedule_dto.action,
                'arguments': schedule_dto.arguments,
                'status': schedule_dto.status,
                'last_executed': schedule_dto.last_executed,
                'next_execution': schedule_dto.next_execution}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> ScheduleDTO
        raise NotImplementedError()


class LegacyScheduleSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(schedule_dto, fields):  # type: (LegacyScheduleDTO, Optional[List[str]]) -> Dict
        data = {'id': schedule_dto.id,
                'hour': Toolbox.denonify(schedule_dto.hour, LegacyScheduleSerializer.BYTE_MAX),
                'minute': Toolbox.denonify(schedule_dto.minute, LegacyScheduleSerializer.BYTE_MAX),
                'day': Toolbox.denonify(schedule_dto.day, LegacyScheduleSerializer.BYTE_MAX),
                'action': ','.join([str(action) for action in schedule_dto.action])}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> LegacyScheduleDTO
        schedule_dto = LegacyScheduleDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=schedule_dto,  # Referenced
            api_data=api_data,
            mapping={'hour': ('hour', LegacyScheduleSerializer.BYTE_MAX),
                     'minute': ('minute', LegacyScheduleSerializer.BYTE_MAX),
                     'day': ('day', LegacyScheduleSerializer.BYTE_MAX),
                     'action': ('action', lambda s: [] if s == '' else [int(a) for a in s.split(',')])}
        )
        return schedule_dto


class LegacyStartupActionSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(startup_action_dto, fields):  # type: (LegacyStartupActionDTO, Optional[List[str]]) -> Dict
        data = {'actions': ','.join([str(action) for action in startup_action_dto.actions])}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> LegacyStartupActionDTO
        startup_action_dto = LegacyStartupActionDTO()
        SerializerToolbox.deserialize(
            dto=startup_action_dto,  # Referenced
            api_data=api_data,
            mapping={'actions': ('actions', lambda s: [] if s == '' else [int(a) for a in s.split(',')])}
        )
        return startup_action_dto
