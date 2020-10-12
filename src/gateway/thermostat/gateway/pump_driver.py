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

logger = logging.getLogger('openmotics')


@Inject
class PumpDriver(object):
    def __init__(self, pump, output_controller=INJECTED):  # type: (Pump, OutputController) -> None
        self._pump = pump
        self._output_controller = output_controller
        self._state = None  # type: Optional[bool]
        self._error = False

    def _set_state(self, active):  # type: (bool) -> None
        if self._pump.output is None:
            logger.warning('Cannot set state on Pump {0} since it has no output'.format(self._pump.number))
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
        logger.info('Turning on pump {0}'.format(self._pump.number))
        try:
            self._set_state(True)
            self._error = False
        except Exception:
            logger.error('There was a problem turning on pump {0}'.format(self._pump.number))
            self._error = True
            raise

    def turn_off(self):  # type: () -> None
        if self._state is False:
            return
        logger.info('Turning off pump {0}'.format(self._pump.number))
        try:
            self._set_state(False)
            self._error = False
        except Exception:
            logger.error('There was a problem turning off pump {0}'.format(self._pump.number))
            self._error = True
            raise

    @property
    def state(self):  # type: () -> Optional[bool]
        return self._state

    @property
    def error(self):  # type: () -> bool
        return self._error

    @property
    def number(self):  # type: () -> int
        return self._pump.number

    def __eq__(self, other):  # type: (Any) -> bool
        if not isinstance(other, PumpDriver):
            return False
        return self._pump.number == other.number
