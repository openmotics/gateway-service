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
from gateway.dto import RealtimeEnergyDTO
from gateway.enums import EnergyEnums
from gateway.exceptions import UnsupportedException
from gateway.models import EnergyModule
from gateway.energy.module_helper import ModuleHelper
from gateway.energy.energy_api import EnergyAPI

if False:  # MYPY
    from gateway.energy.energy_command import EnergyCommand
    from typing import Dict, Optional, List, Tuple, Any, Callable, Union, TypeVar
    T = TypeVar('T', bound=Union[int, float])

logger = logging.getLogger(__name__)


class P1ConcentratorHelper(ModuleHelper):
    NUMBER_OF_PORTS = EnergyEnums.NUMBER_OF_PORTS[EnergyEnums.Version.P1_CONCENTRATOR]

    def get_realtime(self, energy_module):  # type: (EnergyModule) -> Dict[int, RealtimeEnergyDTO]
        data = {}
        statuses = self._get_statuses(energy_module=energy_module)
        voltages = self._get_voltages(energy_module=energy_module)
        frequencies = self._get_frequencies(energy_module=energy_module)
        currents = self._get_currents(energy_module=energy_module)
        powers = self._get_powers(energy_module=energy_module)
        for port_id in range(self.__class__.NUMBER_OF_PORTS):
            if statuses[port_id]:
                data[port_id] = RealtimeEnergyDTO(voltage=voltages[port_id],
                                                  frequency=frequencies[port_id],
                                                  power=powers[port_id],
                                                  current=currents[port_id])
            else:
                data[port_id] = RealtimeEnergyDTO(voltage=0.0, frequency=0.0, power=0.0, current=0.0)
        return data

    def get_information(self, energy_module):  # type: (EnergyModule) -> Tuple[bool, Optional[str]]
        raise NotImplementedError()  # TODO

    def get_day_counters(self, energy_module):  # type: (EnergyModule) -> List[Optional[int]]
        cmd = EnergyAPI.get_day_energy(energy_module.version)
        return [None if value is None else int(value * 1000)
                for value in self._parse_payload(cmd=cmd,
                                                 energy_module=energy_module,
                                                 field_length=10,
                                                 padding_length=4,
                                                 cast=float)]

    def get_night_counters(self, energy_module):  # type: (EnergyModule) -> List[Optional[int]]
        cmd = EnergyAPI.get_night_energy(energy_module.version)
        return [None if value is None else int(value * 1000)
                for value in self._parse_payload(cmd=cmd,
                                                 energy_module=energy_module,
                                                 field_length=10,
                                                 padding_length=4,
                                                 cast=float)]

    def configure_cts(self, energy_module):  # type: (EnergyModule) -> None
        _ = self, energy_module
        return  # Accept these calls for now

    def set_module_voltage(self, energy_module, voltage):  # type: (EnergyModule, float) -> None
        raise UnsupportedException()

    def get_energy_time(self, energy_module, input_id=None):  # type: (EnergyModule, Optional[int]) -> Dict[str, Dict[str, Any]]
        raise UnsupportedException()

    def get_energy_frequency(self, energy_module, input_id=None):  # type: (EnergyModule, Optional[int]) -> Dict[str, Dict[str, Any]]
        raise UnsupportedException()

    def get_realtime_p1(self, energy_module):  # type: (EnergyModule) -> List[Dict[str, Any]]
        statuses = self._get_statuses(energy_module=energy_module)
        timestamps = self._get_timestamp(energy_module=energy_module)
        eans1 = self._get_meter(energy_module=energy_module, meter_type=1)
        eans2 = self._get_meter(energy_module=energy_module, meter_type=2)
        currents = self._get_currents(energy_module=energy_module)
        voltages = self._get_voltages(energy_module=energy_module)
        consumptions1 = self._get_consumption_tariff(energy_module=energy_module, tariff_type=1)
        consumptions2 = self._get_consumption_tariff(energy_module=energy_module, tariff_type=2)
        injections1 = self._get_injection_tariff(energy_module=energy_module, tariff_type=1)
        injections2 = self._get_injection_tariff(energy_module=energy_module, tariff_type=2)
        tariff_indicators = self._get_tariff_indicator(energy_module=energy_module)
        gas_consumptions = self._get_gas_consumption(energy_module=energy_module)

        # TODO: Return DTO
        values = []
        for port_id, status in enumerate(statuses):
            if status:
                values.append({'device_id': '{}.{}'.format(energy_module.module.address, port_id),
                               'module_id': energy_module.number,
                               'port_id': port_id,
                               'timestamp': timestamps[port_id],
                               'gas': {'ean': eans2[port_id].strip(),
                                       'consumption': gas_consumptions[port_id]},
                               'electricity': {'ean': eans1[port_id].strip(),
                                               'current': currents[port_id],
                                               'voltage': voltages[port_id],
                                               'consumption_tariff1': consumptions1[port_id],
                                               'consumption_tariff2': consumptions2[port_id],
                                               'injection_tariff1': injections1[port_id],
                                               'injection_tariff2': injections2[port_id],
                                               'tariff_indicator': tariff_indicators[port_id]}})

        return values

    def _get_statuses(self, energy_module):  # type: (EnergyModule) -> List[bool]
        cmd = EnergyAPI.get_status_p1(energy_module.version)
        payload = self._energy_communicator.do_command(int(energy_module.module.address), cmd)[0]
        return [(payload & 1 << port_id) != 0
                for port_id in range(P1ConcentratorHelper.NUMBER_OF_PORTS)]

    def _get_voltages(self, energy_module):  # type: (EnergyModule) -> List[float]
        return [voltage['phase1'] or 0.0
                for voltage in self._get_phase_voltages(energy_module=energy_module)]

    def _get_phase_voltages(self, energy_module):  # type: (EnergyModule) -> List[Dict[str, Optional[float]]]
        values = {}
        for phase in range(1, 4):
            cmd = EnergyAPI.get_voltage(energy_module.version, phase=phase)
            values[phase] = self._parse_payload(cmd=cmd,
                                                energy_module=energy_module,
                                                field_length=5,
                                                padding_length=2,
                                                cast=float)
        return [{'phase1': values[1][port_id],
                 'phase2': values[2][port_id],
                 'phase3': values[3][port_id]} for port_id in range(P1ConcentratorHelper.NUMBER_OF_PORTS)]

    def _get_currents(self, energy_module):  # type: (EnergyModule) -> List[float]
        return [sum(value for value in current.values() if value is not None)
                for current in self._get_phase_currents(energy_module=energy_module)]

    def _get_phase_currents(self, energy_module):  # type: (EnergyModule) -> List[Dict[str, Optional[float]]]
        values = {}
        for phase in range(1, 4):
            cmd = EnergyAPI.get_current(energy_module.version, phase=phase)
            values[phase] = self._parse_payload(cmd=cmd,
                                                energy_module=energy_module,
                                                field_length=3,
                                                padding_length=2,
                                                cast=float)
        return [{'phase1': values[1][port_id],
                 'phase2': values[2][port_id],
                 'phase3': values[3][port_id]} for port_id in range(P1ConcentratorHelper.NUMBER_OF_PORTS)]

    def _get_powers(self, energy_module):  # type: (EnergyModule) -> List[float]
        delivered_powers = self._get_delivered_powers(energy_module=energy_module)
        received_powers = self._get_received_powers(energy_module=energy_module)
        return [((delivered_powers[port_id] or 0.0) - (received_powers[port_id] or 0.0)) * 1000
                for port_id in range(P1ConcentratorHelper.NUMBER_OF_PORTS)]

    def _get_delivered_powers(self, energy_module):  # type: (EnergyModule) -> List[Optional[float]]
        cmd = EnergyAPI.get_delivered_power(energy_module.version)
        return self._parse_payload(cmd=cmd,
                                   energy_module=energy_module,
                                   field_length=6,
                                   padding_length=3,
                                   cast=float)

    def _get_received_powers(self, energy_module):  # type: (EnergyModule) -> List[Optional[float]]
        cmd = EnergyAPI.get_received_power(energy_module.version)
        return self._parse_payload(cmd=cmd,
                                   energy_module=energy_module,
                                   field_length=6,
                                   padding_length=3,
                                   cast=float)

    def _get_frequencies(self, energy_module):  # type: (EnergyModule) -> List[float]
        _ = self, energy_module
        return [0.0 for _ in range(P1ConcentratorHelper.NUMBER_OF_PORTS)]

    def _get_meter(self, energy_module, meter_type=1):  # type: (EnergyModule, int) -> List[str]
        cmd = EnergyAPI.get_meter_p1(energy_module.version, meter_type=meter_type)
        return [value or ''
                for value in self._parse_payload(cmd=cmd,
                                                 energy_module=energy_module,
                                                 field_length=28,
                                                 padding_length=0,
                                                 filter_status=False)]

    def _get_timestamp(self, energy_module):  # type: (EnergyModule) -> List[Optional[float]]
        cmd = EnergyAPI.get_timestamp_p1(energy_module.version)
        return self._parse_payload(cmd=cmd,
                                   energy_module=energy_module,
                                   field_length=12,
                                   padding_length=1,
                                   cast=float)

    def _get_gas_consumption(self, energy_module):  # type: (EnergyModule) -> List[Optional[float]]
        cmd = EnergyAPI.get_gas_consumption_p1(energy_module.version)
        return self._parse_payload(cmd=cmd,
                                   energy_module=energy_module,
                                   field_length=9,
                                   padding_length=3,
                                   cast=float)

    def _get_consumption_tariff(self, energy_module, tariff_type=None):  # type: (EnergyModule, int) -> List[Optional[float]]
        cmd = EnergyAPI.get_consumption_tariff_p1(energy_module.version, tariff_type=tariff_type)
        return self._parse_payload(cmd=cmd,
                                   energy_module=energy_module,
                                   field_length=10,
                                   padding_length=4,
                                   cast=float)

    def _get_injection_tariff(self, energy_module, tariff_type=None):  # type: (EnergyModule, int) -> List[Optional[float]]
        cmd = EnergyAPI.get_injection_tariff_p1(energy_module.version, tariff_type=tariff_type)
        return self._parse_payload(cmd=cmd,
                                   energy_module=energy_module,
                                   field_length=10,
                                   padding_length=4,
                                   cast=float)

    def _get_tariff_indicator(self, energy_module):  # type: (EnergyModule) -> List[Optional[float]]
        cmd = EnergyAPI.get_tariff_indicator_p1(energy_module.version)
        return self._parse_payload(cmd=cmd,
                                   energy_module=energy_module,
                                   field_length=4,
                                   padding_length=0,
                                   cast=float)

    def _parse_payload(self, cmd, energy_module, field_length, padding_length, cast=None, filter_status=True):  # type: (EnergyCommand, EnergyModule, int, int, Optional[Callable[[Any], Any]], bool) -> List[Optional[Any]]
        statuses = [] if filter_status is False else self._get_statuses(energy_module=energy_module)
        part_length = field_length + padding_length
        payload = self._energy_communicator.do_command(int(energy_module.module.address), cmd)[0]
        data = []  # type: List[Optional[Any]]
        if cast is None:
            cast = lambda x: x
        for port_id in range(P1ConcentratorHelper.NUMBER_OF_PORTS):
            value = None
            if not filter_status or statuses[port_id]:
                try:
                    value = cast(payload[port_id * part_length:(port_id + 1) * part_length][:field_length])
                except ValueError:
                    pass
            data.append(value)
        return data
