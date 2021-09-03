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
Authentication api tests
"""
from __future__ import absolute_import

import cherrypy
import time
import ujson as json
import unittest

import mock

from gateway.authentication_controller import AuthenticationController, AuthenticationToken, LoginMethod
from gateway.dto import UserDTO
from gateway.enums import UserEnums
from gateway.exceptions import *
from gateway.user_controller import UserController
from gateway.api.V1.authentication import Authentication

from ioc import SetTestMode, SetUpTestInjections

from .base import BaseCherryPyUnitTester


class ApiAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.auth_controller = mock.Mock(AuthenticationController)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        self.users_controller = mock.Mock(UserController)
        self.users_controller.authentication_controller = self.auth_controller
        SetUpTestInjections(user_controller=self.users_controller)
        self.web = Authentication()

        self.super_user = UserDTO(
            id=0,
            username='SUPER',
            first_name='',
            last_name='',
            role='SUPER',
            pin_code='6542',
            apartment=None,
            accepted_terms=1,
            is_active=True
        )

        # setup some users that will be used throughout the tests
        self.admin_user = UserDTO(
            id=0,
            username='ADMIN',
            first_name='',
            last_name='',
            role='ADMIN',
            pin_code='0000',
            apartment=None,
            accepted_terms=1,
            is_active=True
        )

        self.normal_user_1 = UserDTO(
            id=1,
            first_name='User',
            last_name='1',
            role='USER',
            pin_code='1111',
            apartment=None,
            language='en',
            accepted_terms=1,
            is_active=True
        )
        self.normal_user_2 = UserDTO(
            id=2,
            first_name='User',
            last_name='2',
            role='USER',
            pin_code='2222',
            apartment=None,
            language='Nederlands',
            accepted_terms=0,
            is_active=True
        )
        self.normal_user_3 = UserDTO(
            id=3,
            username='test_user_name',
            first_name='User',
            last_name='3',
            role='USER',
            pin_code='some_random_string',
            apartment=None,
            language='Francais',
            accepted_terms=1,
            is_active=True
        )
        self.courier_1 = UserDTO(
            id=4,
            username='Courier',
            first_name='Courier',
            last_name='1',
            role='COURIER',
            pin_code='some_random_string',
            apartment=None,
            language='Nederlands',
            accepted_terms=1,
            is_active=True
        )

        self.normal_users = [
            self.normal_user_1,
            self.normal_user_2,
            self.normal_user_3
        ]

        self.all_users = [self.admin_user] + self.normal_users + [self.courier_1]

    # ----------------------------------------------------------------
    # --- AUTHENTICATE
    # ----------------------------------------------------------------

    def test_authenticate_basic(self):
        auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PIN_CODE)
        body = {'pin_code': 'some-test-code'}
        with mock.patch.object(self.auth_controller, 'login_with_user_code', return_value=(True, auth_token)):
            response = self.web.authenticate_pin_code(request_body=body).decode('utf-8')
            expected = json.dumps(auth_token.to_dict())
            self.assertEqual(expected, response)

    def test_authenticate_wrong_credentials(self):
        data = UserEnums.AuthenticationErrors.INVALID_CREDENTIALS
        body = {'pin_code': 'some-test-code'}
        with mock.patch.object(self.auth_controller, 'login_with_user_code', return_value=(False, data)):
            response = self.web.authenticate_pin_code(request_body=body)
            self.assertIn(UnAuthorizedException.bytes_message(), response)

    def test_authenticate_basic_rfid(self):
        auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.RFID)
        body = {'rfid_tag': 'some-test-tag'}
        with mock.patch.object(self.auth_controller, 'login_with_rfid_tag', return_value=(True, auth_token)):
            response = self.web.authenticate_rfid_tag(request_body=body).decode('utf-8')
            self.assertEqual(response, json.dumps(auth_token.to_dict()))

    def test_authenticate_pin_code_wrong_body(self):
        body = {'some_wrong_key': 'some_wrong_data'}
        response = self.web.authenticate_pin_code(request_body=body)
        self.assertIn(WrongInputParametersException.bytes_message(), response)

    def test_authenticate_rfid_tag_wrong_body(self):
        body = {'some_wrong_key': 'some_wrong_data'}
        response = self.web.authenticate_rfid_tag(request_body=body)
        self.assertIn(WrongInputParametersException.bytes_message(), response)

    def test_authenticate_impersonate(self):
        auth_token = AuthenticationToken(user=self.normal_user_1, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PIN_CODE, impersonator=self.super_user)
        body = {'pin_code': 'some-test-code', 'impersonate': self.normal_user_1.username}
        with mock.patch.object(self.auth_controller, 'login_with_user_code', return_value=(True, auth_token)):
            response = self.web.authenticate_pin_code(request_body=body).decode('utf-8')
            self.assertEqual(response, json.dumps(auth_token.to_dict()))

    # ----------------------------------------------------------------
    # --- DEAUTHENTICATE
    # ----------------------------------------------------------------

    def test_deauthenticate_basic(self):
        auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
        with mock.patch.object(self.users_controller, 'logout') as logout_func:
            response = self.web.deauthenticate(auth_token=auth_token)
            logout_func.assert_called_once_with(auth_token)
            self.assertIsNone(response)


class AuthenticationApiCherryPyTest(BaseCherryPyUnitTester):
    def setUp(self):
        super(AuthenticationApiCherryPyTest, self).setUp()
        self.web = Authentication()
        cherrypy.tree.mount(root=self.web,
                            script_name=self.web.API_ENDPOINT,
                            config={'/':  {'request.dispatch': self.web.route_dispatcher}})

        self.test_admin = UserDTO(
            id=30,
            username='admin_1',
            role='ADMIN'
        )

        self.test_user_1 = UserDTO(
            id=30,
            username='user_1',
            role='USER'
        )
        self.test_user_1.set_password('test')

    def test_authenticate_no_body(self):
        auth_token = AuthenticationToken(user=self.test_user_1, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PIN_CODE)
        with mock.patch.object(self.auth_controller, 'login_with_user_code') as login_func:
            login_func.return_value = (True, auth_token)
            status, headers, response = self.POST('/api/v1/authenticate/pin_code', login_user=self.test_user_1, body=None)
            self.assertIn(WrongInputParametersException.bytes_message(), response)

    def test_deauthenticate_no_token(self):
        auth_token = None
        with mock.patch.object(self.auth_controller, 'login_with_user_code') as login_func:
            login_func.return_value = auth_token
            status, headers, response = self.POST('/api/v1/deauthenticate', login_user=None, body=None)
            self.assertIn(UnAuthorizedException.bytes_message(), response)

