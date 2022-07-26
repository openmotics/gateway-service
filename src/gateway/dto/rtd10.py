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
RTD10 related DTO
"""

from collections import defaultdict
from gateway.dto.base import BaseDTO

if False:
    from typing import Dict, Optional


class GlobalRTD10DTO(BaseDTO):
    TEMPERATURES = [16.0, 16.5, 17.0, 17.5, 18.0, 18.5, 19.0, 19.5, 20.0, 20.5,
                    21.0, 21.5, 22.0, 22.5, 23.0, 23.5, 24.0]

    def __init__(self, heating_values=None, cooling_values=None):
        # type: (Optional[Dict[float, int]], Optional[Dict[float, int]]) -> None
        self.heating_values = defaultdict(lambda: 0)  # type: Dict[float, int]
        self.cooling_values = defaultdict(lambda: 0)  # type: Dict[float, int]
        if heating_values is not None:
            self.heating_values.update({i: heating_values[i]
                                        for i in GlobalRTD10DTO.TEMPERATURES
                                        if i in heating_values})
        if cooling_values is not None:
            self.cooling_values.update({i: cooling_values[i]
                                        for i in GlobalRTD10DTO.TEMPERATURES
                                        if i in cooling_values})


class RTD10DTO(BaseDTO):
    def __init__(self, id, temp_setpoint_output=None,
                 ventilation_speed_output=None, ventilation_speed_value=None,
                 mode_output=None, mode_value=None,
                 on_off_output=None, poke_angle_output=None, poke_angle_value=None, room=None):
        # type: (int, Optional[int], Optional[int], Optional[int], Optional[int], Optional[int], Optional[int], Optional[int], Optional[int], Optional[int]) -> None
        self.id = id
        self.temp_setpoint_output = temp_setpoint_output
        self.ventilation_speed_output = ventilation_speed_output
        self.ventilation_speed_value = ventilation_speed_value
        self.mode_output = mode_output
        self.mode_value = mode_value
        self.on_off_output = on_off_output
        self.poke_angle_output = poke_angle_output
        self.poke_angle_value = poke_angle_value
        self.room = room
