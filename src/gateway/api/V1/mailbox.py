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
mailbox api description
"""

import cherrypy
import logging
import ujson as json

from ioc import INJECTED, Inject

from gateway.api.serializers import MailboxSerializer
from esafe.rebus.rebus_controller import RebusController
from gateway.exceptions import UnAuthorizedException, ItemDoesNotExistException, InvalidOperationException
from gateway.models import User
from gateway.webservice_v1 import RestAPIEndpoint, openmotics_api_v1, expose

if False:  # MyPy
    from typing import Dict, Any
    from gateway.authentication_controller import AuthenticationToken
    from gateway.delivery_controller import DeliveryController

logger = logging.getLogger(__name__)


@expose
class MailBox(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/mailboxes'

    @Inject
    def __init__(self, rebus_controller=INJECTED, delivery_controller=INJECTED):
        # type: (RebusController, DeliveryController) -> None
        super(MailBox, self).__init__()
        self.rebus_controller = rebus_controller
        self.delivery_controller = delivery_controller
        # Set a custom route dispatcher in the class so that you have full
        # control over how the routes are defined.
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_mailboxes', '',
                                      controller=self, action='get_mailboxes',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_mailbox', '/:rebus_id',
                                      controller=self, action='get_mailbox',
                                      conditions={'method': ['GET']})
        # --- PUT ---
        self.route_dispatcher.connect('put_open_mailbox', '/:rebus_id',
                                      controller=self, action='put_open_mailbox',
                                      conditions={'method': ['PUT']})

    @openmotics_api_v1(auth=False, expect_body_type=None)
    def get_mailboxes(self):
        # type: () -> str
        self._check_controller()
        boxes = self.rebus_controller.get_mailboxes()
        boxes_serial = [MailboxSerializer.serialize(box) for box in boxes]
        return json.dumps(boxes_serial)

    @openmotics_api_v1(auth=False, expect_body_type=None, check={'rebus_id': int})
    def get_mailbox(self, rebus_id):
        # type: (int) -> str
        self._check_controller()
        boxes = self.rebus_controller.get_mailboxes(rebus_id=rebus_id)
        if len(boxes) != 1:
            raise ItemDoesNotExistException('Cannot find mailbox with rebus id: {}'.format(rebus_id))
        box = boxes[0]
        box_serial = MailboxSerializer.serialize(box)
        return json.dumps(box_serial)

    @openmotics_api_v1(auth=True, pass_token=True, expect_body_type='JSON', check={'rebus_id': int})
    def put_open_mailbox(self, rebus_id, request_body, auth_token):
        # type: (int, Dict[str, Any], AuthenticationToken) -> str
        self._check_controller()
        if 'open' not in request_body:
            raise ValueError('Expected json body with the open parameter')
        boxes = self.rebus_controller.get_mailboxes(rebus_id=rebus_id)
        box = boxes[0] if len(boxes) == 1 else None

        if box is None:
            raise ItemDoesNotExistException('Cannot open mailbox with id: {}: it does not exists'.format(rebus_id))

        # auth check
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            if box.apartment is None:
                raise UnAuthorizedException('Cannot open mailbox with id: {}: You are not admin, techinican and the box has no owner'.format(rebus_id))
            apartment_id = box.apartment.id
            user_dto = self.user_controller.load_user_by_apartment_id(apartment_id)
            if user_dto.id != auth_token.user.id:
                raise UnAuthorizedException('UnAuthorized to open mailbox with id: {}: you are not admin, technician or the owner of the mailbox'.format(rebus_id))

        if request_body['open'] is True:
            box = self.rebus_controller.open_box(box.id)
        box_serial = MailboxSerializer.serialize(box) if box is not None else {}
        return json.dumps(box_serial)

    def _check_controller(self):
        if self.rebus_controller is None:
            raise InvalidOperationException('Cannot check mailboxes, eSafe controller is None')
