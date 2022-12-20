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
from ioc import INJECTED, Inject

if False:  # MYPY
    from typing import Optional, Any
    from gateway.output_controller import OutputController

logger = logging.getLogger(__name__)


@Inject
class ValveDriver(object):

    def __init__(self, valve, output_controller=INJECTED):  # type: (Valve, OutputController) -> None
        self._output_controller = output_controller
        self._valve = valve
        self._percentage = 0
        self._current_percentage = None # type: Optional[int]
        self._desired_percentage = 0
        self._time_state_changed = None  # type: Optional[float]
        self._state_change_lock = Lock()

    @property
    def id(self):  # type: () -> int
        return self._valve.id

    @property
    def percentage(self):  # type: () -> Optional[int]
        return self._current_percentage

    def is_open(self, percentage=0):  # type: (int) -> bool
        # return true if valve is open, return false if valve is not open or still moving
        if self._current_percentage is None:
            return False
        now_open = self._current_percentage > percentage
        return now_open if not self.in_transition else False

    @property
    def in_transition(self):  # type: () -> bool
        with self._state_change_lock:
            now = time.time()
            if self._time_state_changed is not None:
                return self._time_state_changed + float(self._valve.delay) > now
            else:
                return False

    def update(self, valve):  # type: (Valve) -> None
        with self._state_change_lock:
            self._valve = valve

    def steer_output(self):  # type: () -> None
        with self._state_change_lock:
            # update the timestamps of the valves so the pump delays etc. are taken into account
            if self._current_percentage != self._desired_percentage:
                logger.info('Valve {0} (output {1}) changing from {2}% to {3}%'.format(
                    self._valve.id, self._valve.output.number, self._current_percentage, self._desired_percentage
                ))
                desired_on = self._desired_percentage > 0
                self._output_controller.set_output_status(output_id=self._valve.output.number,
                                                          is_on=desired_on,
                                                          dimmer=self._desired_percentage)
                self._current_percentage = self._desired_percentage
                # TODO: use the updated_at timestamp of the output in the outputcontroller cache
                self._time_state_changed = time.time()

    def set(self, percentage):  # type: (float) -> None
        self._desired_percentage = int(percentage)

    @property
    def will_open(self):  # type: () -> bool
        if self._current_percentage is None:
            return False
        return self._desired_percentage > 0 and self._current_percentage == 0

    @property
    def will_close(self):  # type: () -> bool
        if self._current_percentage is None:
            return False
        return self._desired_percentage == 0 and self._current_percentage > 0

    def open(self):  # type: () -> None
        self.set(100)

    def close(self):  # type: () -> None
        self.set(0)

    def __str__(self):
        return 'Valve driver for valve {0} at {1}'.format(self._valve.id, hex(id(self)))

    def __hash__(self):
        return self._valve.id

    def __eq__(self, other):  # type: (Any) -> bool
        if not isinstance(other, Valve):
            # don't attempt to compare against unrelated types
            return NotImplemented
        return self.id == other.id
