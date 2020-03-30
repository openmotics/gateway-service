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
from toolbox import Toolbox
from gateway.dto.output import OutputDTO
from gateway.dto.feedback_led import FeedbackLedDTO

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class OutputSerializer(object):
    @staticmethod
    def serialize(output_dto, fields):  # type: (OutputDTO, Optional[List[str]]) -> Dict
        data = {'id': output_dto.id,
                'module_type': output_dto.module_type,
                'name': output_dto.name,
                'timer': Toolbox.denonify(output_dto.timer, 2 ** 16 - 1),
                'floor': Toolbox.denonify(output_dto.floor, 255),
                'type': Toolbox.denonify(output_dto.output_type, 255),
                'can_led_1_id': Toolbox.denonify(output_dto.can_led_1.id, 255),
                'can_led_1_function': output_dto.can_led_1.function,
                'can_led_2_id': Toolbox.denonify(output_dto.can_led_2.id, 255),
                'can_led_2_function': output_dto.can_led_2.function,
                'can_led_3_id': Toolbox.denonify(output_dto.can_led_3.id, 255),
                'can_led_3_function': output_dto.can_led_3.function,
                'can_led_4_id': Toolbox.denonify(output_dto.can_led_4.id, 255),
                'can_led_4_function': output_dto.can_led_4.function,
                'room': Toolbox.denonify(output_dto.room, 255)}
        if fields is None:
            return data
        return {field: data[field] for field in fields}

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> Tuple[OutputDTO, List[str]]
        loaded_fields = ['id']
        output_dto = OutputDTO(api_data['id'])
        for data_field, dto_field in {'module_type': 'module_type',
                                      'name': 'name',
                                      'type': 'output_type'}.iteritems():
            if data_field in api_data:
                loaded_fields.append(dto_field)
                setattr(output_dto, dto_field, api_data[data_field])
        for data_field, (dto_field, default) in {'timer': ('timer', 2 ** 16 - 1),
                                                 'floor': ('floor', 255),
                                                 'room': ('room', 255)}.iteritems():
            if data_field in api_data:
                loaded_fields.append(dto_field)
                setattr(output_dto, dto_field, Toolbox.nonify(api_data[data_field], default))
        for i in xrange(4):
            base_field = 'can_led_{0}'.format(i + 1)
            id_field = '{0}_id'.format(base_field)
            function_field = '{0}_function'.format(base_field)
            if id_field in api_data and function_field in api_data:
                loaded_fields.append(base_field)
                setattr(output_dto, base_field, FeedbackLedDTO(id=api_data[id_field],
                                                               function=api_data[function_field]))
        return output_dto, loaded_fields
