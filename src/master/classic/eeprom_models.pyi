# Copyright (C) 2016 OpenMotics BV
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
Eeprom models MyPy stub
"""

from typing import List, Optional, Any
from master.classic.eeprom_controller import EepromModel


class FloorConfiguration(EepromModel):
    id: int
    name: str


class RoomConfiguration(EepromModel):
    id: int
    name: str
    floor: int


class OutputConfiguration(EepromModel):
    id: int
    module_type: str
    name: str
    timer: int
    floor: int
    type: int
    can_led_1_id: int
    can_led_1_function: str
    can_led_2_id: int
    can_led_2_function: str
    can_led_3_id: int
    can_led_3_function: str
    can_led_4_id: int
    can_led_4_function: str
    room: int


class InputConfiguration(EepromModel):
    id: int
    module_type: str
    name: str
    action: int
    basic_actions: List[int]
    invert: int
    room: int
    can: str
    event_enabled: bool


class CanLedConfiguration(EepromModel):
    id: int
    can_led_1_id: int
    can_led_1_function: str
    can_led_2_id: int
    can_led_2_function: str
    can_led_3_id: int
    can_led_3_function: str
    can_led_4_id: int
    can_led_4_function: str
    room: int


class ShutterConfiguration(EepromModel):
    id: int
    timer_up: int
    timer_down: int
    up_down_config: int
    name: str
    group_1: int
    group_2: int
    room: int
    steps: int


class ShutterGroupConfiguration(EepromModel):
    id: int
    timer_up: int
    timer_down: int
    room: int


class ThermostatConfiguration(EepromModel):
    id: int
    name: str
    setp0: Optional[float]
    setp1: Optional[float]
    setp2: Optional[float]
    setp3: Optional[float]
    setp4: Optional[float]
    setp5: Optional[float]
    sensor: int
    output0: int
    output1: int
    pid_p: int
    pid_i: int
    pid_d: int
    pid_int: int
    permanent_manual: bool
    auto_mon: List[Any]
    auto_tue = List[Any]
    auto_wed = List[Any]
    auto_thu = List[Any]
    auto_fri = List[Any]
    auto_sat = List[Any]
    auto_sun = List[Any]
    room: int


class PumpGroupConfiguration(EepromModel):
    id: int
    outputs = List[int]
    output: int
    room: int


class CoolingConfiguration(EepromModel):
    id: int
    name: str
    setp0: Optional[float]
    setp1: Optional[float]
    setp2: Optional[float]
    setp3: Optional[float]
    setp4: Optional[float]
    setp5: Optional[float]
    sensor: int
    output0: int
    output1: int
    pid_p: int
    pid_i: int
    pid_d: int
    pid_int: int
    permanent_manual: bool
    auto_mon = List[Any]
    auto_tue = List[Any]
    auto_wed = List[Any]
    auto_thu = List[Any]
    auto_fri = List[Any]
    auto_sat = List[Any]
    auto_sun = List[Any]
    room: int


class CoolingPumpGroupConfiguration(EepromModel):
    id: int
    outputs = List[int]
    output: int
    room: int


class RTD10HeatingConfiguration(EepromModel):
    id: int
    temp_setpoint_output: int
    ventilation_speed_output: int
    ventilation_speed_value: int
    mode_output: int
    mode_value: int
    on_off_output: int
    poke_angle_output: int
    poke_angle_value: int
    room: int


class RTD10CoolingConfiguration(EepromModel):
    id: int
    temp_setpoint_output: int
    ventilation_speed_output: int
    ventilation_speed_value: int
    mode_output: int
    mode_value: int
    on_off_output: int
    poke_angle_output: int
    poke_angle_value: int
    room: int


class GlobalRTD10Configuration(EepromModel):
    output_value_heating_16: int
    output_value_heating_16_5: int
    output_value_heating_17: int
    output_value_heating_17_5: int
    output_value_heating_18: int
    output_value_heating_18_5: int
    output_value_heating_19: int
    output_value_heating_19_5: int
    output_value_heating_20: int
    output_value_heating_20_5: int
    output_value_heating_21: int
    output_value_heating_21_5: int
    output_value_heating_22: int
    output_value_heating_22_5: int
    output_value_heating_23: int
    output_value_heating_23_5: int
    output_value_heating_24: int
    output_value_cooling_16: int
    output_value_cooling_16_5: int
    output_value_cooling_17: int
    output_value_cooling_17_5: int
    output_value_cooling_18: int
    output_value_cooling_18_5: int
    output_value_cooling_19: int
    output_value_cooling_19_5: int
    output_value_cooling_20: int
    output_value_cooling_20_5: int
    output_value_cooling_21: int
    output_value_cooling_21_5: int
    output_value_cooling_22: int
    output_value_cooling_22_5: int
    output_value_cooling_23: int
    output_value_cooling_23_5: int
    output_value_cooling_24: int


class SensorConfiguration(EepromModel):
    id: int
    name: str
    offset: Optional[float]
    virtual: bool
    room: int


class GroupActionConfiguration(EepromModel):
    id: int
    name: str
    actions: List[int]


class ScheduledActionConfiguration(EepromModel):
    id: int
    hour: int
    minute: int
    day: int
    action: List[int]


class PulseCounterConfiguration(EepromModel):
    id: int
    name: str
    input: int
    room: int


class StartupActionConfiguration(EepromModel):
    actions: List[int]


class DimmerConfiguration(EepromModel):
    min_dim_level: int
    dim_step: int
    dim_wait_cycle: int
    dim_memory: int


class GlobalThermostatConfiguration(EepromModel):
    outside_sensor: int
    threshold_temp: Optional[float]
    pump_delay: int
    switch_to_heating_output_0: int
    switch_to_heating_value_0: int
    switch_to_heating_output_1: int
    switch_to_heating_value_1: int
    switch_to_heating_output_2: int
    switch_to_heating_value_2: int
    switch_to_heating_output_3: int
    switch_to_heating_value_3: int
    switch_to_cooling_output_0: int
    switch_to_cooling_value_0: int
    switch_to_cooling_output_1: int
    switch_to_cooling_value_1: int
    switch_to_cooling_output_2: int
    switch_to_cooling_value_2: int
    switch_to_cooling_output_3: int
    switch_to_cooling_value_3: int


class ModuleConfiguration(EepromModel):
    nr_input_modules: int
    nr_output_modules: int
    enable_thermostat_16: int


class CliConfiguration(EepromModel):
    auto_response: int
    auto_response_OL: int
    echo: int
    start_cli_api: int
    auto_init: int
