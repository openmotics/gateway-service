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

import logging

from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import VentilationDTO, VentilationSourceDTO, \
    VentilationStatusDTO
from toolbox import Toolbox

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple

logger = logging.getLogger('openmotics')


class VentilationSerializer(object):
    @staticmethod
    def serialize(ventilation_dto, fields):
        # type: (VentilationDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': ventilation_dto.id,
                'external_id': Toolbox.denonify(ventilation_dto.external_id, ''),
                'source': {'type': ventilation_dto.source.type,
                           'name': ventilation_dto.source.name},
                'name': Toolbox.denonify(ventilation_dto.name, ''),
                'amount_of_levels': Toolbox.denonify(ventilation_dto.amount_of_levels, 0),
                'device': {'vendor': Toolbox.denonify(ventilation_dto.device_vendor, ''),
                           'type': Toolbox.denonify(ventilation_dto.device_type, '')}}
        if ventilation_dto.device_serial:
            data['device'].update({'serial': Toolbox.denonify(ventilation_dto.device_serial, '')})
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
        if 'amount_of_levels' in api_data:
            loaded_fields.append('amount_of_levels')
            ventilation_dto.amount_of_levels = Toolbox.nonify(api_data['amount_of_levels'], '')
        if 'device' in api_data:
            loaded_fields.append('device')
            if 'type' in api_data['device']:
                ventilation_dto.device_type = Toolbox.nonify(api_data['device']['type'], '')
            if 'vendor' in api_data['device']:
                ventilation_dto.device_vendor = Toolbox.nonify(api_data['device']['vendor'], '')
            if 'serial' in api_data['device']:
                ventilation_dto.device_serial = Toolbox.nonify(api_data['device']['serial'], '')
        return ventilation_dto, loaded_fields


class VentilationStatusSerializer(object):
    @staticmethod
    def serialize(status_dto, fields):
        # type: (VentilationStatusDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': status_dto.id,
                'mode': status_dto.mode,
                'level': status_dto.level,
                'remaining_time': status_dto.remaining_time,
                'timer': status_dto.timer,
                'connected': status_dto.is_connected}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> Tuple[VentilationStatusDTO, List[str]]
        loaded_fields = ['id', 'mode']
        status_dto = VentilationStatusDTO(api_data['id'], api_data['mode'])
        if 'level' in api_data:
            loaded_fields.append('level')
            status_dto.level = Toolbox.nonify(api_data['level'], 0)
        if 'timer' in api_data:
            loaded_fields.append('timer')
            status_dto.timer = Toolbox.nonify(api_data['timer'], 0)
        if 'remaining_time' in api_data:
            loaded_fields.append('remaining_time')
            status_dto.remaining_time = Toolbox.nonify(api_data['remaining_time'], 0)
        return status_dto, loaded_fields
