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
ThermostatSchedule DTO
"""
from gateway.dto.base import BaseDTO, capture_fields

if False:  # MYPY
    from typing import Optional


class ThermostatScheduleDTO(BaseDTO):
    @capture_fields
    def __init__(self,
                 temp_night, temp_day_1, temp_day_2,
                 start_day_1, end_day_1,
                 start_day_2, end_day_2):
        self.temp_night = float(temp_night) if temp_night is not None else temp_night  # type: Optional[float]
        self.temp_day_1 = float(temp_day_1) if temp_day_1 is not None else temp_day_1  # type: Optional[float]
        self.temp_day_2 = float(temp_day_2) if temp_day_2 is not None else temp_day_2  # type: Optional[float]
        self.start_day_1 = start_day_1  # type: str
        self.end_day_1 = end_day_1  # type: str
        self.start_day_2 = start_day_2  # type: str
        self.end_day_2 = end_day_2  # type: str
