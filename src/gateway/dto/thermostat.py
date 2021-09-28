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
    from typing import Optional, List, Tuple, Dict


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


class ThermostatGroupDTO(BaseDTO):
    def __init__(self, id, outside_sensor_id=None, pump_delay=None, threshold_temperature=None,
                 switch_to_heating_0=None, switch_to_heating_1=None, switch_to_heating_2=None, switch_to_heating_3=None,
                 switch_to_cooling_0=None, switch_to_cooling_1=None, switch_to_cooling_2=None, switch_to_cooling_3=None):
        self.id = id  # type: int
        self.outside_sensor_id = outside_sensor_id  # type: Optional[int]
        self.pump_delay = 60 if pump_delay in (None, 255) else pump_delay  # type: int
        self.threshold_temperature = threshold_temperature  # type: Optional[float]
        self.switch_to_heating_0 = switch_to_heating_0  # type: Optional[Tuple[int, int]]
        self.switch_to_heating_1 = switch_to_heating_1  # type: Optional[Tuple[int, int]]
        self.switch_to_heating_2 = switch_to_heating_2  # type: Optional[Tuple[int, int]]
        self.switch_to_heating_3 = switch_to_heating_3  # type: Optional[Tuple[int, int]]
        self.switch_to_cooling_0 = switch_to_cooling_0  # type: Optional[Tuple[int, int]]
        self.switch_to_cooling_1 = switch_to_cooling_1  # type: Optional[Tuple[int, int]]
        self.switch_to_cooling_2 = switch_to_cooling_2  # type: Optional[Tuple[int, int]]
        self.switch_to_cooling_3 = switch_to_cooling_3  # type: Optional[Tuple[int, int]]


class ThermostatStatusDTO(BaseDTO):
    def __init__(self, id, actual_temperature, setpoint_temperature, automatic, setpoint, mode,
                 outside_temperature=None, output_0_level=None, output_1_level=None):
        # type: (int, Optional[float], float, bool, int, int, Optional[float], Optional[int], Optional[int]) -> None
        self.id = id
        self.actual_temperature = actual_temperature
        self.setpoint_temperature = setpoint_temperature
        self.automatic = automatic
        self.setpoint = setpoint
        self.mode = mode
        self.outside_temperature = outside_temperature
        self.output_0_level = output_0_level
        self.output_1_level = output_1_level


class ThermostatGroupStatusDTO(BaseDTO):
    def __init__(self, id, on, automatic, cooling, setpoint=None, statusses=None):
        # type: (int, bool, bool, bool, Optional[int], Optional[List[ThermostatStatusDTO]]) -> None
        self.id = id
        self.on = on
        self.automatic = automatic
        self.cooling = cooling
        self.setpoint = setpoint if setpoint is not None else 0  # type: int
        self.statusses = statusses if statusses is not None else []  # type: List[ThermostatStatusDTO]


class ThermostatAircoStatusDTO(BaseDTO):
    def __init__(self, status):
        # type: (Dict[int, bool]) -> None
        self.status = status


class PumpGroupDTO(BaseDTO):
    def __init__(self, id, pump_output_id=None, valve_output_ids=None, room_id=None):
        # type: (int, Optional[int], Optional[List[int]], Optional[int]) -> None
        self.id = id
        self.pump_output_id = pump_output_id
        self.valve_output_ids = valve_output_ids if valve_output_ids else []  # type: List[int]
        self.room_id = room_id
