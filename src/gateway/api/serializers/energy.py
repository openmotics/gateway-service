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
Energy (de)serializer
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import EnergyModuleDTO

if False:  # MYPY
    from typing import Dict, Optional, List


class EnergyModuleSerializer(object):
    DTO_FIELDS = ['id', 'name', 'address', 'version',
                  'input0', 'input1', 'input2', 'input3', 'input4', 'input5', 'input6', 'input7', 'input8', 'input9', 'input10', 'input11',
                  'sensor0', 'sensor1', 'sensor2', 'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7', 'sensor8', 'sensor9', 'sensor10', 'sensor11',
                  'times0', 'times1', 'times2', 'times3', 'times4', 'times5', 'times6', 'times7', 'times8', 'times9', 'times10', 'times11',
                  'inverted0', 'inverted1', 'inverted2', 'inverted3', 'inverted4', 'inverted5', 'inverted6', 'inverted7', 'inverted8', 'inverted9', 'inverted10', 'inverted11']

    @staticmethod
    def serialize(energy_module_dto, fields):  # type: (EnergyModuleDTO, Optional[List[str]]) -> Dict
        data = {}
        for field in EnergyModuleSerializer.DTO_FIELDS:
            data[field] = getattr(energy_module_dto, field)
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> EnergyModuleDTO
        kwargs = {}
        for field in EnergyModuleSerializer.DTO_FIELDS:
            if field in api_data:
                kwargs[field] = field
        return EnergyModuleDTO(**kwargs)
