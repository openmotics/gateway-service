# Copyright (C) 2016 OpenMotics BV
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
The GatewayApi defines high level functions, these are used by the interface
and call the master_api to complete the actions.
"""

from __future__ import absolute_import

from gateway.hal.master_controller import MasterController
from ioc import INJECTED, Inject, Injectable, Singleton


@Injectable.named('gateway_api')
@Singleton
class GatewayApi(object):
    """ The GatewayApi combines master_api functions into high level functions. """

    @Inject
    def __init__(self, master_controller=INJECTED):
        # type: (MasterController) -> None
        self.__master_controller = master_controller  # type: MasterController

    # Sensors

    def set_virtual_sensor(self, sensor_id, temperature, humidity, brightness):
        # TODO: work with sensor controller
        # TODO: add other sensors too (e.g. from database <-- plugins)
        """ Set the temperature, humidity and brightness value of a virtual sensor. """
        self.__master_controller.set_virtual_sensor(sensor_id, temperature, humidity, brightness)
