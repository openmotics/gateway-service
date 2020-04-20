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
Memory models MyPy stub
"""
from typing import List

from master_core.basic_action import BasicAction
from master_core.memory_types import MemoryModelDefinition, GlobalMemoryModelDefinition, CompositeMemoryModelDefinition


class GlobalConfiguration(GlobalMemoryModelDefinition):
    number_of_output_modules: int
    number_of_input_modules: int
    number_of_sensor_modules: int
    scan_time_rs485_sensor_modules: int
    number_of_can_inputs: int
    number_of_can_sensors: int
    number_of_ucan_modules: int
    scan_time_rs485_bus: int
    number_of_can_control_modules: int
    scan_time_rs485_can_control_modules: int
    groupaction_all_outputs_off: int
    groupaction_startup: int
    groupaction_minutes_changed: int
    groupaction_hours_changed: int
    groupaction_day_changed: int
    startup_time: List[int]
    startup_date: List[int]
    uptime_hours: int


class OutputModuleConfiguration(MemoryModelDefinition):
    class _ShutterComposition(CompositeMemoryModelDefinition):
        set_01_direction: bool
        set_23_direction: bool
        set_45_direction: bool
        set_67_direction: bool
        are_01_outputs: bool
        are_23_outputs: bool
        are_45_outputs: bool
        are_67_outputs: bool

    device_type: str
    address: str
    firmware_version: str
    shutter_config: _ShutterComposition


class OutputConfiguration(MemoryModelDefinition):
    class _DALIOutputComposition(CompositeMemoryModelDefinition):
        dali_output_id: int
        dali_group_id: int

    module: OutputModuleConfiguration
    timer_value: int
    timer_type: int
    output_type: int
    min_output_level: int
    max_output_level: int
    output_groupaction_follow: int
    dali_mapping: _DALIOutputComposition
    name: str

    @property
    def is_shutter(self) -> bool: ...


class InputModuleConfiguration(MemoryModelDefinition):
    device_type: str
    address: str
    firmware_version: str


class InputConfiguration(MemoryModelDefinition):
    class _InputConfigComposition(CompositeMemoryModelDefinition):
        normal_open: bool

    class _DALIInputComposition(CompositeMemoryModelDefinition):
        lunatone_input_id: int
        helvar_input_id: int

    class _InputLink(CompositeMemoryModelDefinition):
        output_id: int
        enable_specific_actions: bool
        dimming_up: bool
        enable_1s_press: bool
        enable_2s_press: bool
        enable_double_press: bool

    module: InputModuleConfiguration
    input_config: _InputConfigComposition
    dali_mapping: _DALIInputComposition
    name: str
    input_link: _InputLink
    basic_action_press: BasicAction
    basic_action_release: BasicAction
    basic_action_1s_press: BasicAction
    basic_action_2s_press: BasicAction
    basic_action_double_press: BasicAction


class SensorModuleConfiguration(MemoryModelDefinition):
    device_type: str
    address: str
    firmware_version: str


class SensorConfiguration(MemoryModelDefinition):
    class _DALISensorComposition(CompositeMemoryModelDefinition):
        dali_output_id: int
        dali_group_id: int

    module: SensorModuleConfiguration
    temperature_groupaction_follow: int
    humidity_groupaction_follow: int
    brightness_groupaction_follow: int
    aqi_groupaction_follow: int
    dali_mapping: _DALISensorComposition
    name: str


class ShutterConfiguration(MemoryModelDefinition):
    class _OutputMappingComposition(CompositeMemoryModelDefinition):
        output_0: int
        output_1: int

    class _ShutterGroupMembershipComposition(CompositeMemoryModelDefinition):
        group_0: bool
        group_1: bool
        group_2: bool
        group_3: bool
        group_4: bool
        group_5: bool
        group_6: bool
        group_7: bool
        group_8: bool
        group_9: bool
        group_10: bool
        group_11: bool
        group_12: bool
        group_13: bool
        group_14: bool
        group_15: bool

    outputs: _OutputMappingComposition
    timer_up: int
    timer_down: int
    name: str
    groups: _ShutterGroupMembershipComposition

    @property
    def output_set(self) -> str: ...


class CanControlModuleConfiguration(MemoryModelDefinition):
    device_type: str
    address: str


class ExtraSensorConfiguration(MemoryModelDefinition):
    grouaction_changed: int
    name: str


class ValidationBitConfiguration(MemoryModelDefinition):
    grouaction_changed: int
    name: str
