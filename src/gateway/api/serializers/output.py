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
from gateway.dto.output import OutputDTO

if False:  # Mypy
    from typing import Dict, Optional, List


class OutputSerializer(object):
    @staticmethod
    def serialize_v0(output_dto, fields):  # type: (OutputDTO, Optional[List[str]]) -> Dict
        data = {'id': output_dto.id,
                'module_type': output_dto.module_type,
                'name': output_dto.name,
                'timer': OutputDTO._denonify(output_dto.timer, 2 ** 16 - 1),
                'floor': OutputDTO._denonify(output_dto.floor, 255),
                'type': output_dto.output_type,
                'can_led_1_id': output_dto.can_led_1.id,
                'can_led_1_function': output_dto.can_led_1.function,
                'can_led_2_id': output_dto.can_led_2.id,
                'can_led_2_function': output_dto.can_led_2.function,
                'can_led_3_id': output_dto.can_led_3.id,
                'can_led_3_function': output_dto.can_led_3.function,
                'can_led_4_id': output_dto.can_led_4.id,
                'can_led_4_function': output_dto.can_led_4.function,
                'room': OutputDTO._denonify(output_dto.room, 255)}
        if fields is None:
            return data
        return {field: data[field] for field in fields}
