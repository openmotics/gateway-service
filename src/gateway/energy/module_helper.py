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
from ioc import Inject, INJECTED
from gateway.dto import RealtimeEnergyDTO
from gateway.models import EnergyModule

if False:  # MYPY
    from typing import Dict, Tuple, Optional, List, Any, TypeVar, Union
    from gateway.energy.energy_communicator import EnergyCommunicator
    T = TypeVar('T', bound=Union[int, float])

logger = logging.getLogger(__name__)


class ModuleHelper(object):
    @Inject
    def __init__(self, energy_communicator=INJECTED):
        self._energy_communicator = energy_communicator  # type: EnergyCommunicator  # TODO: Rename

    def get_realtime(self, energy_module):  # type: (EnergyModule) -> Dict[int, RealtimeEnergyDTO]
        raise NotImplementedError()

    def get_information(self, energy_module):  # type: (EnergyModule) -> Tuple[bool, Optional[str]]
        raise NotImplementedError()

    def get_day_counters(self, energy_module):  # type: (EnergyModule) -> List[Optional[int]]
        raise NotImplementedError()

    def get_night_counters(self, energy_module):  # type: (EnergyModule) -> List[Optional[int]]
        raise NotImplementedError()

    def configure_cts(self, energy_module):  # type: (EnergyModule) -> None
        raise NotImplementedError()

    def set_module_voltage(self, energy_module, voltage):  # type: (EnergyModule, float) -> None
        raise NotImplementedError()

    def get_energy_time(self, energy_module, input_id=None):  # type: (EnergyModule, Optional[int]) -> Dict[str, Dict[str, Any]]
        raise NotImplementedError()

    def get_energy_frequency(self, energy_module, input_id=None):  # type: (EnergyModule, Optional[int]) -> Dict[str, Dict[str, Any]]
        raise NotImplementedError()

    def get_realtime_p1(self, energy_module):  # type: (EnergyModule) -> List[Dict[str, Any]]
        raise NotImplementedError()
