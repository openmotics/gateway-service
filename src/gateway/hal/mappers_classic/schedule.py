# Copyright (C) 2021 OpenMotics BV
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
Legacy Schedule Mapper
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.dto import LegacyScheduleDTO, LegacyStartupActionDTO
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import ScheduledActionConfiguration, StartupActionConfiguration

if False:  # MYPY
    from typing import Dict, Any


class LegacyScheduleMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> LegacyScheduleDTO
        data = orm_object.serialize()
        return LegacyScheduleDTO(id=data['id'],
                                 hour=Toolbox.nonify(data['hour'], LegacyScheduleMapper.BYTE_MAX),
                                 minute=Toolbox.nonify(data['minute'], LegacyScheduleMapper.BYTE_MAX),
                                 day=Toolbox.nonify(data['day'], LegacyScheduleMapper.BYTE_MAX),
                                 action=None if data['action'] == '' else int(data['action']))

    @staticmethod
    def dto_to_orm(schedule_dto):  # type: (LegacyScheduleDTO) -> EepromModel
        data = {'id': schedule_dto.id}  # type: Dict[str, Any]
        for dto_field, data_field in {'hour': 'hour',
                                      'minute': 'minute',
                                      'day': 'day'}.items():
            if dto_field in schedule_dto.loaded_fields:
                data[data_field] = Toolbox.denonify(getattr(schedule_dto, dto_field), LegacyScheduleMapper.BYTE_MAX)
        if 'action' in schedule_dto.loaded_fields:
            data['action'] = '' if schedule_dto.action is None else str(schedule_dto.action)
        return ScheduledActionConfiguration.deserialize(data)


class LegacyStartupActionMapper(object):
    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> LegacyStartupActionDTO
        data = orm_object.serialize()
        return LegacyStartupActionDTO(actions=[] if data['actions'] == '' else [int(i) for i in data['actions'].split(',')])

    @staticmethod
    def dto_to_orm(startup_action_dto):  # type: (LegacyStartupActionDTO) -> EepromModel
        data = {}  # type: Dict[str, Any]
        if 'actions' in startup_action_dto.loaded_fields:
            data['actions'] = ','.join([str(action) for action in startup_action_dto.actions])
        return StartupActionConfiguration.deserialize(data)
