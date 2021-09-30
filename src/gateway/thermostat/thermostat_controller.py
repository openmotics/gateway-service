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
        ThermostatGroupStatusDTO, ThermostatGroupDTO, PumpGroupDTO, \
        RTD10DTO, GlobalRTD10DTO
    from gateway.output_controller import OutputController
    from typing import List, Tuple, Optional


class ThermostatController(object):
    GLOBAL_THERMOSTAT = 0

    def __init__(self, output_controller):
        # type: (OutputController) -> None
        self._output_controller = output_controller

    def start(self):  # type: () -> None
        raise NotImplementedError()

    def stop(self):  # type: () -> None
        raise NotImplementedError()

    def set_current_setpoint(self, thermostat_number, temperature=None, heating_temperature=None, cooling_temperature=None):
        # type: (int, Optional[float], Optional[float], Optional[float]) -> None
        raise NotImplementedError()

    def set_setpoint_from_scheduler(self, thermostat_number, heating_temperature=None, cooling_temperature=None):
        # type: (int, Optional[float], Optional[float]) -> None
        raise NotImplementedError()

    def get_current_preset(self, thermostat_number):
        raise NotImplementedError()

    def set_current_preset(self, thermostat_number, preset_type):
        raise NotImplementedError()

    def load_heating_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        raise NotImplementedError()

    def load_heating_thermostats(self):  # type: () -> List[ThermostatDTO]
        raise NotImplementedError()

    def save_heating_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        raise NotImplementedError()

    def load_heating_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        raise NotImplementedError()

    def load_heating_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        raise NotImplementedError()

    def save_heating_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        raise NotImplementedError()

    def set_per_thermostat_mode(self, thermostat_id, automatic, setpoint):
        # type: (int, bool, int) -> None
        raise NotImplementedError()

    def set_thermostat(self, thermostat_id, preset=None, state=None, temperature=None):
        # type: (int, Optional[str], Optional[str], Optional[float]) -> None
        raise NotImplementedError()

    def load_thermostat_groups(self):  # type: () -> List[ThermostatGroupDTO]
        raise NotImplementedError()

    def load_thermostat_group(self, thermostat_group_id):  # type: (int) -> ThermostatGroupDTO
        raise NotImplementedError()

    def save_thermostat_group(self, thermostat_group):  # type: (ThermostatGroupDTO) -> None
        raise NotImplementedError()

    def get_thermostat_group_status(self):  # type: () -> List[ThermostatGroupStatusDTO]
        raise NotImplementedError()

    def set_thermostat_group(self, thermostat_group_id, state=None, mode=None):
        # type: (int, Optional[str], Optional[str]) -> None
        raise NotImplementedError()

    def set_thermostat_mode(self, thermostat_on, cooling_mode=False, cooling_on=False, automatic=None, setpoint=None):
        # type: (bool, bool, bool, Optional[bool], Optional[int]) -> None
        raise NotImplementedError()

    def load_cooling_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        raise NotImplementedError()

    def load_cooling_thermostats(self):  # type: () -> List[ThermostatDTO]
        raise NotImplementedError()

    def save_cooling_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        raise NotImplementedError()

    def load_cooling_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        raise NotImplementedError()

    def load_cooling_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        raise NotImplementedError()

    def save_cooling_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        raise NotImplementedError()

    def load_global_rtd10(self):  # type: () -> GlobalRTD10DTO
        raise NotImplementedError()

    def save_global_rtd10(self, global_rtd10):  # type: (GlobalRTD10DTO) -> None
        raise NotImplementedError()

    def load_heating_rtd10(self, rtd10_id):  # type: (int) -> RTD10DTO
        raise NotImplementedError()

    def load_heating_rtd10s(self):  # type: () -> List[RTD10DTO]
        raise NotImplementedError()

    def save_heating_rtd10s(self, rtd10s):  # type: (List[RTD10DTO]) -> None
        raise NotImplementedError()

    def load_cooling_rtd10(self, rtd10_id):  # type: (int) -> RTD10DTO
        raise NotImplementedError()

    def load_cooling_rtd10s(self):  # type: () -> List[RTD10DTO]
        raise NotImplementedError()

    def save_cooling_rtd10s(self, rtd10s):  # type: (List[RTD10DTO]) -> None
        raise NotImplementedError()

    def set_airco_status(self, thermostat_id, airco_on):  # type: (int, bool) -> None
        raise NotImplementedError()

    def load_airco_status(self):  # type: () -> ThermostatAircoStatusDTO
        raise NotImplementedError()
