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
Module for communicating with the Master
"""
from __future__ import absolute_import

from gateway.dto import DimmerConfigurationDTO, GlobalFeedbackDTO, \
    GroupActionDTO, InputDTO, LegacyScheduleDTO, LegacyStartupActionDTO, \
    MasterSensorDTO, ModuleDTO, OutputDTO, OutputStatusDTO, PulseCounterDTO, \
    SensorDTO, ShutterDTO, ShutterGroupDTO, ThermostatAircoStatusDTO, \
    ThermostatDTO, ThermostatGroupDTO, ModuleDTO, GlobalFeedbackDTO, \
    OutputStatusDTO, LegacyStartupActionDTO, LegacyScheduleDTO, \
    DimmerConfigurationDTO, InputStatusDTO


if False:  # MYPY
    from typing import Any, Dict, List, Literal, Optional, Tuple

    HEALTH = Literal['success', 'unstable', 'failure']


class MasterController(object):

    def __init__(self, master_communicator):
        self._master_communicator = master_communicator

    #######################
    # Internal management #
    #######################

    def start(self):
        self._master_communicator.start()

    def stop(self):
        self._master_communicator.stop()

    def set_plugin_controller(self, plugin_controller):
        raise NotImplementedError()

    ##############
    # Public API #
    ##############

    def get_command_histograms(self):
        return self._master_communicator.get_command_histograms()

    def get_communication_statistics(self):
        return self._master_communicator.get_communication_statistics()

    def get_communicator_health(self):
        # type: () -> HEALTH
        raise NotImplementedError()

    def get_debug_buffer(self):
        return self._master_communicator.get_debug_buffer()

    # TODO: Currently the objects returned here are classic-format dicts. This needs to be changed to intermediate transport objects

    def get_master_online(self):
        # type: () -> bool
        raise NotImplementedError()

    def get_firmware_version(self):
        raise NotImplementedError()

    # Input

    def set_input(self, input_id, state):
        raise NotImplementedError()

    def get_input_module_type(self, input_module_id):
        raise NotImplementedError()

    def load_input(self, input_id):  # type: (int) -> InputDTO
        raise NotImplementedError()

    def load_inputs(self):  # type: () -> List[InputDTO]
        raise NotImplementedError()

    def save_inputs(self, inputs):  # type: (List[InputDTO]) -> None
        raise NotImplementedError()

    def load_input_status(self):
        # type: () -> List[InputStatusDTO]
        raise NotImplementedError()

    # Outputs

    def set_output(self, output_id, state, dimmer=None, timer=None):
        raise NotImplementedError()

    def toggle_output(self, output_id):
        raise NotImplementedError()

    def load_output(self, output_id):  # type: (int) -> OutputDTO
        raise NotImplementedError()

    def load_outputs(self):  # type: () -> List[OutputDTO]
        raise NotImplementedError()

    def save_outputs(self, outputs):  # type: (List[OutputDTO]) -> None
        raise NotImplementedError()

    def load_output_status(self):
        # type: () -> List[OutputStatusDTO]
        raise NotImplementedError()

    # Shutters

    def shutter_up(self, shutter_id, timer=None):
        raise NotImplementedError()

    def shutter_down(self, shutter_id, timer=None):
        raise NotImplementedError()

    def shutter_stop(self, shutter_id):
        raise NotImplementedError()

    def load_shutter(self, shutter_id):  # type: (int) -> ShutterDTO
        raise NotImplementedError()

    def load_shutters(self):  # type: () -> List[ShutterDTO]
        raise NotImplementedError()

    def save_shutters(self, config):  # type: (List[ShutterDTO]) -> None
        raise NotImplementedError()

    def shutter_group_down(self, group_id):
        raise NotImplementedError()

    def shutter_group_up(self, group_id):
        raise NotImplementedError()

    def shutter_group_stop(self, group_id):
        raise NotImplementedError()

    def load_shutter_group(self, shutter_group_id):  # type: (int) -> ShutterGroupDTO
        raise NotImplementedError()

    def load_shutter_groups(self):  # type: () -> List[ShutterGroupDTO]
        raise NotImplementedError()

    def save_shutter_groups(self, config):  # type: (List[ShutterGroupDTO]) -> None
        raise NotImplementedError()

    # Thermostats

    def set_thermostat_mode(self, mode):
        # type: (int) -> None
        raise NotImplementedError()

    def set_thermostat_cooling_heating(self, mode):
        # type: (int) -> None
        raise NotImplementedError()

    def set_thermostat_automatic(self, action_number):
        # type: (int) -> None
        raise NotImplementedError()

    def set_thermostat_all_setpoints(self, setpoint):
        # type: (int) -> None
        raise NotImplementedError()

    def write_thermostat_setpoint(self, thermostat_id, temperature):
        # type: (int, float) -> None
        raise NotImplementedError()

    def set_thermostat_setpoint(self, thermostat_id, setpoint):
        # type: (int, int) -> None
        raise NotImplementedError()

    def set_thermostat_tenant_auto(self, thermostat_id):
        # type: (int) -> None
        raise NotImplementedError()

    def get_thermostats(self):
        # type: () -> Dict[str,Any]
        raise NotImplementedError()

    def get_thermostat_modes(self):
        # type: () -> Dict[str,Any]
        raise NotImplementedError()

    def load_airco_status(self):
        # type: () -> ThermostatAircoStatusDTO
        raise NotImplementedError()

    def set_airco_status(self, thermostat_id, airco_on):
        # type: (int, bool) -> None
        raise NotImplementedError()

    def set_thermostat_tenant_manual(self, thermostat_id):
        # type: (int) -> None
        raise NotImplementedError()

    def load_heating_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        raise NotImplementedError()

    def load_heating_thermostats(self):  # type: () -> List[ThermostatDTO]
        raise NotImplementedError()

    def save_heating_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        raise NotImplementedError()

    def load_cooling_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        raise NotImplementedError()

    def load_cooling_thermostats(self):  # type: () -> List[ThermostatDTO]
        raise NotImplementedError()

    def save_cooling_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        raise NotImplementedError()

    def get_cooling_pump_group_configuration(self, pump_group_id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str,Any]
        raise NotImplementedError()

    def get_cooling_pump_group_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        raise NotImplementedError()

    def set_cooling_pump_group_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        raise NotImplementedError()

    def set_cooling_pump_group_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        raise NotImplementedError()

    def get_global_rtd10_configuration(self, fields=None):
        # type: (Optional[List[str]]) -> Dict[str,Any]
        raise NotImplementedError()

    def set_global_rtd10_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        raise NotImplementedError()

    def get_rtd10_heating_configuration(self, heating_id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str,Any]
        raise NotImplementedError()

    def get_rtd10_heating_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        raise NotImplementedError()

    def set_rtd10_heating_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        raise NotImplementedError()

    def set_rtd10_heating_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        raise NotImplementedError()

    def get_rtd10_cooling_configuration(self, cooling_id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str,Any]
        raise NotImplementedError()

    def get_rtd10_cooling_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        raise NotImplementedError()

    def set_rtd10_cooling_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        raise NotImplementedError()

    def set_rtd10_cooling_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        raise NotImplementedError()

    def load_thermostat_group(self):
        # type: () -> ThermostatGroupDTO
        raise NotImplementedError()

    def save_thermostat_group(self, thermostat_group):
        # type: (ThermostatGroupDTO) -> None
        raise NotImplementedError()

    def get_pump_group_configuration(self, pump_group_id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str,Any]
        raise NotImplementedError()

    def get_pump_group_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        raise NotImplementedError()

    def set_pump_group_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        raise NotImplementedError()

    def set_pump_group_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        raise NotImplementedError()

    # Sensors

    def get_sensor_temperature(self, sensor_id):
        raise NotImplementedError()

    def get_sensors_temperature(self):
        # type: () -> List[Optional[float]]
        raise NotImplementedError()

    def get_sensor_humidity(self, sensor_id):
        raise NotImplementedError()

    def get_sensors_humidity(self):
        # type: () -> List[Optional[float]]
        raise NotImplementedError()

    def get_sensor_brightness(self, sensor_id):
        raise NotImplementedError()

    def get_sensors_brightness(self):
        # type: () -> List[Optional[float]]
        raise NotImplementedError()

    def set_virtual_sensor(self, sensor_id, temperature, humidity, brightness):
        raise NotImplementedError()

    def load_sensor(self, sensor_id):  # type: (int) -> MasterSensorDTO
        raise NotImplementedError()

    def load_sensors(self):  # type: () -> List[MasterSensorDTO]
        raise NotImplementedError()

    def save_sensors(self, sensors):  # type: (List[MasterSensorDTO]) -> None
        raise NotImplementedError()

    # PulseCounters

    def load_pulse_counter(self, pulse_counter_id):  # type: (int) -> PulseCounterDTO
        raise NotImplementedError()

    def load_pulse_counters(self):  # type: () -> List[PulseCounterDTO]
        raise NotImplementedError()

    def save_pulse_counters(self, pulse_counters):  # type: (List[PulseCounterDTO]) -> None
        raise NotImplementedError()

    def get_pulse_counter_values(self):  # type: () -> Dict[int, int]
        raise NotImplementedError()

    # Virtual modules

    def add_virtual_output_module(self):
        # type: () -> None
        raise NotImplementedError()

    def add_virtual_dim_control_module(self):
        # type: () -> None
        raise NotImplementedError()

    def add_virtual_input_module(self):
        # type: () -> None
        raise NotImplementedError()

    def add_virtual_sensor_module(self):
        # type: () -> None
        raise NotImplementedError()

    # Generic

    def power_cycle_bus(self):
        raise NotImplementedError()

    def get_status(self):
        raise NotImplementedError()

    def reset(self):
        raise NotImplementedError()

    def cold_reset(self, power_on=True):
        # type: (bool) -> None
        raise NotImplementedError()

    def raw_action(self, action, size=None, data=None):
        # type: (str, int, Optional[bytearray]) -> Dict[str,Any]
        raise NotImplementedError()

    def update_master(self, hex_filename):
        # type: (str) -> None
        raise NotImplementedError()

    def update_slave_modules(self, module_type, hex_filename, version):
        # type: (str, str, str) -> None
        raise NotImplementedError()

    def get_modules(self):
        raise NotImplementedError()

    def get_modules_information(self, address=None):  # type: (Optional[str]) -> List[ModuleDTO]
        raise NotImplementedError()

    def replace_module(self, old_address, new_address):  # type: (str, str) -> None
        raise NotImplementedError()

    def flash_leds(self, led_type, led_id):  # type: (int, int) -> str
        raise NotImplementedError()

    def get_backup(self):
        raise NotImplementedError()

    def restore(self, data):
        raise NotImplementedError()

    def factory_reset(self, can):
        # type: (bool) -> None
        raise NotImplementedError()

    def sync_time(self):
        # type: () -> None
        raise NotImplementedError()

    def get_configuration_dirty_flag(self):
        # type: () -> bool
        raise NotImplementedError()

    # Module functions

    def module_discover_start(self, timeout):  # type: (int) -> None
        raise NotImplementedError()

    def module_discover_stop(self):  # type: () -> None
        raise NotImplementedError()

    def module_discover_status(self):  # type: () -> bool
        raise NotImplementedError()

    def get_module_log(self):  # type: () -> List[Dict[str, Any]]
        raise NotImplementedError()

    # Error functions

    def error_list(self):
        # type: () -> List[Tuple[str,int]]
        raise NotImplementedError()

    def last_success(self):
        raise NotImplementedError()

    def clear_error_list(self):
        raise NotImplementedError()

    def set_status_leds(self, status):
        raise NotImplementedError()

    # (Group)Actions

    def do_basic_action(self, action_type, action_number):  # type: (int, int) -> None
        raise NotImplementedError()

    def do_group_action(self, group_action_id):  # type: (int) -> None
        raise NotImplementedError()

    def load_group_action(self, group_action_id):  # type: (int) -> GroupActionDTO
        raise NotImplementedError()

    def load_group_actions(self):  # type: () -> List[GroupActionDTO]
        raise NotImplementedError()

    def save_group_actions(self, group_actions):  # type: (List[GroupActionDTO]) -> None
        raise NotImplementedError()

    # Schedule

    def load_scheduled_action(self, scheduled_action_id):  # type: (int) -> LegacyScheduleDTO
        raise NotImplementedError()

    def load_scheduled_actions(self):  # type: () -> List[LegacyScheduleDTO]
        raise NotImplementedError()

    def save_scheduled_actions(self, scheduled_actions):  # type: (List[LegacyScheduleDTO]) -> None
        raise NotImplementedError()

    def load_startup_action(self):  # type: () -> LegacyStartupActionDTO
        raise NotImplementedError()

    def save_startup_action(self, startup_action):  # type: (LegacyStartupActionDTO) -> None
        raise NotImplementedError()

    # Dimmer functions

    def load_dimmer_configuration(self):
        # type: () -> DimmerConfigurationDTO
        raise NotImplementedError()

    def save_dimmer_configuration(self, dimmer_configuration_dto):
        # type: (DimmerConfigurationDTO) -> None
        raise NotImplementedError()

    # Can Led functions

    def load_global_feedback(self, global_feedback_id):
        # type: (int) -> GlobalFeedbackDTO
        raise NotImplementedError()

    def load_global_feedbacks(self):
        # type: () -> List[GlobalFeedbackDTO]
        raise NotImplementedError()

    def save_global_feedbacks(self, global_feedbacks):
        # type: (List[GlobalFeedbackDTO]) -> None
        raise NotImplementedError()

    # All lights

    def set_all_lights(self, action, output_ids=None):
        # type: (Literal['ON', 'OFF', 'TOGGLE'], Optional[List[int]]) -> None
        raise NotImplementedError()

    # Validation bits

    def load_validation_bits(self):
        raise NotImplementedError()
