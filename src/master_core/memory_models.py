# Copyright (C) 2019 OpenMotics BV
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
Memory models
"""
from master_core.memory_file import MemoryTypes
from master_core.memory_types import (MemoryModelDefinition, GlobalMemoryModelDefinition,
                                      MemoryRelation,
                                      MemoryByteField, MemoryWordField, MemoryAddressField, MemoryStringField, MemoryVersionField, MemoryBasicActionField,
                                      MemoryByteArrayField, Memory3BytesField,
                                      CompositeMemoryModelDefinition, CompositeNumberField, CompositeBitField)

if False:  # MYPY
    from typing import Union


class GlobalConfiguration(GlobalMemoryModelDefinition):
    number_of_output_modules = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 1))  # 0, 1
    number_of_input_modules = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 2))  # 0, 1
    number_of_sensor_modules = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 3))  # 0, 3
    scan_time_rs485_sensor_modules = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 4))  # 0, 4
    number_of_can_inputs = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 5))  # 0, 5
    number_of_can_sensors = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 6))  # 0, 6
    number_of_ucan_modules = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 7))  # 0, 7
    scan_time_rs485_bus = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 8))  # 0, 8
    number_of_can_control_modules = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 9))  # 0, 9
    scan_time_rs485_can_control_modules = MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 10))  # 0, 10
    groupaction_all_outputs_off = MemoryWordField(MemoryTypes.EEPROM, address_spec=(0, 50))  # 0, 50-51
    groupaction_startup = MemoryWordField(MemoryTypes.EEPROM, address_spec=(0, 52))  # 0, 52-53
    groupaction_minutes_changed = MemoryWordField(MemoryTypes.EEPROM, address_spec=(0, 54))  # 0, 54-55
    groupaction_hours_changed = MemoryWordField(MemoryTypes.EEPROM, address_spec=(0, 56))  # 0, 56-57
    groupaction_day_changed = MemoryWordField(MemoryTypes.EEPROM, address_spec=(0, 58))  # 0, 58-59
    startup_time = MemoryByteArrayField(MemoryTypes.FRAM, address_spec=(0, 64), length=3)  # 0, 64-66
    startup_date = MemoryByteArrayField(MemoryTypes.FRAM, address_spec=(0, 67), length=3)  # 0, 67-69
    uptime_hours = Memory3BytesField(MemoryTypes.FRAM, address_spec=(0, 70))  # 0, 70-72


class OutputModuleConfiguration(MemoryModelDefinition):
    class _ShutterComposition(CompositeMemoryModelDefinition):
        set_01_direction = CompositeBitField(bit=0)  # True means 0 is down, 1 is up. False means the opposite
        set_23_direction = CompositeBitField(bit=1)
        set_45_direction = CompositeBitField(bit=2)
        set_67_direction = CompositeBitField(bit=3)
        are_01_outputs = CompositeBitField(bit=4)  # True means "output", False means "shutter"
        are_23_outputs = CompositeBitField(bit=5)
        are_45_outputs = CompositeBitField(bit=6)
        are_67_outputs = CompositeBitField(bit=7)

    device_type = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id, 0), length=1)  # 1-80, 0-3
    address = MemoryAddressField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id, 0))  # 1-80, 0-3
    firmware_version = MemoryVersionField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id, 4))  # 1-80, 4-6
    shutter_config = _ShutterComposition(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (392, id)))  # 392, 0-79


class OutputConfiguration(MemoryModelDefinition):
    class _DALIOutputComposition(CompositeMemoryModelDefinition):
        dali_output_id = CompositeNumberField(start_bit=0, width=8, max_value=63)
        dali_group_id = CompositeNumberField(start_bit=0, width=8, max_value=15, value_offset=64)

    module = MemoryRelation(OutputModuleConfiguration, id_spec=lambda id: id / 8)  # type: Union[MemoryRelation, OutputModuleConfiguration]
    timer_value = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id / 8, 7 + id % 8))  # 1-80, 7-22
    timer_type = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id / 8, 23 + id % 8))  # 1-80, 23-30
    output_type = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id / 8, 31 + id % 8))  # 1-80, 31-38
    min_output_level = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id / 8, 39 + id % 8))  # 1-80, 39-46
    max_output_level = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id / 8, 47 + id % 8))  # 1-80, 47-54
    output_groupaction_follow = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id / 8, 55 + (id % 8) * 2))  # 1-80, 55-70
    dali_mapping = _DALIOutputComposition(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id / 8, 71 + id % 8)))  # 1-80, 71-78
    name = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (1 + id / 8, 128 + (id % 8) * 16), length=16)  # 1-80, 128-255

    @property
    def is_shutter(self):
        group = self.id % 8 / 2
        return not getattr(self.module.shutter_config, 'are_{0}_outputs'.format(['01', '23', '45', '67'][group]))


class InputModuleConfiguration(MemoryModelDefinition):
    device_type = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (81 + id * 2, 0), length=1)  # 81-238, 0-3
    address = MemoryAddressField(MemoryTypes.EEPROM, address_spec=lambda id: (81 + id * 2, 0))  # 81-238, 0-3
    firmware_version = MemoryVersionField(MemoryTypes.EEPROM, address_spec=lambda id: (81 + id * 2, 4))  # 81-238, 4-6


class InputConfiguration(MemoryModelDefinition):
    class _InputConfigComposition(CompositeMemoryModelDefinition):
        normal_open = CompositeBitField(bit=1)

    class _DALIInputComposition(CompositeMemoryModelDefinition):
        lunatone_input_id = CompositeNumberField(start_bit=0, width=8, max_value=63)
        helvar_input_id = CompositeNumberField(start_bit=0, width=8, max_value=63, value_offset=64)

    class _InputLink(CompositeMemoryModelDefinition):
        output_id = CompositeNumberField(start_bit=0, width=10)
        enable_specific_actions = CompositeBitField(bit=10)
        dimming_up = CompositeBitField(bit=11)
        enable_1s_press = CompositeBitField(bit=12)
        enable_2s_press = CompositeBitField(bit=13)
        enable_double_press = CompositeBitField(bit=15)

    module = MemoryRelation(InputModuleConfiguration, id_spec=lambda id: id / 8)  # type: Union[MemoryRelation, InputModuleConfiguration]
    input_config = _InputConfigComposition(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (81 + id * 2, 7 + id)))  # 81-238, 7-14
    dali_mapping = _DALIInputComposition(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (81 + id * 2, 15 + id % 8)))  # 81-238, 15-22
    name = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (81 + id * 2, 128 + id * 16), length=16)  # 81-238, 128-255
    input_link = _InputLink(field=MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (82 + id * 2, id % 8 * 2)))  # 81-238, 0-15
    basic_action_press = MemoryBasicActionField(MemoryTypes.EEPROM, address_spec=lambda id: (82 + id * 2, 16 + id % 8))  # 81-238, 16-63
    basic_action_release = MemoryBasicActionField(MemoryTypes.EEPROM, address_spec=lambda id: (82 + id % 2, 64 + id % 8))  # 81-238, 64-111
    basic_action_1s_press = MemoryBasicActionField(MemoryTypes.EEPROM, address_spec=lambda id: (82 + id % 2, 112 + id % 8))  # 81-238, 112-159
    basic_action_2s_press = MemoryBasicActionField(MemoryTypes.EEPROM, address_spec=lambda id: (82 + id % 2, 160 + id % 8))  # 81-238, 160-207
    basic_action_double_press = MemoryBasicActionField(MemoryTypes.EEPROM, address_spec=lambda id: (82 + id % 2, 208 + id % 8))  # 81-238, 208-255


class SensorModuleConfiguration(MemoryModelDefinition):
    device_type = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (239 + id, 0), length=1)  # 239-254, 0-3
    address = MemoryAddressField(MemoryTypes.EEPROM, address_spec=lambda id: (239 + id, 0))  # 239-254, 0-3
    firmware_version = MemoryVersionField(MemoryTypes.EEPROM, address_spec=lambda id: (239 + id, 4))  # 239-254, 4-6


class SensorConfiguration(MemoryModelDefinition):
    class _DALISensorComposition(CompositeMemoryModelDefinition):
        dali_output_id = CompositeNumberField(start_bit=0, width=8, max_value=63)
        dali_group_id = CompositeNumberField(start_bit=0, width=8, max_value=15, value_offset=64)

    module = MemoryRelation(SensorModuleConfiguration, id_spec=lambda id: id / 8)  # type: Union[MemoryRelation, SensorModuleConfiguration]
    temperature_groupaction_follow = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (239 + id / 8, 8 + (id % 8) * 2))  # 239-254, 8-23
    humidity_groupaction_follow = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (239 + id / 8, 24 + (id % 8) * 2))  # 239-254, 24-39
    brightness_groupaction_follow = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (239 + id / 8, 40 + (id % 8) * 2))  # 239-254, 40-55
    aqi_groupaction_follow = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (239 + id / 8, 56 + (id % 8) * 2))  # 239-254, 56-71
    dali_mapping = _DALISensorComposition(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (239 + id / 8, 72 + (id % 8))))  # 239-254, 72-79
    name = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (239 + id / 8, 128 + id * 16), length=16)  # 239-254, 128-255


class ShutterConfiguration(MemoryModelDefinition):
    class _OutputMappingComposition(CompositeMemoryModelDefinition):
        output_0 = CompositeNumberField(start_bit=0, width=8, value_factor=2)
        output_1 = CompositeNumberField(start_bit=0, width=8, value_offset=-1, value_factor=2)

    class _ShutterGroupMembershipComposition(CompositeMemoryModelDefinition):
        group_0 = CompositeBitField(bit=0)
        group_1 = CompositeBitField(bit=1)
        group_2 = CompositeBitField(bit=2)
        group_3 = CompositeBitField(bit=3)
        group_4 = CompositeBitField(bit=4)
        group_5 = CompositeBitField(bit=5)
        group_6 = CompositeBitField(bit=6)
        group_7 = CompositeBitField(bit=7)
        group_8 = CompositeBitField(bit=8)
        group_9 = CompositeBitField(bit=9)
        group_10 = CompositeBitField(bit=10)
        group_11 = CompositeBitField(bit=11)
        group_12 = CompositeBitField(bit=12)
        group_13 = CompositeBitField(bit=13)
        group_14 = CompositeBitField(bit=14)
        group_15 = CompositeBitField(bit=15)

    outputs = _OutputMappingComposition(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (391, id)))  # 391, 0-255
    timer_up = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (393 + id / 128, id % 128 * 2))  # 393-394, 0-255
    timer_down = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (395 + id / 128, id % 128 * 2))  # 395-396, 0-255
    name = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (397 + id / 16, id % 16 * 16), length=16)  # 397-412, 0-255
    groups = _ShutterGroupMembershipComposition(field=MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (413 + id / 128, id % 128 * 2)))  # 413-414, 0-255


class CanControlModuleConfiguration(MemoryModelDefinition):
    device_type = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (255, id * 16), length=1)  # 255, 0-255
    address = MemoryAddressField(MemoryTypes.EEPROM, address_spec=lambda id: (255, id * 16))  # 255, 0-255


class ExtraSensorConfiguration(MemoryModelDefinition):
    grouaction_changed = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (471, id * 2))  # 471, 0-255
    name = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (476 + id / 16, (id % 16) * 16), length=16)  # 472-479, 0-255


class ValidationBitConfiguration(MemoryModelDefinition):
    grouaction_changed = MemoryWordField(MemoryTypes.EEPROM, address_spec=lambda id: (480 + id / 127, (id % 127) * 2))  # 480-481, 0-255
    name = MemoryStringField(MemoryTypes.EEPROM, address_spec=lambda id: (482 + id / 16, (id % 16) * 16), length=16)  # 482-497, 0-255
