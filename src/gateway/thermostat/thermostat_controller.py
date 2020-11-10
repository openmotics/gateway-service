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

if False:  # MYPY
    from gateway.dto import ThermostatAircoStatusDTO, ThermostatDTO, \
        ThermostatGroupStatusDTO, ThermostatGroupDTO, PumpGroupDTO
    from gateway.output_controller import OutputController
    from typing import Any, Dict, List, Tuple, Optional


class ThermostatController(object):
    def __init__(self, output_controller):
        # type: (OutputController) -> None
        self._output_controller = output_controller

    def start(self):  # type: () -> None
        raise NotImplementedError()

    def stop(self):  # type: () -> None
        raise NotImplementedError()

    ################################
    # v1 APIs
    ################################
    # TODO: Implement all v1 APIs

    def set_current_setpoint(self, thermostat_number, temperature=None, heating_temperature=None, cooling_temperature=None):
        # type: (int, Optional[float], Optional[float], Optional[float]) -> None
        raise NotImplementedError()

    def get_current_preset(self, thermostat_number):
        raise NotImplementedError()

    def set_current_preset(self, thermostat_number, preset_type):
        raise NotImplementedError()

    ################################
    # Legacy API
    ################################

    def load_heating_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        raise NotImplementedError()

    def load_heating_thermostats(self):  # type: () -> List[ThermostatDTO]
        raise NotImplementedError()

    def save_heating_thermostats(self, thermostats):  # type: (List[Tuple[ThermostatDTO, List[str]]]) -> None
        raise NotImplementedError()

    def set_thermostat_mode(self, thermostat_on, cooling_mode=False, cooling_on=False, automatic=None, setpoint=None):
        # type: (bool, bool, bool, Optional[bool], Optional[int]) -> None
        """ Set the mode of the thermostats. """
        raise NotImplementedError()

    def load_heating_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        raise NotImplementedError()

    def load_heating_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        raise NotImplementedError()

    def save_heating_pump_groups(self, pump_groups):  # type: (List[Tuple[PumpGroupDTO, List[str]]]) -> None
        raise NotImplementedError()

    def set_per_thermostat_mode(self, thermostat_id, automatic, setpoint):
        # type: (int, bool, int) -> None
        """ Set the setpoint/mode for a certain thermostat. """
        raise NotImplementedError()

    def load_thermostat_group(self):
        # type: () -> ThermostatGroupDTO
        raise NotImplementedError()

    def save_thermostat_group(self, thermostat_group):
        # type: (Tuple[ThermostatGroupDTO, List[str]]) -> None
        raise NotImplementedError()

    def get_thermostat_status(self):
        # type: () -> ThermostatGroupStatusDTO
        raise NotImplementedError()

    def load_cooling_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        raise NotImplementedError()

    def load_cooling_thermostats(self):  # type: () -> List[ThermostatDTO]
        raise NotImplementedError()

    def save_cooling_thermostats(self, thermostats):  # type: (List[Tuple[ThermostatDTO, List[str]]]) -> None
        raise NotImplementedError()

    def load_cooling_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        raise NotImplementedError()

    def load_cooling_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        raise NotImplementedError()

    def save_cooling_pump_groups(self, pump_groups):  # type: (List[Tuple[PumpGroupDTO, List[str]]]) -> None
        raise NotImplementedError()

    def v0_get_global_rtd10_configuration(self, fields=None):
        # type: (Optional[List[str]]) -> Dict[str,Any]
        """
        Get the global_rtd10_configuration.

        :param fields: The field of the global_rtd10_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: global_rtd10_configuration dict: contains 'output_value_cooling_16' (Byte), 'output_value_cooling_16_5' (Byte), 'output_value_cooling_17' (Byte), 'output_value_cooling_17_5' (Byte), 'output_value_cooling_18' (Byte), 'output_value_cooling_18_5' (Byte), 'output_value_cooling_19' (Byte), 'output_value_cooling_19_5' (Byte), 'output_value_cooling_20' (Byte), 'output_value_cooling_20_5' (Byte), 'output_value_cooling_21' (Byte), 'output_value_cooling_21_5' (Byte), 'output_value_cooling_22' (Byte), 'output_value_cooling_22_5' (Byte), 'output_value_cooling_23' (Byte), 'output_value_cooling_23_5' (Byte), 'output_value_cooling_24' (Byte), 'output_value_heating_16' (Byte), 'output_value_heating_16_5' (Byte), 'output_value_heating_17' (Byte), 'output_value_heating_17_5' (Byte), 'output_value_heating_18' (Byte), 'output_value_heating_18_5' (Byte), 'output_value_heating_19' (Byte), 'output_value_heating_19_5' (Byte), 'output_value_heating_20' (Byte), 'output_value_heating_20_5' (Byte), 'output_value_heating_21' (Byte), 'output_value_heating_21_5' (Byte), 'output_value_heating_22' (Byte), 'output_value_heating_22_5' (Byte), 'output_value_heating_23' (Byte), 'output_value_heating_23_5' (Byte), 'output_value_heating_24' (Byte)
        """
        raise NotImplementedError()

    def v0_set_global_rtd10_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set the global_rtd10_configuration.

        :param config: The global_rtd10_configuration to set: global_rtd10_configuration dict: contains 'output_value_cooling_16' (Byte), 'output_value_cooling_16_5' (Byte), 'output_value_cooling_17' (Byte), 'output_value_cooling_17_5' (Byte), 'output_value_cooling_18' (Byte), 'output_value_cooling_18_5' (Byte), 'output_value_cooling_19' (Byte), 'output_value_cooling_19_5' (Byte), 'output_value_cooling_20' (Byte), 'output_value_cooling_20_5' (Byte), 'output_value_cooling_21' (Byte), 'output_value_cooling_21_5' (Byte), 'output_value_cooling_22' (Byte), 'output_value_cooling_22_5' (Byte), 'output_value_cooling_23' (Byte), 'output_value_cooling_23_5' (Byte), 'output_value_cooling_24' (Byte), 'output_value_heating_16' (Byte), 'output_value_heating_16_5' (Byte), 'output_value_heating_17' (Byte), 'output_value_heating_17_5' (Byte), 'output_value_heating_18' (Byte), 'output_value_heating_18_5' (Byte), 'output_value_heating_19' (Byte), 'output_value_heating_19_5' (Byte), 'output_value_heating_20' (Byte), 'output_value_heating_20_5' (Byte), 'output_value_heating_21' (Byte), 'output_value_heating_21_5' (Byte), 'output_value_heating_22' (Byte), 'output_value_heating_22_5' (Byte), 'output_value_heating_23' (Byte), 'output_value_heating_23_5' (Byte), 'output_value_heating_24' (Byte)
        :type config: dict
        """
        raise NotImplementedError()

    def v0_get_rtd10_heating_configuration(self, heating_id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str,Any]
        """
        Get a specific rtd10_heating_configuration defined by its id.

        :param heating_id: The id of the rtd10_heating_configuration
        :type heating_id: Id
        :param fields: The field of the rtd10_heating_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: rtd10_heating_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        raise NotImplementedError()

    def v0_get_rtd10_heating_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        """
        Get all rtd10_heating_configurations.

        :param fields: The field of the rtd10_heating_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of rtd10_heating_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        raise NotImplementedError()

    def v0_set_rtd10_heating_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set one rtd10_heating_configuration.

        :param config: The rtd10_heating_configuration to set
        :type config: rtd10_heating_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        raise NotImplementedError()

    def v0_set_rtd10_heating_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        """
        Set multiple rtd10_heating_configurations.

        :param config: The list of rtd10_heating_configurations to set
        :type config: list of rtd10_heating_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        raise NotImplementedError()

    def v0_get_rtd10_cooling_configuration(self, cooling_id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str,Any]
        """
        Get a specific rtd10_cooling_configuration defined by its id.

        :param cooling_id: The id of the rtd10_cooling_configuration
        :type cooling_id: Id
        :param fields: The field of the rtd10_cooling_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: rtd10_cooling_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        raise NotImplementedError()

    def v0_get_rtd10_cooling_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        """
        Get all rtd10_cooling_configurations.

        :param fields: The field of the rtd10_cooling_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of rtd10_cooling_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        raise NotImplementedError()

    def v0_set_rtd10_cooling_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set one rtd10_cooling_configuration.

        :param config: The rtd10_cooling_configuration to set
        :type config: rtd10_cooling_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        raise NotImplementedError()

    def v0_set_rtd10_cooling_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        """
        Set multiple rtd10_cooling_configurations.

        :param config: The list of rtd10_cooling_configurations to set
        :type config: list of rtd10_cooling_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        raise NotImplementedError()

    def set_airco_status(self, thermostat_id, airco_on):
        # type: (int, bool) -> None
        raise NotImplementedError()

    def load_airco_status(self):
        # type: () -> ThermostatAircoStatusDTO
        raise NotImplementedError()
