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
from threading import Lock

from gateway.models import Valve
from gateway.thermostat.gateway.pump_driver import PumpDriver
from ioc import INJECTED, Inject

if False:  # MYPY
    from typing import Dict, List, Optional, Any
    from gateway.output_controller import OutputController

logger = logging.getLogger('openmotics')


@Inject
class ValveDriver(object):

    def __init__(self, valve, output_controller=INJECTED):  # type: (Valve, OutputController) -> None
        self._output_controller = output_controller
        self._valve = valve
        self._percentage = 0
        self._current_percentage = 0
        self._desired_percentage = 0
        self._time_state_changed = None  # type: Optional[float]
        self._pump_drivers = {}  # type: Dict[int, PumpDriver]
        self._state_change_lock = Lock()

    @property
    def number(self):  # type: () -> int
        return self._valve.number

    @property
    def percentage(self):  # type: () -> int
        return self._current_percentage

    @property
    def pump_drivers(self):  # type: () -> List[PumpDriver]
        drivers = []
        pump_ids = []
        for pump in self._valve.pumps:
            drivers.append(self._pump_drivers.setdefault(pump.id, PumpDriver(pump)))
            pump_ids.append(pump.id)
        for pump_id in list(self._pump_drivers.keys()):
            if pump_id not in pump_ids:
                self._pump_drivers.pop(pump_id)
        return list(self._pump_drivers.values())

    @property
    def is_open(self):  # type: () -> bool
        now_open = self._current_percentage > 0
        return now_open if not self.in_transition else False

    @property
    def in_transition(self):  # type: () -> bool
        with self._state_change_lock:
            now = time.time()
            if self._time_state_changed is not None:
                return self._time_state_changed + float(self._valve.delay) > now
            else:
                return False

    def update_valve(self, valve):  # type: (Valve) -> None
        with self._state_change_lock:
            self._valve = valve

    def steer_output(self):  # type: () -> None
        with self._state_change_lock:
            if self._current_percentage != self._desired_percentage:
                output_nr = self._valve.output.number
                logger.info('Valve (output: {0}) changing from {1}% --> {2}%'.format(output_nr,
                                                                                     self._current_percentage,
                                                                                     self._desired_percentage))
                output_status = self._desired_percentage > 0
                self._output_controller.set_output_status(output_id=self._valve.output.number,
                                                          is_on=output_status,
                                                          dimmer=self._desired_percentage)
                self._current_percentage = self._desired_percentage
                self._time_state_changed = time.time()

    def set(self, percentage):  # type: (float) -> None
        self._desired_percentage = int(percentage)

    @property
    def will_open(self):  # type: () -> bool
        return self._desired_percentage > 0 and self._current_percentage == 0

    @property
    def will_close(self):  # type: () -> bool
        return self._desired_percentage == 0 and self._current_percentage > 0

    def open(self):  # type: () -> None
        self.set(100)

    def close(self):  # type: () -> None
        self.set(0)

    def __eq__(self, other):  # type: (Any) -> bool
        if not isinstance(other, Valve):
            # don't attempt to compare against unrelated types
            return NotImplemented
        return self._valve.number == other.number
