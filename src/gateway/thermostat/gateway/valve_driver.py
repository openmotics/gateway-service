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
    from gateway.gateway_api import GatewayApi
    from gateway.output_controller import OutputController

logger = logging.getLogger('openmotics')


@Inject
class ValveDriver(object):

    def __init__(self, valve, gateway_api=INJECTED, output_controller=INJECTED):  # type: (Valve, GatewayApi, OutputController) -> None
        """ Create a valve object """
        self._gateway_api = gateway_api
        self._output_controller = output_controller
        self._valve = valve
        self._percentage = 0

        self._current_percentage = 0
        self._desired_percentage = 0
        self._time_state_changed = None
        self._state_change_lock = Lock()

    @property
    def number(self):
        return self._valve.number

    @property
    def percentage(self):
        return self._current_percentage

    @property
    def pump_drivers(self):
        return [PumpDriver(pump, self._gateway_api) for pump in self._valve.pumps]

    def is_open(self):
        _now_open = self._current_percentage > 0
        return _now_open if not self.in_transition() else False

    def in_transition(self):
        with self._state_change_lock:
            now = time.time()
            if self._time_state_changed is not None:
                return self._time_state_changed + self._valve.delay > now
            else:
                return False

    def update_valve(self, valve):
        with self._state_change_lock:
            self._valve = valve

    def steer_output(self):
        with self._state_change_lock:
            if self._current_percentage != self._desired_percentage:
                output_nr = self._valve.output.number
                logger.info('Valve (output: {}) changing from {}% --> {}%'.format(output_nr,
                                                                                  self._current_percentage,
                                                                                  self._desired_percentage))
                output_status = self._desired_percentage > 0

                self._gateway_api.set_output_status(self._valve.output.number, output_status, dimmer=self._desired_percentage)
                try:
                    dimmable_output = self._output_controller.load_output(output_nr).module_type in ['d', 'D']
                except Exception:
                    dimmable_output = False
                if not dimmable_output:
                    # TODO: Implement PWM logic
                    logger.info('Valve (output: {}) using ON/OFF approximation - desired: {}%'.format(output_nr, self._desired_percentage))
                self._current_percentage = self._desired_percentage
                self._time_state_changed = time.time()

    def set(self, percentage):
        _percentage = int(percentage)
        logger.info('setting valve {} percentage to {}%'.format(self._valve.output.number, _percentage))
        self._desired_percentage = _percentage

    def will_open(self):
        return self._desired_percentage > 0 and self._current_percentage == 0

    def will_close(self):
        return self._desired_percentage == 0 and self._current_percentage > 0

    def open(self):
        self.set(100)

    def close(self):
        self.set(0)

    def __eq__(self, other):
        if not isinstance(other, Valve):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self._valve.number == other.number
