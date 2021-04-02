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
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import ShutterConfiguration


class ShutterMapper(object):
    WORD_MAX = 2 ** 16 - 1
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> ShutterDTO
        data = orm_object.serialize()
        kwargs = {}
        for field in ['timer_up', 'timer_down', 'up_down_config', 'group_1', 'group_2']:
            kwargs[field] = Toolbox.nonify(data[field], ShutterMapper.BYTE_MAX)
        for field in ['steps']:
            kwargs[field] = Toolbox.nonify(data[field], ShutterMapper.WORD_MAX)
        return ShutterDTO(id=data['id'],
                          name=data['name'],
                          **kwargs)

    @staticmethod
    def dto_to_orm(shutter_dto):  # type: (ShutterDTO) -> EepromModel
        data = {'id': shutter_dto.id,
                'name': shutter_dto.name}
        for field in ['name']:
            if field in shutter_dto.loaded_fields:
                data[field] = getattr(shutter_dto, field)
        for field in ['timer_up', 'timer_down', 'up_down_config', 'group_1', 'group_2']:
            if field in shutter_dto.loaded_fields:
                data[field] = Toolbox.denonify(getattr(shutter_dto, field), ShutterMapper.BYTE_MAX)
        for field in ['steps']:
            if field in shutter_dto.loaded_fields:
                data[field] = Toolbox.denonify(getattr(shutter_dto, field), ShutterMapper.WORD_MAX)
        return ShutterConfiguration.deserialize(data)
