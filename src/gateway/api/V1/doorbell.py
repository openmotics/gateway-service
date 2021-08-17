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
doorbell api description
"""

import cherrypy
import logging
import ujson as json

from ioc import INJECTED, Inject

from gateway.api.serializers import DoorbellSerializer
from esafe.rebus.rebus_controller import RebusController
from gateway.exceptions import ItemDoesNotExistException, InvalidOperationException
from gateway.webservice_v1 import RestAPIEndpoint, openmotics_api_v1, expose

logger = logging.getLogger(__name__)


@expose
class Doorbell(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/doorbells'

    @Inject
    def __init__(self, rebus_controller=INJECTED):
        # type: (RebusController) -> None
        super(Doorbell, self).__init__()
        self.rebus_controller = rebus_controller
        # Set a custom route dispatcher in the class so that you have full
        # control over how the routes are defined.
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_doorbells', '',
                                      controller=self, action='get_doorbells',
                                      conditions={'method': ['GET']})
        # --- PUT ---
        self.route_dispatcher.connect('put_ring_doorbell', '/ring/:rebus_id',
                                      controller=self, action='put_ring_doorbell',
                                      conditions={'method': ['PUT']})

    @openmotics_api_v1(auth=False, expect_body_type=None)
    def get_doorbells(self):
        # type: () -> str
        self._check_controller()
        doorbells = self.rebus_controller.get_doorbells()
        doorbells_serial = [DoorbellSerializer.serialize(box) for box in doorbells]
        return json.dumps(doorbells_serial)

    @openmotics_api_v1(auth=False, expect_body_type=None, check={'rebus_id': int})
    def put_ring_doorbell(self, rebus_id):
        self._check_controller()
        doorbells = self.rebus_controller.get_doorbells()
        if rebus_id not in [doorbell.id for doorbell in doorbells]:
            raise ItemDoesNotExistException('Cannot ring doorbell with id: {}. Doorbell does not exists'.format(rebus_id))
        self.rebus_controller.ring_doorbell(rebus_id)

    def _check_controller(self):
        if self.rebus_controller is None:
            raise InvalidOperationException('Cannot check doorbells, eSafe controller is None')
