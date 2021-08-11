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
deliveries api description
"""

import cherrypy
import logging
import ujson as json

from ioc import INJECTED, Inject

from gateway.api.serializers import DeliverySerializer
from gateway.delivery_controller import DeliveryController
from gateway.dto import DeliveryDTO
from gateway.exceptions import UnAuthorizedException, ItemDoesNotExistException, ParseException
from gateway.models import User, Delivery
from gateway.webservice_v1 import RestAPIEndpoint, openmotics_api_v1, expose

if False:  # MyPy
    from gateway.authentication_controller import AuthenticationToken
    from typing import List

logger = logging.getLogger(__name__)


@expose
class Deliveries(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/deliveries'

    @Inject
    def __init__(self, delivery_controller=INJECTED):
        # type: (DeliveryController) -> None
        super(Deliveries, self).__init__()
        self.delivery_controller = delivery_controller
        # Set a custom route dispatcher in the class so that you have full
        # control over how the routes are defined.
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_deliveries', '',
                                      controller=self, action='get_deliveries',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_delivery', '/:delivery_id',
                                      controller=self, action='get_delivery',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_delivery_history', '/history',
                                      controller=self, action='get_delivery_history',
                                      conditions={'method': ['GET']})
        # --- POST ---
        self.route_dispatcher.connect('post_delivery', '',
                                      controller=self, action='post_delivery',
                                      conditions={'method': ['POST']})
        # --- PUT ---
        self.route_dispatcher.connect('put_delivery_pickup', '/:delivery_id/pickup',
                                      controller=self, action='put_delivery_pickup',
                                      conditions={'method': ['PUT']})

    @openmotics_api_v1(auth=True, pass_token=True, check={'user_id': int, 'delivery_type': str})
    def get_deliveries(self, auth_token, user_id=None, delivery_type=None):
        # type: (AuthenticationToken, int, str) -> str
        # get all the deliveries
        deliveries = self.delivery_controller.load_deliveries(user_id=user_id, delivery_type=delivery_type)  # type: List[DeliveryDTO]

        # filter the deliveries for only the user id when they are not technician or admin
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            deliveries = [delivery for delivery in deliveries if auth_token.user.id in [delivery.user_id_delivery, delivery.user_id_pickup]]

        deliveries_serial = [DeliverySerializer.serialize(delivery) for delivery in deliveries]
        return json.dumps(deliveries_serial)

    @openmotics_api_v1(auth=True, pass_token=True)
    def get_delivery(self, delivery_id, auth_token):
        # type: (int, AuthenticationToken) -> str
        delivery = self.delivery_controller.load_delivery(delivery_id)
        if delivery is None:
            raise ItemDoesNotExistException('Could not find the delivery with id: {}'.format(delivery_id))
        user_id = auth_token.user.id
        user_role = auth_token.user.role
        if user_role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            if user_id not in [delivery.user_id_delivery, delivery.user_id_pickup]:
                raise UnAuthorizedException('You are not allowed to request this delivery')
        deliveries_serial = DeliverySerializer.serialize(delivery)
        return json.dumps(deliveries_serial)

    @openmotics_api_v1(auth=True, pass_token=True,
                       check={'user_id': int, 'after': int, 'pagesize': int}, check_for_missing=False)
    def get_delivery_history(self, user_id, auth_token, after=0, pagesize=100):
        # type: (int, AuthenticationToken, int, int) -> str
        deliveries = self.delivery_controller.load_deliveries(user_id=user_id, history=True, from_id=after, limit=pagesize)
        # filter the deliveries for only the user id when they are not technician or admin
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            deliveries = [delivery for delivery in deliveries if auth_token.user.id in [delivery.user_id_delivery, delivery.user_id_pickup]]
        deliveries_serial = [DeliverySerializer.serialize(delivery) for delivery in deliveries]
        return json.dumps(deliveries_serial)

    @openmotics_api_v1(auth=False, pass_token=True, expect_body_type='JSON')
    def post_delivery(self, auth_token=None, request_body=None):
        try:
            delivery_dto = DeliverySerializer.deserialize(request_body)
        except Exception as ex:
            raise ParseException('Could not create a valid delivery from the passed json data: {}'.format(ex))
        if delivery_dto.type == Delivery.DeliveryType.RETURN:
            if auth_token is None or auth_token.user.role == User.UserRoles.COURIER:
                raise UnAuthorizedException('To create a return delivery, you need to be logged in as USER, ADMIN or TECHNICIAN')

        saved_delivery = self.delivery_controller.save_delivery(delivery_dto)
        if saved_delivery is None:
            raise RuntimeError('Unexpected error: Delivery is None when save_delivery is called')
        saved_delivery_serial = DeliverySerializer.serialize(saved_delivery)
        return json.dumps(saved_delivery_serial)

    @openmotics_api_v1(auth=True, pass_token=True)
    def put_delivery_pickup(self, delivery_id, auth_token):
        # type: (int, AuthenticationToken) -> str
        delivery_dto = self.delivery_controller.load_delivery(delivery_id)
        if delivery_dto is None:
            raise ItemDoesNotExistException('Cannot pickup a delivery that does not exists: id: {}'.format(delivery_id))

        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            auth_user_id = auth_token.user.id
            if auth_user_id not in [delivery_dto.user_id_delivery, delivery_dto.user_id_pickup]:
                raise UnAuthorizedException('Cannot pick up a package that is not yours when you are not admin or technician')

        delivery_dto_returned = self.delivery_controller.pickup_delivery(delivery_id)
        if delivery_dto_returned is None:
            raise RuntimeError('Unexpected error: Delivery is None when pickup_delivery is called')
        delivery_serial = DeliverySerializer.serialize(delivery_dto_returned)
        return json.dumps(delivery_serial)
