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
RFID api description
"""

import cherrypy
import logging

from ioc import INJECTED, Inject
from gateway.api.serializers import RfidSerializer
from gateway.exceptions import ItemDoesNotExistException, UnAuthorizedException, WrongInputParametersException
from gateway.models import User
from gateway.rfid_controller import RfidController
from gateway.api.V1.webservice import RestAPIEndpoint, openmotics_api_v1, expose, AuthenticationLevel, ApiResponse

logger = logging.getLogger(__name__)


@expose
class Rfid(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/rfid'

    @Inject
    def __init__(self, rfid_controller=INJECTED):
        # type: (RfidController) -> None
        super(Rfid, self).__init__()
        self.rfid_controller = rfid_controller
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_rfids', '',
                                      controller=self, action='get_rfids',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_rfid', '/:rfid_id',
                                      controller=self, action='get_rfid',
                                      conditions={'method': ['GET']})
        # --- PUT ---
        self.route_dispatcher.connect('put_start_add', '/add_new/start',
                                      controller=self, action='put_start_add',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_cancel_add', '/add_new/cancel',
                                      controller=self, action='put_cancel_add',
                                      conditions={'method': ['PUT']})
        # --- DELETE ---
        self.route_dispatcher.connect('delete_rfid', '/:rfid_id',
                                      controller=self, action='delete_rfid',
                                      conditions={'method': ['DELETE']})

    @openmotics_api_v1(auth=True, pass_token=True, check={'user_id': int})
    def get_rfids(self, auth_token=None, user_id=None):
        rfids = self.rfid_controller.load_rfids(user_id=user_id)

        # filter the rfids if the role is not a super user
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            rfids = [rfid for rfid in rfids if rfid.user.id == auth_token.user.id]

        rfids_serial = [RfidSerializer.serialize(rfid) for rfid in rfids]
        return ApiResponse(body=rfids_serial)

    @openmotics_api_v1(auth=True, pass_token=True)
    def get_rfid(self, rfid_id, auth_token=None):
        rfid = self.rfid_controller.load_rfid(rfid_id)

        if rfid is None:
            raise ItemDoesNotExistException('RFID tag with id {} does not exists'.format(rfid_id))

        # filter the rfids if the role is not a super user
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            if rfid.user.id != auth_token.user.id:
                raise UnAuthorizedException('As a non admin or technician, you cannot request an rfid that is not yours')

        rfid_serial = RfidSerializer.serialize(rfid)
        return ApiResponse(body=rfid_serial)

    @openmotics_api_v1(auth=True, pass_token=True, expect_body_type='JSON', auth_level=AuthenticationLevel.HIGH,
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.USER])
    def put_start_add(self, auth_token, request_body):
        # Authentication - only ADMIN & TECHNICIAN can create new rfid entry for everyone.
        # USER can only create new rfid entry linked to itself.

        if 'user_id' not in request_body or 'label' not in request_body:
            raise WrongInputParametersException('When adding a new rfid, there is the need for the user_id and a label in the request body.')
        user_id = request_body['user_id']
        label = request_body['label']

        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            if user_id != auth_token.user.id:
                raise UnAuthorizedException('Cannot start an add_rfid_badge session: As a normal user, you only can add a badge to yourselves')

        if not self.user_controller.user_id_exists(user_id):
            raise ItemDoesNotExistException('Cannot start add_rfid_badge session: There is no user with user_id: {}'.format(user_id))

        user = self.user_controller.load_user(user_id)
        self.rfid_controller.start_add_rfid_session(user, label)
        return ApiResponse(status_code=204)

    @openmotics_api_v1(auth=True, pass_token=True, expect_body_type=None, auth_level=AuthenticationLevel.HIGH,
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.USER])
    def put_cancel_add(self, auth_token):
        # Authentication - only ADMIN & TECHNICIAN can always cancel 'add new rfid mode'.
        # USER can only cancel mode if adding rfid to his account

        current_rfid_user_id = self.rfid_controller.get_current_add_rfid_session_info()
        # When there is no session running, simply return
        if current_rfid_user_id is None:
            return ApiResponse(status_code=204)
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            if current_rfid_user_id != auth_token.user.id:
                raise UnAuthorizedException('Cannot start an add_rfid_badge session: As a normal user, you only can add a badge to yourselves')

        self.rfid_controller.stop_add_rfid_session()
        return ApiResponse(status_code=204)

    @openmotics_api_v1(auth=True, pass_token=True)
    def delete_rfid(self, rfid_id, auth_token=None):
        # first fetch the rfid tag to check if it exists and if the deletion is authorized
        rfid = self.rfid_controller.load_rfid(rfid_id)
        if rfid is None:
            raise ItemDoesNotExistException("Cannot delete RFID: tag with id '{}' does not exist".format(rfid_id))

        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            if rfid.user.id != auth_token.user.id:
                raise UnAuthorizedException('As a non admin or technician, you cannot delete an rfid that is not yours')

        self.rfid_controller.delete_rfid(rfid_id)
        return ApiResponse(status_code=204)
