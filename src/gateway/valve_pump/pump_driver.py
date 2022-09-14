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
from ioc import INJECTED, Inject

if False:  # MYPY
    from typing import Optional, Any
    from gateway.models import Pump
    from gateway.output_controller import OutputController

logger = logging.getLogger(__name__)


@Inject
class PumpDriver(object):
    def __init__(self, pump, output_controller=INJECTED):  # type: (Pump, OutputController) -> None
        self._pump = pump
        self._output_controller = output_controller
        self._state = None  # type: Optional[bool]
        self._error = False

    def update(self, pump):  # type: (Pump) -> None
        self._pump = pump
        self._state = None
        self._error = False

    def _set_state(self, active):  # type: (bool) -> None
        if self._pump.output is None:
            logger.warning('Cannot set state on Pump {0} since it has no output'.format(self._pump.id))
            return
        output_number = self._pump.output.number
        dimmer = 100 if active else 0
        self._output_controller.set_output_status(output_id=output_number,
                                                  is_on=active,
                                                  dimmer=dimmer)
        self._state = active

    def turn_on(self):  # type: () -> None
        if self._state is True:
            return
        if self._state is None:
            logger.info('Ensuring pump {0} is on'.format(self._pump.id))
        else:
            logger.info('Turning on pump {0}'.format(self._pump.id))
        try:
            self._set_state(True)
            self._error = False
        except Exception:
            logger.error('There was a problem turning on pump {0}'.format(self._pump.id))
            self._error = True
            raise

    def turn_off(self):  # type: () -> None
        if self._state is False:
            return
        if self._state is None:
            logger.info('Ensuring pump {0} is off'.format(self._pump.id))
        else:
            logger.info('Turning off pump {0}'.format(self._pump.id))
        try:
            self._set_state(False)
            self._error = False
        except Exception:
            logger.error('There was a problem turning off pump {0}'.format(self._pump.id))
            self._error = True
            raise

    @property
    def state(self):  # type: () -> Optional[bool]
        return self._state

    @property
    def error(self):  # type: () -> bool
        return self._error

    @property
    def id(self):  # type: () -> int
        return self._pump.id

    @property
    def valve_ids(self):
        return [valve.id for valve in self._pump.valves]

    def __str__(self):
        return 'Pump driver for pump {0} at {1}'.format(self._pump.id, hex(id(self)))

    def __hash__(self):
        return self._pump.id

    def __eq__(self, other):  # type: (Any) -> bool
        if not isinstance(other, PumpDriver):
            return False
        return self.id == other.id
