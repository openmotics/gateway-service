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
PulseCounter Mapper
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.dto import PulseCounterDTO
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import PulseCounterConfiguration

if False:  # MYPY
    from typing import List, Dict, Any


class PulseCounterMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> PulseCounterDTO
        data = orm_object.serialize()
        return PulseCounterDTO(id=data['id'],
                               name=data['name'],
                               input_id=Toolbox.nonify(data['input'], PulseCounterMapper.BYTE_MAX),
                               persistent=False)

    @staticmethod
    def dto_to_orm(pulse_counter_dto):  # type: (PulseCounterDTO) -> EepromModel
        data = {'id': pulse_counter_dto.id}  # type: Dict[str, Any]
        if 'name' in pulse_counter_dto.loaded_fields:
            data['name'] = Toolbox.shorten_name(pulse_counter_dto.name)
        if 'input_id' in pulse_counter_dto.loaded_fields:
            data['input'] = Toolbox.denonify(pulse_counter_dto.input_id, PulseCounterMapper.BYTE_MAX)
        return PulseCounterConfiguration.deserialize(data)
