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
    from bus.om_bus_client import MessageClient
    from gateway.dto import ThermostatDTO, ThermostatGroupStatusDTO, \
        ThermostatGroupDTO
    from gateway.events import GatewayEvent
    from gateway.output_controller import OutputController
    from typing import Any, Callable, Dict, List, Tuple, Optional


class ThermostatController(object):
    def __init__(self, message_client, output_controller):
        # type: (Optional[MessageClient], OutputController) -> None
        self._message_client = message_client
        self._output_controller = output_controller

        self._event_subscriptions = []  # type: List[Callable[[GatewayEvent], None]]

    def start(self):  # type: () -> None
        raise NotImplementedError()

    def stop(self):  # type: () -> None
        raise NotImplementedError()

    def subscribe_events(self, callback):  # type: (Callable[[GatewayEvent], None]) -> None
        """
        Subscribes a callback to generic events
        :param callback: the callback to call
        """
        self._event_subscriptions.append(callback)

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

    def v0_get_pump_group_configuration(self, pump_group_id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str,Any]
        """
        Get a specific pump_group_configuration defined by its id.

        :param pump_group_id: The id of the pump_group_configuration
        :type pump_group_id: Id
        :param fields: The field of the pump_group_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        raise NotImplementedError()

    def v0_get_pump_group_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        """
        Get all pump_group_configurations.

        :param fields: The field of the pump_group_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
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

    def v0_get_cooling_pump_group_configuration(self, id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str,Any]
        """
        Get a specific cooling_pump_group_configuration defined by its id.

        :param id: The id of the cooling_pump_group_configuration
        :type id: int
        :param fields: The field of the cooling_pump_group_configuration to get. (None gets all fields)
        :type fields: list
        :returns: 'config': cooling_pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        :rtype: dict
        """
        raise NotImplementedError()

    def v0_get_cooling_pump_group_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        """
        Get all cooling_pump_group_configurations.

        :param fields: The field of the cooling_pump_group_configuration to get. (None gets all fields)
        :type fields: list
        :returns: 'config': list of cooling_pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        :rtype: dict
        """
        raise NotImplementedError()

    def v0_set_pump_group_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set one pump_group_configuration.

        :param config: The pump_group_configuration to set
        :type config: pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        raise NotImplementedError()

    def v0_set_pump_group_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        """
        Set multiple pump_group_configurations.

        :param config: The list of pump_group_configurations to set
        :type config: list of pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        raise NotImplementedError()

    def v0_set_cooling_pump_group_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set one cooling_pump_group_configuration.

        :param config: The cooling_pump_group_configuration to set: cooling_pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        :type config: dict
        """
        raise NotImplementedError()

    def v0_set_cooling_pump_group_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        """
        Set multiple cooling_pump_group_configurations.

        :param config: The list of cooling_pump_group_configurations to set: list of cooling_pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        :type config: list
        """
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

    def v0_set_airco_status(self, thermostat_id, airco_on):
        # type: (int, bool) -> Dict[str,Any]
        """ Set the mode of the airco attached to a given thermostat.
        :param thermostat_id: The thermostat id.
        :type thermostat_id: Integer [0, 31]
        :param airco_on: Turns the airco on if True.
        :type airco_on: boolean.
        :returns: dict with 'status'.
        """
        raise NotImplementedError()

    def v0_get_airco_status(self):
        # type: () -> Dict[str,Any]
        """ Get the mode of the airco attached to a all thermostats.
        :returns: dict with ASB0-ASB31.
        """
        raise NotImplementedError()
