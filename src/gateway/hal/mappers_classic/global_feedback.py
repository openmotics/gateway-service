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
GlobalFeedback Mapper
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.dto import GlobalFeedbackDTO, FeedbackLedDTO
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import CanLedConfiguration

if False:  # MYPY
    from typing import List


class GlobalFeedbackMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> GlobalFeedbackDTO
        data = orm_object.serialize()
        return GlobalFeedbackDTO(id=data['id'],
                                 can_led_1=FeedbackLedDTO(id=Toolbox.nonify(data['can_led_1_id'], GlobalFeedbackMapper.BYTE_MAX),
                                                          function=data['can_led_1_function']),
                                 can_led_2=FeedbackLedDTO(id=Toolbox.nonify(data['can_led_2_id'], GlobalFeedbackMapper.BYTE_MAX),
                                                          function=data['can_led_2_function']),
                                 can_led_3=FeedbackLedDTO(id=Toolbox.nonify(data['can_led_3_id'], GlobalFeedbackMapper.BYTE_MAX),
                                                          function=data['can_led_3_function']),
                                 can_led_4=FeedbackLedDTO(id=Toolbox.nonify(data['can_led_4_id'], GlobalFeedbackMapper.BYTE_MAX),
                                                          function=data['can_led_4_function']))

    @staticmethod
    def dto_to_orm(global_feedback_dto, fields):  # type: (GlobalFeedbackDTO, List[str]) -> EepromModel
        data = {'id': global_feedback_dto.id}
        for i in range(4):
            base_field = 'can_led_{0}'.format(i + 1)
            if base_field in fields:
                id_field = '{0}_id'.format(base_field)
                function_field = '{0}_function'.format(base_field)
                data[id_field] = getattr(global_feedback_dto, base_field).id
                data[function_field] = getattr(global_feedback_dto, base_field).function
        return CanLedConfiguration.deserialize(data)
