# Copyright (C) 2021 OpenMotics BV
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
Contains energy module abstraction logic
"""

from __future__ import absolute_import

import logging
import math

from gateway.dto import RealtimeEnergyDTO
from gateway.enums import EnergyEnums
from gateway.exceptions import UnsupportedException
from gateway.models import EnergyModule
from energy.energy_api import EnergyAPI
from energy.module_helper import ModuleHelper
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from typing import Dict, Optional, List, Tuple, Any, Union, TypeVar
    T = TypeVar('T', bound=Union[int, float])

logger = logging.getLogger(__name__)


class EnergyModuleHelper(ModuleHelper):
    NUMBER_OF_PORTS = EnergyEnums.NUMBER_OF_PORTS[EnergyEnums.Version.ENERGY_MODULE]

    @staticmethod
    def _convert_nan(number, default):  # type: (T, Optional[T]) -> Optional[T]
        """ Convert nan to a default value """
        if math.isnan(number):
            logger.warning('Got an unexpected NaN')
        return default if math.isnan(number) else number

    def get_realtime(self, energy_module):  # type: (EnergyModule) -> Dict[int, RealtimeEnergyDTO]
        data = {}
        voltages = self._get_voltages(energy_module=energy_module)
        frequencies = self._get_frequencies(energy_module=energy_module)
        currents = self._get_currents(energy_module=energy_module)
        powers = self._get_powers(energy_module=energy_module)
        for port_id in range(self.__class__.NUMBER_OF_PORTS):
            data[port_id] = RealtimeEnergyDTO(voltage=voltages[port_id],
                                              frequency=frequencies[port_id],
                                              power=powers[port_id],
                                              current=currents[port_id])
        return data

    def get_information(self, energy_module):  # type: (EnergyModule) -> Tuple[bool, Optional[str]]
        # TODO: Add more information in some kind of EnergyModuleInformationDTO
        cmd = EnergyAPI.get_version(energy_module.version)
        try:
            raw_version = self._energy_communicator.do_command(int(energy_module.module.address), cmd)
            cleaned_version = raw_version[0].split('\x00', 1)[0]
            parsed_version = cleaned_version.split('_')
            if len(parsed_version) != 4:
                firmware_version = cleaned_version
            else:
                firmware_version = '{1}.{2}.{3} ({0})'.format(*parsed_version)
            return True, firmware_version
        except CommunicationTimedOutException:
            pass  # No need to log here, there will be tons of other logs anyway
        return False, None

    def get_day_counters(self, energy_module):  # type: (EnergyModule) -> List[Optional[int]]
        cmd = EnergyAPI.get_day_energy(energy_module.version)
        return [EnergyModuleHelper._convert_nan(value, default=None)
                for value in self._energy_communicator.do_command(int(energy_module.module.address), cmd)]

    def get_night_counters(self, energy_module):  # type: (EnergyModule) -> List[Optional[int]]
        cmd = EnergyAPI.get_night_energy(energy_module.version)
        return [EnergyModuleHelper._convert_nan(value, default=None)
                for value in self._energy_communicator.do_command(int(energy_module.module.address), cmd)]

    def configure_cts(self, energy_module):  # type: (EnergyModule) -> None
        def _convert_ccf(value):
            try:
                if value == 2:  # 12.5 A
                    return 0.5
                if value in [3, 4, 5, 6]:  # 25 A, 50 A, 100 A, 200 A
                    return int(math.pow(2, value - 3))
                return value / 25.0
            except Exception:
                # In case of calculation errors, default to 12.5 A
                return 0.5

        def _convert_sci(value):
            return 1 if value else 0

        address = int(energy_module.module.address)
        sensor_settings = []
        inverted_settings = []
        for ct in sorted(energy_module.cts, key=lambda c: c.ct_id):
            sensor_settings.append(_convert_ccf(ct.sensor_type))
            inverted_settings.append(_convert_sci(ct.inverted))

        self._energy_communicator.do_command(address, EnergyAPI.set_current_clamp_factor(energy_module.version),
                                             *sensor_settings)
        self._energy_communicator.do_command(address, EnergyAPI.set_current_inverse(energy_module.version),
                                             *inverted_settings)

    def set_module_voltage(self, energy_module, voltage):  # type: (EnergyModule, float) -> None
        cmd = EnergyAPI.set_voltage()
        self._energy_communicator.do_command(int(energy_module.module.address), cmd, voltage)

    def get_energy_time(self, energy_module, input_id=None):  # type: (EnergyModule, Optional[int]) -> Dict[str, Dict[str, Any]]
        if input_id is None:
            input_ids = list(range(EnergyModuleHelper.NUMBER_OF_PORTS))
        else:
            input_id = int(input_id)
            if input_id < 0 or input_id >= EnergyModuleHelper.NUMBER_OF_PORTS:
                raise ValueError('Invalid input_id (should be 0-{0})'.format(EnergyModuleHelper.NUMBER_OF_PORTS - 1))
            input_ids = [input_id]
        address = int(energy_module.module.address)
        version = energy_module.version
        data = {}
        for input_id in input_ids:
            voltage = list(self._energy_communicator.do_command(address, EnergyAPI.get_voltage_sample_time(version), input_id, 0))
            current = list(self._energy_communicator.do_command(address, EnergyAPI.get_current_sample_time(version), input_id, 0))
            for entry in self._energy_communicator.do_command(address, EnergyAPI.get_voltage_sample_time(version), input_id, 1):
                if entry == float('inf'):
                    break
                voltage.append(entry)
            for entry in self._energy_communicator.do_command(address, EnergyAPI.get_current_sample_time(version), input_id, 1):
                if entry == float('inf'):
                    break
                current.append(entry)
            data[str(input_id)] = {'voltage': voltage,
                                   'current': current}
        return data

    def get_energy_frequency(self, energy_module, input_id=None):  # type: (EnergyModule, Optional[int]) -> Dict[str, Dict[str, Any]]
        if input_id is None:
            input_ids = list(range(EnergyModuleHelper.NUMBER_OF_PORTS))
        else:
            input_id = int(input_id)
            if input_id < 0 or input_id >= EnergyModuleHelper.NUMBER_OF_PORTS:
                raise ValueError('Invalid input_id (should be 0-{0})'.format(EnergyModuleHelper.NUMBER_OF_PORTS - 1))
            input_ids = [input_id]
        address = int(energy_module.module.address)
        version = energy_module.version
        data = {}
        for input_id in input_ids:
            voltage = self._energy_communicator.do_command(address, EnergyAPI.get_voltage_sample_frequency(version), input_id, 20)
            current = self._energy_communicator.do_command(address, EnergyAPI.get_current_sample_frequency(version), input_id, 20)
            # The received data has a length of 40; 20 harmonics entries, and 20 phase entries. For easier usage, the
            # API calls splits them into two parts so the customers doesn't have to do the splitting.
            data[str(input_id)] = {'voltage': [voltage[:20], voltage[20:]],
                                   'current': [current[:20], current[20:]]}
        return data

    def get_realtime_p1(self, energy_module):  # type: (EnergyModule) -> List[Dict[str, Any]]
        raise UnsupportedException()

    def _get_voltages(self, energy_module):  # type: (EnergyModule) -> List[float]
        cmd = EnergyAPI.get_voltage(energy_module.version, phase=None)
        return [0.0 if value is None else value  # Work around mypy limitation
                for value in (EnergyModuleHelper._convert_nan(voltage, default=0.0)
                              for voltage in list(self._energy_communicator.do_command(int(energy_module.module.address), cmd)))]

    def _get_currents(self, energy_module):  # type: (EnergyModule) -> List[float]
        cmd = EnergyAPI.get_current(energy_module.version, phase=None)
        return [0.0 if value is None else value  # Work around mypy limitation
                for value in (EnergyModuleHelper._convert_nan(current, default=0.0)
                              for current in list(self._energy_communicator.do_command(int(energy_module.module.address), cmd)))]

    def _get_frequencies(self, energy_module):  # type: (EnergyModule) -> List[float]
        cmd = EnergyAPI.get_frequency(energy_module.version)
        return [0.0 if value is None else value  # Work around mypy limitation
                for value in (EnergyModuleHelper._convert_nan(frequency, default=0.0)
                              for frequency in list(self._energy_communicator.do_command(int(energy_module.module.address), cmd)))]

    def _get_powers(self, energy_module):  # type: (EnergyModule) -> List[float]
        cmd = EnergyAPI.get_power(energy_module.version)
        return [0.0 if value is None else value  # Work around mypy limitation
                for value in (EnergyModuleHelper._convert_nan(power, default=0.0)
                              for power in list(self._energy_communicator.do_command(int(energy_module.module.address), cmd)))]


class PowerModuleHelper(EnergyModuleHelper):
    NUMBER_OF_PORTS = EnergyEnums.NUMBER_OF_PORTS[EnergyEnums.Version.POWER_MODULE]

    def _get_voltages(self, energy_module):  # type: (EnergyModule) -> List[float]
        cmd = EnergyAPI.get_voltage(energy_module.version, phase=None)
        raw_voltage = self._energy_communicator.do_command(int(energy_module.module.address), cmd)
        return [0.0 if value is None else value  # Work around mypy limitation
                for value in (EnergyModuleHelper._convert_nan(raw_voltage[0], default=0.0)
                              for _ in range(PowerModuleHelper.NUMBER_OF_PORTS))]

    def _get_frequencies(self, energy_module):  # type: (EnergyModule) -> List[float]
        cmd = EnergyAPI.get_frequency(energy_module.version)
        raw_frequency = self._energy_communicator.do_command(int(energy_module.module.address), cmd)
        return [0.0 if value is None else value  # Work around mypy limitation
                for value in (EnergyModuleHelper._convert_nan(raw_frequency[0], default=0.0)
                              for _ in range(PowerModuleHelper.NUMBER_OF_PORTS))]

    def configure_cts(self, energy_module):  # type: (EnergyModule) -> None
        address = int(energy_module.module.address)
        sensor_settings = []
        for ct in sorted(energy_module.cts, key=lambda c: c.ct_id):
            if ct.sensor_type in [2, 3]:
                sensor_settings.append(ct.sensor_type)
            else:
                sensor_settings.append(2)

        self._energy_communicator.do_command(address, EnergyAPI.set_sensor_types(energy_module.version),
                                             *sensor_settings)

    def get_energy_time(self, energy_module, input_id=None):  # type: (EnergyModule, Optional[int]) -> Dict[str, Dict[str, Any]]
        raise UnsupportedException()

    def get_energy_frequency(self, energy_module, input_id=None):  # type: (EnergyModule, Optional[int]) -> Dict[str, Dict[str, Any]]
        raise UnsupportedException()
