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


class ThermostatGroupDTO(BaseDTO):
    def __init__(self, id, outside_sensor_id=None, pump_delay=None, threshold_temperature=None,
                 switch_to_heating_0=None, switch_to_heating_1=None, switch_to_heating_2=None, switch_to_heating_3=None,
                 switch_to_cooling_0=None, switch_to_cooling_1=None, switch_to_cooling_2=None, switch_to_cooling_3=None):
        self.id = id  # type: int
        self.outside_sensor_id = outside_sensor_id  # type: Optional[int]
        self.pump_delay = pump_delay  # type: Optional[int]
        self.threshold_temperature = threshold_temperature  # type: Optional[float]
        self.switch_to_heating_0 = switch_to_heating_0  # type: Optional[Tuple[int, int]]
        self.switch_to_heating_1 = switch_to_heating_1  # type: Optional[Tuple[int, int]]
        self.switch_to_heating_2 = switch_to_heating_2  # type: Optional[Tuple[int, int]]
        self.switch_to_heating_3 = switch_to_heating_3  # type: Optional[Tuple[int, int]]
        self.switch_to_cooling_0 = switch_to_cooling_0  # type: Optional[Tuple[int, int]]
        self.switch_to_cooling_1 = switch_to_cooling_1  # type: Optional[Tuple[int, int]]
        self.switch_to_cooling_2 = switch_to_cooling_2  # type: Optional[Tuple[int, int]]
        self.switch_to_cooling_3 = switch_to_cooling_3  # type: Optional[Tuple[int, int]]

    def __eq__(self, other):
        if not isinstance(other, ThermostatGroupDTO):
            return False
        return (self.id == other.id and
                self.outside_sensor_id == other.outside_sensor_id and
                self.pump_delay == other.pump_delay and
                self.threshold_temperature == other.threshold_temperature and
                self.switch_to_heating_0 == other.switch_to_heating_0 and
                self.switch_to_heating_1 == other.switch_to_heating_1 and
                self.switch_to_heating_2 == other.switch_to_heating_2 and
                self.switch_to_heating_3 == other.switch_to_heating_3 and
                self.switch_to_cooling_0 == other.switch_to_cooling_0 and
                self.switch_to_cooling_1 == other.switch_to_cooling_1 and
                self.switch_to_cooling_2 == other.switch_to_cooling_2 and
                self.switch_to_cooling_3 == other.switch_to_cooling_3)


class ThermostatStatusDTO(BaseDTO):
    def __init__(self, id, actual_temperature, setpoint_temperature, automatic, setpoint, sensor_id, mode,
                 outside_temperature=None, name='', airco=None, output_0_level=None, output_1_level=None):
        # type: (int, float, float, bool, int, int, int, Optional[float], str, Optional[int], Optional[int], Optional[int]) -> None
        self.id = id
        self.actual_temperature = actual_temperature
        self.setpoint_temperature = setpoint_temperature
        self.automatic = automatic
        self.setpoint = setpoint
        self.sensor_id = sensor_id
        self.mode = mode
        self.outside_temperature = outside_temperature
        self.name = name
        self.airco = airco
        self.output_0_level = output_0_level
        self.output_1_level = output_1_level

    def __eq__(self, other):
        if not isinstance(other, ThermostatStatusDTO):
            return False
        return (self.id == other.id and
                self.actual_temperature == other.actual_temperature and
                self.setpoint_temperature == other.setpoint_temperature and
                self.automatic == other.automatic and
                self.setpoint == other.setpoint and
                self.sensor_id == other.sensor_id and
                self.mode == other.mode and
                self.outside_temperature == other.outside_temperature and
                self.name == other.name and
                self.airco == other.airco and
                self.output_0_level == other.output_0_level and
                self.output_1_level == other.output_1_level)


class ThermostatGroupStatusDTO(BaseDTO):
    def __init__(self, id, on, automatic, cooling, setpoint=None, statusses=None):
        # type: (int, bool, bool, bool, Optional[int], Optional[List[ThermostatStatusDTO]]) -> None
        self.id = id
        self.on = on
        self.automatic = automatic
        self.cooling = cooling
        self.setpoint = setpoint if setpoint is not None else 0  # type: int
        self.statusses = statusses if statusses is not None else []  # type: List[ThermostatStatusDTO]

    def __eq__(self, other):
        if not isinstance(other, ThermostatGroupStatusDTO):
            return False
        return (self.id == other.id and
                self.on == other.on and
                self.automatic == other.automatic and
                self.cooling == other.cooling and
                self.setpoint == other.setpoint and
                self.statusses == other.statusses)


class ThermostatAircoStatusDTO(BaseDTO):
    def __init__(self, status):
        # type: (Dict[int, bool]) -> None
        self.status = status

    def __eq__(self, other):
        if not isinstance(other, ThermostatAircoStatusDTO):
            return False
        return self.status == other.status


class PumpGroupDTO(BaseDTO):
    def __init__(self, id, pump_output_id=None, valve_output_ids=None, room_id=None):
        # type: (int, Optional[int], Optional[List[int]], Optional[int]) -> None
        self.id = id
        self.pump_output_id = pump_output_id
        self.valve_output_ids = valve_output_ids if valve_output_ids else []  # type: List[int]
        self.room_id = room_id

    def __eq__(self, other):
        if not isinstance(other, PumpGroupDTO):
            return False
        return (self.id == other.id and
                self.pump_output_id == other.pump_output_id and
                self.valve_output_ids == other.valve_output_ids and
                self.room_id == other.room_id)
