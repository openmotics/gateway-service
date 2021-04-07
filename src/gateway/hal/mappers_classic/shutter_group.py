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
ShutterGroup Mapper
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.dto.shutter_group import ShutterGroupDTO
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import ShutterGroupConfiguration


class ShutterGroupMapper(object):
    WORD_MAX = 2 ** 16 - 1
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> ShutterGroupDTO
        data = orm_object.serialize()
        kwargs = {}
        for field in ['timer_up', 'timer_down']:
            kwargs[field] = Toolbox.nonify(data[field], ShutterGroupMapper.BYTE_MAX)
        return ShutterGroupDTO(id=data['id'],
                               **kwargs)

    @staticmethod
    def dto_to_orm(shutter_dto):  # type: (ShutterGroupDTO) -> EepromModel
        data = {'id': shutter_dto.id}
        for field in ['timer_up', 'timer_down']:
            if field in shutter_dto.loaded_fields:
                data[field] = Toolbox.denonify(getattr(shutter_dto, field), ShutterGroupMapper.BYTE_MAX)
        return ShutterGroupConfiguration.deserialize(data)
