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
authenticate api description
"""

import cherrypy
import logging

from gateway.authentication_controller import AuthenticationToken
from gateway.enums import UserEnums
from gateway.exceptions import UnAuthorizedException, WrongInputParametersException
from gateway.api.V1.webservice import RestAPIEndpoint, openmotics_api_v1, expose, ApiResponse

logger = logging.getLogger(__name__)


@expose
class Authentication(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1'

    def __init__(self):
        # type: () -> None
        super(Authentication, self).__init__()
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- POST ---
        self.route_dispatcher.connect('authenticate_pin_code', '/authenticate/pin_code',
                                      controller=self, action='authenticate_pin_code',
                                      conditions={'method': ['POST']})
        self.route_dispatcher.connect('authenticate_rfid_tag', '/authenticate/rfid_tag',
                                      controller=self, action='authenticate_rfid_tag',
                                      conditions={'method': ['POST']})
        self.route_dispatcher.connect('deauthenticate', '/deauthenticate',
                                      controller=self, action='deauthenticate',
                                      conditions={'method': ['POST']})

    @openmotics_api_v1(auth=False, expect_body_type='JSON')
    def authenticate_pin_code(self, request_body):
        if 'pin_code' not in request_body:
            raise WrongInputParametersException('Expected a code in the request body json')
        success, data = self.authentication_controller.login_with_user_code(pin_code=request_body['pin_code'])
        return self.handle_authentication_result(success, data)

    @openmotics_api_v1(auth=False, expect_body_type='JSON')
    def authenticate_rfid_tag(self, request_body):
        if 'rfid_tag' not in request_body:
            raise WrongInputParametersException('Expected an rfid_tag in the request body json')
        success, data = self.authentication_controller.login_with_rfid_tag(rfid_tag_string=request_body['rfid_tag'])
        return self.handle_authentication_result(success, data)

    def handle_authentication_result(self, success, data):
        _ = self
        if success:
            if not isinstance(data, AuthenticationToken):
                raise RuntimeError('Retrieved success as true, but no authentication token')
            if not data.user.is_active:
                return ApiResponse(status_code=206, body={
                    'user_id': data.user.id,
                    'user_role': data.user.role,
                    'is_active': False
                })
            return ApiResponse(body=data.to_dict())
        else:
            raise UnAuthorizedException('could not authenticate user: {}'.format(data))

    @openmotics_api_v1(auth=True, pass_token=True, expect_body_type=None)
    def deauthenticate(self, auth_token):
        self.user_controller.logout(auth_token)
        return ApiResponse(status_code=204)
