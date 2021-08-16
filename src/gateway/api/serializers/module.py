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
from gateway.enums import ModuleType, HardwareType

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple, Any


class ModuleSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(module_dto, fields):  # type: (ModuleDTO, Optional[List[str]]) -> Dict
        data = {'address': module_dto.address}  # type: Dict[str, Any]
        if module_dto.source == ModuleDTO.Source.MASTER:
            category_map = {ModuleType.CAN_CONTROL: 'INPUT',
                            ModuleType.SENSOR: 'INPUT',
                            ModuleType.INPUT: 'INPUT',
                            ModuleType.SHUTTER: 'SHUTTER',
                            ModuleType.OUTPUT: 'OUTPUT',
                            ModuleType.DIM_CONTROL: 'OUTPUT',
                            ModuleType.OPEN_COLLECTOR: 'OUTPUT',
                            None: 'UNKNOWN'}
            type_int = int(module_dto.address.split('.')[0])
            data.update({'type': chr(type_int) if 32 <= type_int <= 126 else None,
                         'hardware_type': module_dto.hardware_type,
                         'module_nr': module_dto.order,
                         'is_can': (module_dto.hardware_type == HardwareType.EMULATED or
                                    module_dto.module_type == ModuleType.CAN_CONTROL),
                         'is_virtual': module_dto.hardware_type == HardwareType.VIRTUAL,
                         'category': category_map.get(module_dto.module_type, 'UNKNOWN')})
            if module_dto.hardware_type == HardwareType.PHYSICAL:
                data.update({'firmware': module_dto.firmware_version,
                             'hardware': module_dto.hardware_version})
        else:
            module_type_map = {ModuleType.ENERGY: 'E',
                               ModuleType.POWER: 'P',
                               ModuleType.P1_CONCENTRATOR: 'C',
                               None: 'U'}
            data.update({'type': module_type_map.get(module_dto.module_type, 'U'),
                         'firmware': module_dto.firmware_version,
                         'address': module_dto.address,
                         'id': module_dto.order})
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> ModuleDTO
        raise NotImplementedError()  # Not supported
