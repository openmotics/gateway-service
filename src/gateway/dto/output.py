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
from gateway.dto.feedback_led import FeedbackLedDTO

if False:  # MYPY
    from typing import Optional


class OutputDTO(object):
    def __init__(self, id, name='', module_type=None, timer=None, floor=None, output_type=None,
                 can_led_1=None,  # type: Optional[FeedbackLedDTO]
                 can_led_2=None,  # type: Optional[FeedbackLedDTO]
                 can_led_3=None,  # type: Optional[FeedbackLedDTO]
                 can_led_4=None,  # type: Optional[FeedbackLedDTO]
                 room=None):
        self.id = id  # type: int
        self.name = name  # type: str
        self.module_type = module_type  # type: str
        self.timer = timer  # type: Optional[int]
        self.floor = floor  # type: Optional[int]
        self.output_type = output_type  # type: int
        self.room = room  # type: Optional[int]
        self.can_led_1 = can_led_1 or FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
        self.can_led_2 = can_led_2 or FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
        self.can_led_3 = can_led_3 or FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
        self.can_led_4 = can_led_4 or FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN)
