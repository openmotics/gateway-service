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
Ventilation (de)serializer
"""
from __future__ import absolute_import

from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import VentilationDTO, VentilationSourceDTO
from toolbox import Toolbox

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple


class VentilationSerializer(object):
    @staticmethod
    def serialize(ventilation_dto, fields):
        # type: (VentilationDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': ventilation_dto.id,
                'source': {
                    'type': ventilation_dto.source.type,
                    'name': ventilation_dto.source.name,
                },
                'external_id': Toolbox.denonify(ventilation_dto.external_id, ''),
                'name': Toolbox.denonify(ventilation_dto.name, ''),
                'type': Toolbox.denonify(ventilation_dto.type, ''),
                'vendor': Toolbox.denonify(ventilation_dto.vendor, ''),
                'amount_of_levels': Toolbox.denonify(ventilation_dto.amount_of_levels, 0)}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> Tuple[VentilationDTO, List[str]]
        loaded_fields = ['source']
        ventilation_id = None  # type: Optional[int]
        if 'id' in api_data:
            loaded_fields.append('id')
            ventilation_id = api_data['id']
        source_dto = None  # type: Optional[VentilationSourceDTO]
        if 'source' in api_data:
            source_dto = VentilationSourceDTO(None,
                                              name=api_data['source']['name'],
                                              type=api_data['source']['type'])
        ventilation_dto = VentilationDTO(id=ventilation_id, source=source_dto)
        if 'external_id' in api_data:
            loaded_fields.append('external_id')
            ventilation_dto.external_id = Toolbox.nonify(api_data['external_id'], '')
        if 'name' in api_data:
            loaded_fields.append('name')
            ventilation_dto.name = Toolbox.nonify(api_data['name'], '')
        if 'type' in api_data:
            loaded_fields.append('type')
            ventilation_dto.type = Toolbox.nonify(api_data['type'], '')
        if 'vendor' in api_data:
            loaded_fields.append('vendor')
            ventilation_dto.vendor = Toolbox.nonify(api_data['vendor'], '')
        if 'amount_of_levels' in api_data:
            loaded_fields.append('amount_of_levels')
            ventilation_dto.amount_of_levels = Toolbox.nonify(api_data['amount_of_levels'], '')
        return ventilation_dto, loaded_fields
