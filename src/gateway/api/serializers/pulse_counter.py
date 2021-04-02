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
PulseCounter (de)serializer
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import PulseCounterDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class PulseCounterSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(pulse_counter_dto, fields):  # type: (PulseCounterDTO, Optional[List[str]]) -> Dict
        data = {'id': pulse_counter_dto.id,
                'name': pulse_counter_dto.name,
                'input': Toolbox.denonify(pulse_counter_dto.input_id, PulseCounterSerializer.BYTE_MAX),
                'persistent': pulse_counter_dto.persistent,
                'room': Toolbox.denonify(pulse_counter_dto.room, PulseCounterSerializer.BYTE_MAX)}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> PulseCounterDTO
        pulse_counter_dto = PulseCounterDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=pulse_counter_dto,  # Referenced
            api_data=api_data,
            mapping={'name': ('name', None),
                     'persistent': ('persistent', None),
                     'input': ('input_id', PulseCounterSerializer.BYTE_MAX),
                     'room': ('room', PulseCounterSerializer.BYTE_MAX)}
        )
        return pulse_counter_dto
