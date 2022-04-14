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
Output (de)serializer
"""
from __future__ import absolute_import

from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import FeedbackLedDTO, OutputDTO, OutputStatusDTO, \
    DimmerConfigurationDTO
from toolbox import Toolbox

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class OutputSerializer(object):
    WORD_MAX = 2 ** 16 - 1
    BYTE_MAX = 255

    @staticmethod
    def serialize(output_dto, fields):  # type: (OutputDTO, Optional[List[str]]) -> Dict
        data = {'id': output_dto.id,
                'module_type': output_dto.module_type,
                'name': output_dto.name,
                'timer': Toolbox.denonify(output_dto.timer, OutputSerializer.WORD_MAX),
                'type': Toolbox.denonify(output_dto.output_type, OutputSerializer.BYTE_MAX),
                'lock_bit_id': Toolbox.denonify(output_dto.lock_bit_id, OutputSerializer.BYTE_MAX),
                'can_led_1_id': Toolbox.denonify(output_dto.can_led_1.id, OutputSerializer.BYTE_MAX),
                'can_led_1_function': output_dto.can_led_1.function,
                'can_led_2_id': Toolbox.denonify(output_dto.can_led_2.id, OutputSerializer.BYTE_MAX),
                'can_led_2_function': output_dto.can_led_2.function,
                'can_led_3_id': Toolbox.denonify(output_dto.can_led_3.id, OutputSerializer.BYTE_MAX),
                'can_led_3_function': output_dto.can_led_3.function,
                'can_led_4_id': Toolbox.denonify(output_dto.can_led_4.id, OutputSerializer.BYTE_MAX),
                'can_led_4_function': output_dto.can_led_4.function,
                'in_use': output_dto.in_use,
                'room': Toolbox.denonify(output_dto.room, OutputSerializer.BYTE_MAX)}
        if output_dto.module is not None:
            data.update({'module': {'hardware_type': output_dto.module.hardware_type,
                                    'hardware_module': output_dto.module.module_type,
                                    'module_id': output_dto.module.order}})
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> OutputDTO
        output_dto = OutputDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=output_dto,  # Referenced
            api_data=api_data,
            mapping={'module_type': ('module_type', None),
                     'name': ('name', None),
                     'type': ('output_type', None),
                     'in_use': ('in_use', None),
                     'lock_bit_id': ('lock_bit_id', OutputSerializer.BYTE_MAX),
                     'timer': ('timer', OutputSerializer.WORD_MAX),
                     'room': ('room', OutputSerializer.BYTE_MAX)}
        )
        for i in range(4):
            base_field = 'can_led_{0}'.format(i + 1)
            id_field = '{0}_id'.format(base_field)
            function_field = '{0}_function'.format(base_field)
            if id_field in api_data and function_field in api_data:
                setattr(output_dto, base_field, FeedbackLedDTO(id=Toolbox.nonify(api_data[id_field], OutputSerializer.BYTE_MAX),
                                                               function=api_data[function_field]))
        return output_dto


class OutputStateSerializer(object):
    @staticmethod
    def serialize(output_state_dto, fields):
        # type: (OutputStatusDTO, Optional[List[str]]) -> Dict
        data = {'id': output_state_dto.id,
                'status': 1 if output_state_dto.status else 0,
                'ctimer': output_state_dto.ctimer,
                'dimmer': output_state_dto.dimmer,
                'locked': output_state_dto.locked}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict) -> OutputStatusDTO
        output_state_dto = OutputStatusDTO(api_data['id'])
        SerializerToolbox.deserialize(
            dto=output_state_dto,  # Referenced
            api_data=api_data,
            mapping={'status': ('status', bool),
                     'ctimer': ('ctimer', lambda x: x or 0),
                     'dimmer': ('dimmer', lambda x: x or 0),
                     'locked': ('locked', lambda x: x or False)}
        )
        return output_state_dto


class DimmerConfigurationSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(dimmer_configuration_dto, fields):  # type: (DimmerConfigurationDTO, Optional[List[str]]) -> Dict
        data = {}
        for field in ['min_dim_level', 'dim_step', 'dim_wait_cycle', 'dim_memory']:
            data[field] = Toolbox.denonify(getattr(dimmer_configuration_dto, field), DimmerConfigurationSerializer.BYTE_MAX)
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> DimmerConfigurationDTO
        dimmer_configuration_dto = DimmerConfigurationDTO()
        SerializerToolbox.deserialize(
            dto=dimmer_configuration_dto,  # Referenced
            api_data=api_data,
            mapping={'min_dim_level': ('min_dim_level', DimmerConfigurationSerializer.BYTE_MAX),
                     'dim_step': ('dim_step', DimmerConfigurationSerializer.BYTE_MAX),
                     'dim_wait_cycle': ('dim_wait_cycle', DimmerConfigurationSerializer.BYTE_MAX),
                     'dim_memory': ('dim_memory', DimmerConfigurationSerializer.BYTE_MAX)}
        )
        return dimmer_configuration_dto
