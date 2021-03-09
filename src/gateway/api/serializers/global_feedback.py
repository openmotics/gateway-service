# Copyright (C) 2021 OpenMotics BV
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
GlobalFeedback (de)serializer
"""
from __future__ import absolute_import

from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import FeedbackLedDTO, GlobalFeedbackDTO
from toolbox import Toolbox

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple


class GlobalFeedbackSerializer(object):
    BYTE_MAX = 255

    @staticmethod
    def serialize(global_feedback_dto, fields):  # type: (GlobalFeedbackDTO, Optional[List[str]]) -> Dict
        data = {'id': global_feedback_dto.id,
                'can_led_1_id': Toolbox.denonify(global_feedback_dto.can_led_1.id, GlobalFeedbackSerializer.BYTE_MAX),
                'can_led_1_function': global_feedback_dto.can_led_1.function,
                'can_led_2_id': Toolbox.denonify(global_feedback_dto.can_led_2.id, GlobalFeedbackSerializer.BYTE_MAX),
                'can_led_2_function': global_feedback_dto.can_led_2.function,
                'can_led_3_id': Toolbox.denonify(global_feedback_dto.can_led_3.id, GlobalFeedbackSerializer.BYTE_MAX),
                'can_led_3_function': global_feedback_dto.can_led_3.function,
                'can_led_4_id': Toolbox.denonify(global_feedback_dto.can_led_4.id, GlobalFeedbackSerializer.BYTE_MAX),
                'can_led_4_function': global_feedback_dto.can_led_4.function}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):  # type: (Dict) -> Tuple[GlobalFeedbackDTO, List[str]]
        loaded_fields = ['id']
        global_feedback_dto = GlobalFeedbackDTO(api_data['id'])
        for i in range(4):
            base_field = 'can_led_{0}'.format(i + 1)
            id_field = '{0}_id'.format(base_field)
            function_field = '{0}_function'.format(base_field)
            if id_field in api_data and function_field in api_data:
                loaded_fields.append(base_field)
                setattr(global_feedback_dto, base_field, FeedbackLedDTO(id=Toolbox.nonify(api_data[id_field], GlobalFeedbackSerializer.BYTE_MAX),
                                                                        function=api_data[function_field]))
        return global_feedback_dto, loaded_fields
