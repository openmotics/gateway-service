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

logger = logging.getLogger('openmotics')


@Inject
class PumpDriver(object):

    def __init__(self, pump, gateway_api=INJECTED):
        """ Create a pump object
        :param pump: the pump object
        :type pump: gateway.thermostat.gateway.models.Pump
        :param gateway_api: Gateway API Controller
        :type gateway_api: gateway.gateway_api.GatewayApi
        """
        self._pump = pump
        self._gateway_api = gateway_api
        self._state = None
        self._error = False

    def _set_state(self, active):
        output_number = self._pump.output.number
        dimmer = 100 if active else 0
        self._gateway_api.set_output_status(output_number, active, dimmer=dimmer)
        self._state = active

    def turn_on(self):
        logger.info('turning on pump {}'.format(self._pump.number))
        try:
            self._set_state(True)
            self._error = False
        except Exception:
            logger.error('There was a problem turning on pump {}'.format(self._pump.number))
            self._error = True
            raise

    def turn_off(self):
        logger.info('turning off pump {}'.format(self._pump.number))
        try:
            self._set_state(False)
            self._error = False
        except Exception:
            logger.error('There was a problem turning off pump {}'.format(self._pump.number))
            self._error = True
            raise

    @property
    def state(self):
        return self._state

    @property
    def error(self):
        return self._error

    @property
    def number(self):
        return self._pump.number

    def __eq__(self, other):
        if not isinstance(other, PumpDriver):
            return False

        return self._pump.number == other.number
