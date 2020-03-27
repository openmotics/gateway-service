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
Output DTO
"""

from gateway.dto.base_dto import BaseDTO
from gateway.dto.feedback_led import FeedbackLedDTO


class OutputDTO(BaseDTO):
    id = None  # type: int
    name = ''  # type: str
    module_type = None  # type: None or int
    timer = None  # type: None or int
    floor = None  # type: None or int
    output_type = None  # type: None or int
    can_led_1 = FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
    can_led_2 = FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
    can_led_3 = FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
    can_led_4 = FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
    room = None  # type: None or int

    def __init__(self, id, **kwargs):
        self.id = id
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    @staticmethod
    def read_from_core_orm(core_object):
        timer = 0
        if core_object.timer_type == 2:
            timer = core_object.timer_value
        elif core_object.timer_type == 1:
            timer = core_object.timer_value / 10.0
        return OutputDTO(id=core_object.id,
                         name=core_object.name,
                         module_type=core_object.module.device_type,  # TODO: Proper translation
                         timer=timer,  # TODO: Proper calculation
                         output_type=core_object.output_type)  # TODO: Proper translation

    @staticmethod
    def read_from_classic_orm(classic_object):
        data = classic_object.serialize()
        return OutputDTO(id=data['id'],
                         module_type=data['module_type'],
                         name=data['name'],
                         timer=OutputDTO._nonify(data['timer'], 2 ** 16 - 1),
                         floor=OutputDTO._nonify(data['floor'], 255),
                         output_type=data['type'],
                         room=OutputDTO._nonify(data['room'], 255),
                         can_led_1=FeedbackLedDTO(id=OutputDTO._nonify(data['can_led_1_id'], 255),
                                                  function=data['can_led_1_function']),
                         can_led_2=FeedbackLedDTO(id=OutputDTO._nonify(data['can_led_2_id'], 255),
                                                  function=data['can_led_2_function']),
                         can_led_3=FeedbackLedDTO(id=OutputDTO._nonify(data['can_led_3_id'], 255),
                                                  function=data['can_led_3_function']),
                         can_led_4=FeedbackLedDTO(id=OutputDTO._nonify(data['can_led_4_id'], 255),
                                                  function=data['can_led_4_function']))
