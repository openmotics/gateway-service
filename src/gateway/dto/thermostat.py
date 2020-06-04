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
HeatingThermostat DTO
"""

from gateway.dto.base import BaseDTO
from gateway.dto.thermostat_schedule import ThermostatScheduleDTO

if False:
    from typing import Optional


class ThermostatDTO(BaseDTO):
    def __init__(self, id,
                 name='', permanent_manual=False,
                 setp0=None, setp1=None, setp2=None, setp3=None, setp4=None, setp5=None,
                 sensor=None, output0=None, output1=None,
                 pid_p=None, pid_i=None, pid_d=None, pid_int=None,
                 room=None,
                 auto_mon=None, auto_tue=None, auto_wed=None, auto_thu=None, auto_fri=None, auto_sat=None, auto_sun=None):
        self.id = id  # type: int
        self.name = name  # type: str
        self.setp0 = setp0  # type: Optional[float]
        self.setp1 = setp1  # type: Optional[float]
        self.setp2 = setp2  # type: Optional[float]
        self.setp3 = setp3  # type: Optional[float]
        self.setp4 = setp4  # type: Optional[float]
        self.setp5 = setp5  # type: Optional[float]
        self.sensor = sensor  # type: Optional[int]
        self.output0 = output0  # type: Optional[int]
        self.output1 = output1  # type: Optional[int]
        self.pid_p = pid_p  # type: Optional[int]
        self.pid_i = pid_i  # type: Optional[int]
        self.pid_d = pid_d  # type: Optional[int]
        self.pid_int = pid_int  # type: Optional[int]
        self.permanent_manual = permanent_manual  # type: bool
        self.room = room  # type: Optional[int]
        self.auto_mon = auto_mon  # type: Optional[ThermostatScheduleDTO]
        self.auto_tue = auto_tue  # type: Optional[ThermostatScheduleDTO]
        self.auto_wed = auto_wed  # type: Optional[ThermostatScheduleDTO]
        self.auto_thu = auto_thu  # type: Optional[ThermostatScheduleDTO]
        self.auto_fri = auto_fri  # type: Optional[ThermostatScheduleDTO]
        self.auto_sat = auto_sat  # type: Optional[ThermostatScheduleDTO]
        self.auto_sun = auto_sun  # type: Optional[ThermostatScheduleDTO]

    @property
    def in_use(self):
        return (self.output0 is not None and
                self.output0 <= 240 and
                self.sensor is not None and
                (self.sensor <= 31 or self.sensor == 240))

    def __eq__(self, other):
        if not isinstance(other, ThermostatDTO):
            return False
        return (self.id == other.id and
                self.name == other.name and
                self.room == other.room and
                self.setp0 == other.setp0 and
                self.setp1 == other.setp1 and
                self.setp2 == other.setp2 and
                self.setp3 == other.setp3 and
                self.setp4 == other.setp4 and
                self.setp5 == other.setp5 and
                self.sensor == other.sensor and
                self.output0 == other.output0 and
                self.output1 == other.output1 and
                self.pid_p == other.pid_p and
                self.pid_i == other.pid_i and
                self.pid_d == other.pid_d and
                self.pid_int == other.pid_int and
                self.permanent_manual == other.permanent_manual and
                self.auto_mon == other.auto_mon and
                self.auto_tue == other.auto_tue and
                self.auto_wed == other.auto_wed and
                self.auto_thu == other.auto_thu and
                self.auto_fri == other.auto_fri and
                self.auto_sat == other.auto_sat and
                self.auto_sun == other.auto_sun)
