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

import ujson as json

import cherrypy

from gateway.dto import UserDTO
from gateway.api.V1.webservice import RestAPIEndpoint, openmotics_api_v1, LoginMethod, ApiResponse

from .base import BaseCherryPyUnitTester


class OpenMoticsApiTest(BaseCherryPyUnitTester):

    def setUp(self):
        self.test_admin = UserDTO(
            username='ADMIN',
            role='ADMIN',
            pin_code='0000'
        )
        self.test_user = UserDTO(
            username='USER',
            role='USER',
            pin_code='1111'
        )
        self.test_technician = UserDTO(
            username='TECHNICIAN',
            role='TECHNICIAN',
            pin_code='2222'
        )
        self.test_courier = UserDTO(
            username='COURIER',
            role='COURIER',
            pin_code='3333'
        )
        super(OpenMoticsApiTest, self).setUp()

        # Custom rest class to test the behavior of the api decorator
        class RestTest(RestAPIEndpoint):
            API_ENDPOINT = '/rest'

            def __init__(self):
                # type: () -> None
                super(RestTest, self).__init__()
                self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
                # --- GET ---
                self.route_dispatcher.connect('get_rest', '',
                                              controller=self, action='get_rest',
                                              conditions={'method': ['GET']})

                self.route_dispatcher.connect('get_rest', '/auth/admin',
                                              controller=self, action='get_rest_auth_admin',
                                              conditions={'method': ['GET']})
                self.route_dispatcher.connect('get_rest', '/auth/technician',
                                              controller=self, action='get_rest_auth_technician',
                                              conditions={'method': ['GET']})
                self.route_dispatcher.connect('get_rest', '/auth/courier',
                                              controller=self, action='get_rest_auth_courier',
                                              conditions={'method': ['GET']})

                # --- POST ---
                self.route_dispatcher.connect('post_rest', '',
                                              controller=self, action='post_rest_no_auth_no_body',
                                              conditions={'method': ['POST']})
                self.route_dispatcher.connect('post_rest', '/noauth/json',
                                              controller=self, action='post_rest_auth_json',
                                              conditions={'method': ['POST']})

                # --- PUT ---
                self.route_dispatcher.connect('put_rest', '/noauth/raw',
                                              controller=self, action='put_rest_auth_raw',
                                              conditions={'method': ['PUT']})

                # --- DELETE ---
                self.route_dispatcher.connect('delete_rest', '/auth',
                                              controller=self, action='delete_rest_auth',
                                              conditions={'method': ['DELETE']})

            @openmotics_api_v1(auth=False)
            def get_rest(self):
                return ApiResponse(body='get_method', is_json=False)

            @openmotics_api_v1(auth=True, allowed_user_roles=['ADMIN'])
            def get_rest_auth_admin(self):
                return ApiResponse(body='get_method_auth_admin', is_json=False)

            @openmotics_api_v1(auth=True, allowed_user_roles=['TECHNICIAN'])
            def get_rest_auth_technician(self):
                return ApiResponse(body='get_method_auth_technician', is_json=False)

            @openmotics_api_v1(auth=True, allowed_user_roles=['COURIER'])
            def get_rest_auth_courier(self):
                return ApiResponse(body='get_method_auth_courier', is_json=False)

            @openmotics_api_v1(auth=False, pass_role=True)
            def post_rest_no_auth_no_body(self, auth_role):
                return ApiResponse(body={'role': auth_role})

            @openmotics_api_v1(auth=True, pass_role=True, expect_body_type='JSON')
            def post_rest_auth_json(self, auth_role, request_body):
                return ApiResponse(body={'role': auth_role, 'request_body': request_body})

            @openmotics_api_v1(auth=True, pass_token=True, expect_body_type='RAW')
            def put_rest_auth_raw(self, auth_token, request_body):
                return ApiResponse(body={'token_userrole': auth_token.user.role, 'request_body': request_body})

            @openmotics_api_v1(auth=True, auth_locahost=True)
            def delete_rest_auth(self):
                return ApiResponse(body='Delete', is_json=False)

        restTest = RestTest()
        cherrypy.tree.mount(root=restTest,
                            script_name=restTest.API_ENDPOINT,
                            config={'/': {'request.dispatch': restTest.route_dispatcher}})

    def test_get(self):
        resp = self.GET('/rest')
        self.assertBody('get_method')
        self.assertStatus('200 OK')
        self.assertNoHeaderItemValue('Content-Type', 'application/json')

    def test_get_auth_admin(self):
        resp = self.GET('/rest/auth/admin', login_user=self.test_admin)
        self.assertBody('get_method_auth_admin')
        self.assertStatus('200 OK')

    def test_get_auth_non_admin(self):
        resp = self.GET('/rest/auth/admin', login_user=self.test_user)
        self.assertBody("Unauthorized operation: User role is not allowed for this API call: Allowed: ['ADMIN'], Got: USER")
        self.assertStatus('401 Unauthorized')

    def test_get_auth_courier(self):
        resp = self.GET('/rest/auth/courier', login_user=self.test_courier)
        self.assertBody('get_method_auth_courier')
        self.assertStatus('200 OK')

    def test_get_auth_non_courier(self):
        resp = self.GET('/rest/auth/courier', login_user=self.test_user)
        self.assertBody("Unauthorized operation: User role is not allowed for this API call: Allowed: ['COURIER'], Got: USER")
        self.assertStatus('401 Unauthorized')

    def test_post(self):
        resp = self.POST('/rest', login_user=None)
        self.assertBody(json.dumps({'role': None}))
        self.assertStatus('200 OK')
        self.assertHeaderItemValue('Content-Type', 'application/json')

    def test_post_json(self):
        body_dict = {'body': 'test'}
        body = json.dumps(body_dict)
        resp = self.POST('/rest/noauth/json', login_user=self.test_user, body=body)
        self.assertBody(json.dumps({'role': 'USER', 'request_body': body_dict}))
        self.assertStatus('200 OK')

    def test_post_non_json(self):
        body = 'test'
        resp = self.POST('/rest/noauth/json', login_user=self.test_user, body=body)
        self.assertBody('Could not parse input: Could not parse the json body type')
        self.assertStatus('400 Bad Request')

    def test_put_non_raw(self):
        body = 'test'
        resp = self.PUT('/rest/noauth/raw', login_user=self.test_user, body=body)
        self.assertBody(json.dumps({'token_userrole': 'USER', 'request_body': body}))
        self.assertStatus('200 OK')

    def test_delete_no_auth(self):
        resp = self.DELETE('/rest/auth', login_user=None)
        self.assertStatus('401 Unauthorized')

    def test_delete_auth(self):
        resp = self.DELETE('/rest/auth', login_user=self.test_courier)
        self.assertBody('Delete')
        self.assertStatus('200 OK')
