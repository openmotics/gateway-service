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
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import ScheduleDTO

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
    def deserialize(api_data):  # type: (Dict) -> Tuple[ScheduleDTO, List[str]]
        raise NotImplementedError()
