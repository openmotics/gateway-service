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
Module serializer
"""
from __future__ import absolute_import
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import ModuleDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Any


class ModuleSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(module_dto, fields):  # type: (ModuleDTO, Optional[List[str]]) -> Dict
        data = {'address': module_dto.address,
                'source': module_dto.source,
                'module_type': module_dto.module_type,
                'hardware_type': module_dto.hardware_type,
                'firmware_version': module_dto.firmware_version,
                'order': module_dto.order,
                'update_success': module_dto.update_success}  # type: Dict[str, Any]
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> ModuleDTO
        raise NotImplementedError()  # Not supported
