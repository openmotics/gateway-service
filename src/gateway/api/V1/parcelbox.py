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
parcelbox api description
"""

import cherrypy
import logging
import random

from ioc import INJECTED, Inject

from gateway.api.serializers import ParcelBoxSerializer, DeliverySerializer
from esafe.rebus.rebus_controller import RebusController
from gateway.exceptions import UnAuthorizedException, ItemDoesNotExistException, InvalidOperationException, WrongInputParametersException, StateException
from gateway.models import User
from gateway.api.V1.webservice import RestAPIEndpoint, openmotics_api_v1, expose, ApiResponse

if False:  # MyPy
    from typing import Optional
    from gateway.authentication_controller import AuthenticationToken
    from gateway.delivery_controller import DeliveryController

logger = logging.getLogger(__name__)


@expose
class ParcelBox(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/parcelboxes'

    @Inject
    def __init__(self, rebus_controller=INJECTED, delivery_controller=INJECTED):
        # type: (RebusController, DeliveryController) -> None
        super(ParcelBox, self).__init__()
        self.rebus_controller = rebus_controller
        self.delivery_controller = delivery_controller
        # Set a custom route dispatcher in the class so that you have full
        # control over how the routes are defined.
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_parcelboxes', '',
                                      controller=self, action='get_parcelboxes',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_parcelbox', '/:rebus_id',
                                      controller=self, action='get_parcelbox',
                                      conditions={'method': ['GET']})
        # --- PUT ---
        self.route_dispatcher.connect('put_open_random_parcelbox', '/open',
                                      controller=self, action='put_parcelboxes',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_open_specific_parcelbox', '/:rebus_id',
                                      controller=self, action='put_parcelbox',
                                      conditions={'method': ['PUT']})

    @openmotics_api_v1(auth=False, pass_token=True, expect_body_type=None, check={'size': str, 'available': bool, 'show_deliveries': bool})
    def get_parcelboxes(self, auth_token=None, size=None, available=None, show_deliveries=None):
        # type: (Optional[AuthenticationToken], Optional[str], Optional[bool], Optional[bool]) -> ApiResponse
        self._check_controller()
        boxes = self.rebus_controller.get_parcelboxes(size=size, available=available)
        boxes_serial = [ParcelBoxSerializer.serialize(box) for box in boxes]
        if show_deliveries is True:
            if auth_token is None or auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.SUPER, User.UserRoles.TECHNICIAN]:
                raise UnAuthorizedException('Cannot include delivery information with the parcelboxes when not logged in as SUPER, ADMIN or TECHNICIAN.')
            for box in boxes_serial:
                deliveries = self.delivery_controller.load_deliveries_filter(delivery_parcelbox_rebus_id=box['id'])
                delivery = deliveries[0] if len(deliveries) == 1 else None
                if delivery is not None:
                    box['delivery'] = DeliverySerializer.serialize(delivery)
        return ApiResponse(body=boxes_serial)

    @openmotics_api_v1(auth=False, expect_body_type=None, check={'rebus_id': int})
    def get_parcelbox(self, rebus_id):
        self._check_controller()
        boxes = self.rebus_controller.get_parcelboxes(rebus_id=rebus_id)
        if len(boxes) != 1:
            raise ItemDoesNotExistException('Cannot find parcelbox with rebus id: {}'.format(rebus_id))
        box = boxes[0]
        box_serial = ParcelBoxSerializer.serialize(box)
        return ApiResponse(body=box_serial)

    @openmotics_api_v1(auth=False, expect_body_type=None, check={'size': str}, check_for_missing=True)
    def put_parcelboxes(self, size):
        logger.info('opening random parcelbox with size: {}'.format(size))
        self._check_controller()
        boxes = self.rebus_controller.get_parcelboxes(size=size, available=True)
        if len(boxes) == 0:
            raise InvalidOperationException('Cannot open box of size: {}, no boxes available'.format(size))
        random_index = random.randint(0, len(boxes)-1)
        box = self.rebus_controller.open_box(boxes[random_index].id)
        if box is None:
            raise StateException("Could not open the rebus lock, lock did not open upon request")
        box_serial = ParcelBoxSerializer.serialize(box)
        status_code = 200 if box.is_open else 500
        return ApiResponse(status_code=status_code, body=box_serial)

    @openmotics_api_v1(auth=True, pass_token=True, expect_body_type='JSON', check={'rebus_id': int})
    def put_parcelbox(self, rebus_id, request_body, auth_token):
        self._check_controller()
        if 'open' not in request_body:
            WrongInputParametersException('Expected json body with the open parameter')
        boxes = self.rebus_controller.get_parcelboxes(rebus_id=rebus_id)
        box = boxes[0] if len(boxes) == 1 else None

        if box is None:
            raise ItemDoesNotExistException('Cannot open mailbox with id: {}: it does not exists'.format(rebus_id))

        # auth check
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            deliveries = self.delivery_controller.load_deliveries(user_id=auth_token.user.id)
            if True not in [delivery.parcelbox_rebus_id == rebus_id for delivery in deliveries]:
                raise UnAuthorizedException('Cannot open parcelbox with id: {}: You are not admin, technician and the box does not belong to you'.format(rebus_id))

        if request_body['open'] is True:
            box = self.rebus_controller.open_box(box.id)
            if box is None:
                raise StateException("Could not open the rebus lock, lock did not open upon request")
        box_serial = ParcelBoxSerializer.serialize(box)
        status_code = 200 if box.is_open else 500
        return ApiResponse(status_code=status_code, body=box_serial)

    def _check_controller(self):
        if self.rebus_controller is None:
            raise InvalidOperationException('Cannot check parcelboxes, eSafe controller is None')
