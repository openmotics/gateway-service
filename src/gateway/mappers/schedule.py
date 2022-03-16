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
Schedule Mapper
"""
from __future__ import absolute_import
import json
from gateway.dto import ScheduleDTO
from gateway.models import Schedule, Session

if False:  # MYPY
    from typing import List, Optional, Any


class ScheduleMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):  # type: (Schedule) -> ScheduleDTO
        arguments = None  # type: Optional[Any]
        if orm_object.arguments is not None:
            arguments = json.loads(orm_object.arguments)
        return ScheduleDTO(id=orm_object.id,
                           source=orm_object.source,
                           external_id=orm_object.external_id,
                           name=orm_object.name,
                           start=orm_object.start,
                           action=orm_object.action,
                           status=orm_object.status,
                           repeat=orm_object.repeat,
                           duration=orm_object.duration,
                           end=orm_object.end,
                           arguments=arguments)

    @staticmethod
    def dto_to_orm(db, schedule_dto):  # type: (Session, ScheduleDTO) -> Schedule
        schedule = db.query(Schedule).where(Schedule.id == schedule_dto.id).one_or_none()
        if schedule is None:
            mandatory_fields = {'name', 'start', 'action'}
            if not mandatory_fields.issubset(set(schedule_dto.loaded_fields)):
                raise ValueError('Cannot create schedule without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))
            schedule = Schedule(status='ACTIVE', **{field: getattr(schedule_dto, field)
                                                    for field in mandatory_fields})
        for field in ['source', 'external_id', 'name', 'start', 'action', 'status', 'repeat', 'duration', 'end']:
            if field in schedule_dto.loaded_fields:
                setattr(schedule, field, getattr(schedule_dto, field))
        if 'arguments' in schedule_dto.loaded_fields:
            arguments = None
            if schedule_dto.arguments is not None:
                arguments = json.dumps(schedule_dto.arguments)
            schedule.arguments = arguments
        return schedule
