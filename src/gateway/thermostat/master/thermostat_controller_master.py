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

import logging
import time

from gateway.daemon_thread import DaemonThread, DaemonThreadWait
from gateway.dto import ThermostatDTO, ThermostatGroupStatusDTO, ThermostatStatusDTO, \
    ThermostatGroupDTO
from gateway.events import GatewayEvent
from gateway.hal.master_event import MasterEvent
from gateway.hal.master_controller import CommunicationFailure
from gateway.pubsub import PubSub
from gateway.thermostat.master.thermostat_status_master import \
    ThermostatStatusMaster
from gateway.thermostat.thermostat_controller import ThermostatController
from ioc import INJECTED, Inject
from master.classic.master_communicator import CommunicationTimedOutException
from toolbox import Toolbox

if False:  # MYPY
    from typing import Any, List, Dict, Optional, Tuple
    from gateway.dto import OutputStateDTO
    from gateway.hal.master_controller_classic import MasterClassicController
    from gateway.output_controller import OutputController

logger = logging.getLogger('openmotics')

THERMOSTATS = 'THERMOSTATS'


class ThermostatControllerMaster(ThermostatController):
    @Inject
    def __init__(self, output_controller=INJECTED, master_controller=INJECTED, pubsub=INJECTED):
        # type: (OutputController, MasterClassicController, PubSub) -> None
        super(ThermostatControllerMaster, self).__init__(output_controller)
        self._master_controller = master_controller  # classic only
        self._pubsub = pubsub

        self._monitor_thread = DaemonThread(name='ThermostatControllerMaster monitor',
                                            target=self._monitor,
                                            interval=30, delay=10)

        self._thermostat_status = ThermostatStatusMaster(on_thermostat_change=self._thermostat_changed,
                                                         on_thermostat_group_change=self._thermostat_group_changed)
        self._thermostats_original_interval = 30
        self._thermostats_interval = self._thermostats_original_interval
        self._thermostats_last_updated = 0.0
        self._thermostats_restore = 0
        self._thermostats_config = {}  # type: Dict[int, ThermostatDTO]

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.EEPROM, self._handle_master_event)

    def start(self):
        # type: () -> None
        self._monitor_thread.start()

    def stop(self):
        # type: () -> None
        self._monitor_thread.stop()

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        if master_event.type == MasterEvent.Types.EEPROM_CHANGE:
            self.invalidate_cache(THERMOSTATS)

    def _thermostat_changed(self, thermostat_id, status):
        # type: (int, Dict[str,Any]) -> None
        """ Executed by the Thermostat Status tracker when an output changed state """
        location = {'room_id': Toolbox.denonify(self._thermostats_config[thermostat_id].room, 255)}
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE,
                                     {'id': thermostat_id,
                                      'status': {'preset': status['preset'],
                                                 'current_setpoint': status['current_setpoint'],
                                                 'actual_temperature': status['actual_temperature'],
                                                 'output_0': status['output_0'],
                                                 'output_1': status['output_1']},
                                      'location': location})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _thermostat_group_changed(self, status):
        # type: (Dict[str,Any]) -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_GROUP_CHANGE,
                                     {'id': 0,
                                      'status': {'state': status['state'],
                                                 'mode': status['mode']},
                                      'location': {}})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    @staticmethod
    def check_basic_action(ret_dict):
        """ Checks if the response is 'OK', throws a ValueError otherwise. """
        if ret_dict['resp'] != 'OK':
            raise ValueError('Basic action did not return OK.')

    def increase_interval(self, object_type, interval, window):
        """ Increases a certain interval to a new setting for a given amount of time """
        if object_type == THERMOSTATS:
            self._thermostats_interval = interval
            self._thermostats_restore = time.time() + window

    def invalidate_cache(self, object_type=None):
        """
        Triggered when an external service knows certain settings might be changed in the background.
        For example: maintenance mode or module discovery
        """
        if object_type is None or object_type == THERMOSTATS:
            self._thermostats_last_updated = 0

    ################################
    # New API
    ################################

    def get_current_preset(self, thermostat_number):
        raise NotImplementedError()

    def set_current_preset(self, thermostat_number, preset_type):
        raise NotImplementedError()

    ################################
    # Legacy API
    ################################

    def load_heating_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        return self._master_controller.load_heating_thermostat(thermostat_id)

    def load_heating_thermostats(self):  # type: () -> List[ThermostatDTO]
        return self._master_controller.load_heating_thermostats()

    def save_heating_thermostats(self, thermostats):  # type: (List[Tuple[ThermostatDTO, List[str]]]) -> None
        self._master_controller.save_heating_thermostats(thermostats)
        self.invalidate_cache(THERMOSTATS)

    def load_cooling_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        return self._master_controller.load_cooling_thermostat(thermostat_id)

    def load_cooling_thermostats(self):  # type: () -> List[ThermostatDTO]
        return self._master_controller.load_cooling_thermostats()

    def save_cooling_thermostats(self, thermostats):  # type: (List[Tuple[ThermostatDTO, List[str]]]) -> None
        self._master_controller.save_cooling_thermostats(thermostats)
        self.invalidate_cache(THERMOSTATS)

    def v0_get_cooling_pump_group_configuration(self, pump_group_id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str,Any]
        """
        Get a specific cooling_pump_group_configuration defined by its id.

        :param pump_group_id: The id of the cooling_pump_group_configuration
        :type pump_group_id: Id
        :param fields: The field of the cooling_pump_group_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: cooling_pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        return self._master_controller.get_cooling_pump_group_configuration(pump_group_id, fields=fields)

    def v0_get_cooling_pump_group_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        """
        Get all cooling_pump_group_configurations.

        :param fields: The field of the cooling_pump_group_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of cooling_pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        return self._master_controller.get_cooling_pump_group_configurations(fields=fields)

    def v0_set_cooling_pump_group_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set one cooling_pump_group_configuration.

        :param config: The cooling_pump_group_configuration to set
        :type config: cooling_pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        self._master_controller.set_cooling_pump_group_configuration(config)

    def v0_set_cooling_pump_group_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        """
        Set multiple cooling_pump_group_configurations.

        :param config: The list of cooling_pump_group_configurations to set
        :type config: list of cooling_pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        self._master_controller.set_cooling_pump_group_configurations(config)

    def v0_get_global_rtd10_configuration(self, fields=None):
        # type: (Optional[List[str]]) -> Dict[str,Any]
        """
        Get the global_rtd10_configuration.

        :param fields: The field of the global_rtd10_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: global_rtd10_configuration dict: contains 'output_value_cooling_16' (Byte), 'output_value_cooling_16_5' (Byte), 'output_value_cooling_17' (Byte), 'output_value_cooling_17_5' (Byte), 'output_value_cooling_18' (Byte), 'output_value_cooling_18_5' (Byte), 'output_value_cooling_19' (Byte), 'output_value_cooling_19_5' (Byte), 'output_value_cooling_20' (Byte), 'output_value_cooling_20_5' (Byte), 'output_value_cooling_21' (Byte), 'output_value_cooling_21_5' (Byte), 'output_value_cooling_22' (Byte), 'output_value_cooling_22_5' (Byte), 'output_value_cooling_23' (Byte), 'output_value_cooling_23_5' (Byte), 'output_value_cooling_24' (Byte), 'output_value_heating_16' (Byte), 'output_value_heating_16_5' (Byte), 'output_value_heating_17' (Byte), 'output_value_heating_17_5' (Byte), 'output_value_heating_18' (Byte), 'output_value_heating_18_5' (Byte), 'output_value_heating_19' (Byte), 'output_value_heating_19_5' (Byte), 'output_value_heating_20' (Byte), 'output_value_heating_20_5' (Byte), 'output_value_heating_21' (Byte), 'output_value_heating_21_5' (Byte), 'output_value_heating_22' (Byte), 'output_value_heating_22_5' (Byte), 'output_value_heating_23' (Byte), 'output_value_heating_23_5' (Byte), 'output_value_heating_24' (Byte)
        """
        return self._master_controller.get_global_rtd10_configuration(fields=fields)

    def v0_set_global_rtd10_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set the global_rtd10_configuration.

        :param config: The global_rtd10_configuration to set
        :type config: global_rtd10_configuration dict: contains 'output_value_cooling_16' (Byte), 'output_value_cooling_16_5' (Byte), 'output_value_cooling_17' (Byte), 'output_value_cooling_17_5' (Byte), 'output_value_cooling_18' (Byte), 'output_value_cooling_18_5' (Byte), 'output_value_cooling_19' (Byte), 'output_value_cooling_19_5' (Byte), 'output_value_cooling_20' (Byte), 'output_value_cooling_20_5' (Byte), 'output_value_cooling_21' (Byte), 'output_value_cooling_21_5' (Byte), 'output_value_cooling_22' (Byte), 'output_value_cooling_22_5' (Byte), 'output_value_cooling_23' (Byte), 'output_value_cooling_23_5' (Byte), 'output_value_cooling_24' (Byte), 'output_value_heating_16' (Byte), 'output_value_heating_16_5' (Byte), 'output_value_heating_17' (Byte), 'output_value_heating_17_5' (Byte), 'output_value_heating_18' (Byte), 'output_value_heating_18_5' (Byte), 'output_value_heating_19' (Byte), 'output_value_heating_19_5' (Byte), 'output_value_heating_20' (Byte), 'output_value_heating_20_5' (Byte), 'output_value_heating_21' (Byte), 'output_value_heating_21_5' (Byte), 'output_value_heating_22' (Byte), 'output_value_heating_22_5' (Byte), 'output_value_heating_23' (Byte), 'output_value_heating_23_5' (Byte), 'output_value_heating_24' (Byte)
        """
        self._master_controller.set_global_rtd10_configuration(config)

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
        return self._master_controller.get_rtd10_heating_configuration(heating_id, fields=fields)

    def v0_get_rtd10_heating_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        """
        Get all rtd10_heating_configurations.

        :param fields: The field of the rtd10_heating_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of rtd10_heating_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        return self._master_controller.get_rtd10_heating_configurations(fields=fields)

    def v0_set_rtd10_heating_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set one rtd10_heating_configuration.

        :param config: The rtd10_heating_configuration to set
        :type config: rtd10_heating_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        self._master_controller.set_rtd10_heating_configuration(config)

    def v0_set_rtd10_heating_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        """
        Set multiple rtd10_heating_configurations.

        :param config: The list of rtd10_heating_configurations to set
        :type config: list of rtd10_heating_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        self._master_controller.set_rtd10_heating_configurations(config)

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
        return self._master_controller.get_rtd10_cooling_configuration(cooling_id, fields=fields)

    def v0_get_rtd10_cooling_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        """
        Get all rtd10_cooling_configurations.

        :param fields: The field of the rtd10_cooling_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of rtd10_cooling_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        return self._master_controller.get_rtd10_cooling_configurations(fields=fields)

    def v0_set_rtd10_cooling_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set one rtd10_cooling_configuration.

        :param config: The rtd10_cooling_configuration to set
        :type config: rtd10_cooling_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        self._master_controller.set_rtd10_cooling_configuration(config)

    def v0_set_rtd10_cooling_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        """
        Set multiple rtd10_cooling_configurations.

        :param config: The list of rtd10_cooling_configurations to set
        :type config: list of rtd10_cooling_configuration dict: contains 'id' (Id), 'mode_output' (Byte), 'mode_value' (Byte), 'on_off_output' (Byte), 'poke_angle_output' (Byte), 'poke_angle_value' (Byte), 'room' (Byte), 'temp_setpoint_output' (Byte), 'ventilation_speed_output' (Byte), 'ventilation_speed_value' (Byte)
        """
        self._master_controller.set_rtd10_cooling_configurations(config)

    def load_thermostat_group(self):
        # type: () -> ThermostatGroupDTO
        """ Get the thermostat group. """
        return self._master_controller.load_thermostat_group()

    def save_thermostat_group(self, thermostat_group):
        # type: (Tuple[ThermostatGroupDTO, List[str]]) -> None
        """ Set the thermostat group. """
        self._master_controller.save_thermostat_group(thermostat_group)
        self.invalidate_cache(THERMOSTATS)

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
        return self._master_controller.get_pump_group_configuration(pump_group_id, fields=fields)

    def v0_get_pump_group_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        """
        Get all pump_group_configurations.

        :param fields: The field of the pump_group_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        return self._master_controller.get_pump_group_configurations(fields=fields)

    def v0_set_pump_group_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        """
        Set one pump_group_configuration.

        :param config: The pump_group_configuration to set
        :type config: pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        self._master_controller.set_pump_group_configuration(config)

    def v0_set_pump_group_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        """
        Set multiple pump_group_configurations.

        :param config: The list of pump_group_configurations to set
        :type config: list of pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32]), 'room' (Byte)
        """
        self._master_controller.set_pump_group_configurations(config)

    def set_thermostat_mode(self, thermostat_on, cooling_mode=False, cooling_on=False, automatic=None, setpoint=None):
        # type: (bool, bool, bool, Optional[bool], Optional[int]) -> None
        """ Set the mode of the thermostats. """
        _ = thermostat_on  # Still accept `thermostat_on` for backwards compatibility

        # Figure out whether the system should be on or off
        set_on = False
        if cooling_mode is True and cooling_on is True:
            set_on = True
        if cooling_mode is False:
            # Heating means threshold based
            thermostat_group = self.load_thermostat_group()
            outside_sensor = Toolbox.denonify(thermostat_group.outside_sensor_id, 255)
            current_temperatures = self._master_controller.get_sensors_temperature()[:32]
            if len(current_temperatures) < 32:
                current_temperatures += [None] * (32 - len(current_temperatures))
            if len(current_temperatures) > outside_sensor:
                current_temperature = current_temperatures[outside_sensor]
                set_on = thermostat_group.threshold_temperature > current_temperature
            else:
                set_on = True

        # Calculate and set the global mode
        mode = 0
        mode |= (1 if set_on is True else 0) << 7
        mode |= 1 << 6  # multi-tenant mode
        mode |= (1 if cooling_mode else 0) << 4
        if automatic is not None:
            mode |= (1 if automatic else 0) << 3
        self._master_controller.set_thermostat_mode(mode)

        # Caclulate and set the cooling/heating mode
        cooling_heating_mode = 0
        if cooling_mode is True:
            cooling_heating_mode = 1 if cooling_on is False else 2
        self._master_controller.set_thermostat_cooling_heating(cooling_heating_mode)

        # Then, set manual/auto
        if automatic is not None:
            action_number = 1 if automatic is True else 0
            self._master_controller.set_thermostat_automatic(action_number)

        # If manual, set the setpoint if appropriate
        if automatic is False and setpoint is not None and 3 <= setpoint <= 5:
            self._master_controller.set_thermostat_all_setpoints(setpoint)

        self.invalidate_cache(THERMOSTATS)
        self.increase_interval(THERMOSTATS, interval=2, window=10)

    def set_per_thermostat_mode(self, thermostat_id, automatic, setpoint):
        # type: (int, bool, int) -> None
        """ Set the setpoint/mode for a certain thermostat. """
        if thermostat_id < 0 or thermostat_id > 31:
            raise ValueError('Thermostat_id not in [0, 31]: %d' % thermostat_id)

        if setpoint < 0 or setpoint > 5:
            raise ValueError('Setpoint not in [0, 5]: %d' % setpoint)

        if automatic:
            self._master_controller.set_thermostat_tenant_auto(thermostat_id)
        else:
            self._master_controller.set_thermostat_tenant_manual(thermostat_id)
            self._master_controller.set_thermostat_setpoint(thermostat_id, setpoint)

        self.invalidate_cache(THERMOSTATS)
        self.increase_interval(THERMOSTATS, interval=2, window=10)

    def v0_set_airco_status(self, thermostat_id, airco_on):
        # type: (int, bool) -> Dict[str,Any]
        """ Set the mode of the airco attached to a given thermostat.
        :param thermostat_id: The thermostat id.
        :type thermostat_id: Integer [0, 31]
        :param airco_on: Turns the airco on if True.
        :type airco_on: boolean.
        :returns: dict with 'status'.
        """
        if thermostat_id < 0 or thermostat_id > 31:
            raise ValueError('thermostat_id not in [0, 31]: %d' % thermostat_id)
        modifier = 0 if airco_on else 100
        self._master_controller.set_airco_status_bits(modifier + thermostat_id)
        return {'status': 'OK'}

    def v0_get_airco_status(self):
        # type: () -> Dict[str,Any]
        """ Get the mode of the airco attached to a all thermostats.
        :returns: dict with ASB0-ASB31.
        """
        return self._master_controller.read_airco_status_bits()

    @staticmethod
    def __check_thermostat(thermostat):
        """ :raises ValueError if thermostat not in range [0, 32]. """
        if thermostat not in range(0, 32):
            raise ValueError('Thermostat not in [0,32]: %d' % thermostat)

    def set_current_setpoint(self, thermostat_number, temperature=None, heating_temperature=None, cooling_temperature=None):
        # type: (int, Optional[float], Optional[float], Optional[float]) -> None
        """ Set the current setpoint of a thermostat. """
        if temperature is None:
            temperature = heating_temperature
        if temperature is None:
            temperature = cooling_temperature

        self.__check_thermostat(thermostat_number)
        self._master_controller.write_thermostat_setpoint(thermostat_number, temperature)

        self.invalidate_cache(THERMOSTATS)
        self.increase_interval(THERMOSTATS, interval=2, window=10)

    def _monitor(self):
        # type: () -> None
        """ Monitors certain system states to detect changes without events """
        try:
            # Refresh if required
            if self._thermostats_last_updated + self._thermostats_interval < time.time():
                self._refresh_thermostats()
            # Restore interval if required
            if self._thermostats_restore < time.time():
                self._thermostats_interval = self._thermostats_original_interval
        except CommunicationTimedOutException:
            logger.error('Got communication timeout during thermostat monitoring, waiting 10 seconds.')
            raise DaemonThreadWait

    def _refresh_thermostats(self):
        # type: () -> None
        """
        Get basic information about all thermostats and pushes it in to the Thermostat Status tracker
        """

        def get_automatic_setpoint(_mode):
            _automatic = bool(_mode & 1 << 3)
            return _automatic, 0 if _automatic else (_mode & 0b00000111)

        try:
            thermostat_info = self._master_controller.get_thermostats()
            thermostat_mode = self._master_controller.get_thermostat_modes()
            aircos = self._master_controller.read_airco_status_bits()
        except CommunicationFailure:
            return

        status = {state.id: state for state in self._output_controller.get_output_statuses()}  # type: Dict[int,OutputStateDTO]

        mode = thermostat_info['mode']
        thermostats_on = bool(mode & 1 << 7)
        cooling = bool(mode & 1 << 4)
        automatic, setpoint = get_automatic_setpoint(thermostat_mode['mode0'])

        try:
            if cooling:
                self._thermostats_config = {thermostat.id: thermostat
                                            for thermostat in self.load_cooling_thermostats()}
            else:
                self._thermostats_config = {thermostat.id: thermostat
                                            for thermostat in self.load_heating_thermostats()}
        except CommunicationFailure:
            return

        thermostats = []
        for thermostat_id in range(32):
            thermostat_dto = self._thermostats_config[thermostat_id]  # type: ThermostatDTO
            if thermostat_dto.in_use:
                t_mode = thermostat_mode['mode{0}'.format(thermostat_id)]
                t_automatic, t_setpoint = get_automatic_setpoint(t_mode)
                thermostat = {'id': thermostat_id,
                              'act': thermostat_info['tmp{0}'.format(thermostat_id)].get_temperature(),
                              'csetp': thermostat_info['setp{0}'.format(thermostat_id)].get_temperature(),
                              'outside': thermostat_info['outside'].get_temperature(),
                              'mode': t_mode,
                              'automatic': t_automatic,
                              'setpoint': t_setpoint,
                              'name': thermostat_dto.name,
                              'sensor_nr': thermostat_dto.sensor,
                              'airco': aircos['ASB{0}'.format(thermostat_id)]}
                for output in [0, 1]:
                    output_id = getattr(thermostat_dto, 'output{0}'.format(output))
                    output_state_dto = status.get(output_id)
                    if output_id is not None and output_state_dto is not None and output_state_dto.status:
                        thermostat['output{0}'.format(output)] = output_state_dto.dimmer
                    else:
                        thermostat['output{0}'.format(output)] = 0
                thermostats.append(thermostat)

        self._thermostat_status.full_update({'thermostats_on': thermostats_on,
                                             'automatic': automatic,
                                             'setpoint': setpoint,
                                             'cooling': cooling,
                                             'status': thermostats})
        self._thermostats_last_updated = time.time()

    def get_thermostat_status(self):
        # type: () -> ThermostatGroupStatusDTO
        """ Returns thermostat information """
        self._refresh_thermostats()  # Always return the latest information
        master_status = self._thermostat_status.get_thermostats()
        return ThermostatGroupStatusDTO(id=0,
                                        on=master_status['thermostats_on'],
                                        automatic=master_status['automatic'],
                                        setpoint=master_status['setpoint'],
                                        cooling=master_status['cooling'],
                                        statusses=[ThermostatStatusDTO(id=thermostat['id'],
                                                                       actual_temperature=thermostat['act'],
                                                                       setpoint_temperature=thermostat['csetp'],
                                                                       outside_temperature=thermostat['outside'],
                                                                       mode=thermostat['mode'],
                                                                       automatic=thermostat['automatic'],
                                                                       setpoint=thermostat['setpoint'],
                                                                       name=thermostat['name'],
                                                                       sensor_id=thermostat['sensor_nr'],
                                                                       airco=thermostat['airco'],
                                                                       output_0_level=thermostat['output0'],
                                                                       output_1_level=thermostat['output1'])
                                                   for thermostat in master_status['status']])
        return self._thermostat_status.get_thermostats()
