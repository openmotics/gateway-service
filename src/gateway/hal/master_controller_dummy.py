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
Module for communicating with the Master
"""
from __future__ import absolute_import

import logging

from gateway.dto import GroupActionDTO, InputDTO, ModuleDTO, OutputDTO, \
    PulseCounterDTO, SensorDTO, ShutterDTO, ShutterGroupDTO, ThermostatDTO
from gateway.hal.master_controller import MasterController

if False:  # MYPY
    from typing import Any, Dict, List, Literal, Optional, Tuple
    from plugins.base import PluginController

logger = logging.getLogger('openmotics')


class MasterCommunicator(object):
    def start(self):
        # type: () -> None
        pass

    def stop(self):
        # type: () -> None
        pass


class MasterDummyController(MasterController):
    def __init__(self):
        # type: () -> None
        super(MasterDummyController, self).__init__(MasterCommunicator())

    def set_plugin_controller(self, plugin_controller):
        # type: (PluginController) -> None
        pass

    def get_communicator_health(self):
        # type: () -> Literal['success']
        return 'success'

    def module_discover_status(self):
        # type: () -> bool
        return False

    def get_firmware_version(self):
        # type: () -> Tuple[int, int, int]
        return (0, 0, 0)

    def get_status(self):
        # type: () -> Dict[str,Any]
        return {'time': '%02d:%02d' % (0, 0),
                'date': '%02d/%02d/%d' % (1, 1, 1970),
                'mode': 76,
                'version': '%d.%d.%d' % (0, 0, 0),
                'hw_version': 0}

    def get_modules(self):
        # type: () -> Dict[str,List[Any]]
        return {'outputs': [], 'inputs': [], 'shutters': [], 'can_inputs': []}

    def get_modules_information(self, address=None):
        # type: (Optional[str]) -> List[ModuleDTO]
        if address:
            raise NotImplementedError()
        else:
            return []

    def load_inputs(self):
        # type: () -> List[InputDTO]
        return []

    def load_can_led_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        return []

    def get_inputs_with_status(self):
        # type: () -> List[Dict[str,Any]]
        return []

    def get_recent_inputs(self):
        # type: () -> List[int]
        return []

    def load_outputs(self):  # type: () -> List[OutputDTO]
        return []

    def load_output_status(self):
        # type: () -> List[Dict[str,Any]]
        return []

    def load_shutters(self):
        # type: () -> List[ShutterDTO]
        return []

    def load_shutter_groups(self):
        # type: () -> List[ShutterGroupDTO]
        return []

    def get_thermostats(self):
        # type: () -> Dict[str,Any]
        return {}

    def get_thermostat_modes(self):
        # type: () -> Dict[str,Any]
        return {}

    def get_global_thermostat_configuration(self, fields=None):
        # type: (Optional[List[str]]) -> Dict[str,Any]
        return {}

    def load_cooling_thermostats(self):
        # type: () -> List[ThermostatDTO]
        return []

    def load_heating_thermostats(self):
        # type: () -> List[ThermostatDTO]
        return []

    def read_airco_status_bits(self):
        # type: () -> Dict[str,Any]
        return {}

    def get_pump_group_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        return []

    def get_cooling_pump_group_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> List[Dict[str,Any]]
        return []

    def load_sensors(self):
        # type: () -> List[SensorDTO]
        return []

    def get_sensors_temperature(self):
        # type: () -> List[Optional[float]]
        return []

    def get_sensors_humidity(self):
        # type: () -> List[Optional[float]]
        return []

    def get_sensors_brightness(self):
        # type: () -> List[Optional[float]]
        return []

    def load_pulse_counters(self):
        # type: () -> List[PulseCounterDTO]
        return []

    def get_pulse_counter_values(self):
        # type: () -> Dict[int, int]
        return {}

    def load_group_actions(self):
        # type: () -> List[GroupActionDTO]
        return []

    # Error functions

    def error_list(self):
        # type: () -> List[Tuple[str,int]]
        return []

    def last_success(self):
        # type: () -> int
        return 0

    def clear_error_list(self):
        # type: () -> bool
        return True

    def set_status_leds(self, status):
        # type: (bool) -> None
        return

    def cold_reset(self, power_on=True):  # type: (bool) -> None
        return None

    def update_master(self, hex_filename):  # type: (str) -> None
        return None

    def update_slave_modules(self, module_type, hex_filename):  # type: (str, str) -> None
        return None
