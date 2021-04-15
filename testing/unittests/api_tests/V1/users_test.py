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
from __future__ import absolute_import

import json
import time
import unittest

import mock

from gateway.authentication_controller import AuthenticationController, AuthenticationToken
from gateway.api.serializers.user import UserSerializer
from gateway.dto.user import UserDTO
from gateway.exceptions import *
from gateway.user_controller import UserController
from gateway.webservice_v1 import Users

from ioc import SetTestMode, SetUpTestInjections


class ApiUsersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.users_controller = mock.Mock(UserController)
        SetUpTestInjections(user_controller=self.users_controller)
        self.web = Users()

        # setup some users that will be used throughout the tests
        self.admin_user = UserDTO(
            id=0,
            username='ADMIN',
            role='ADMIN',
            pin_code='0000',
            apartment=None,
            accepted_terms=1
        )

        self.normal_user_1 = UserDTO(
            id=1,
            username='User 1',
            role='USER',
            pin_code='1111',
            apartment=None,
            accepted_terms=1
        )
        self.normal_user_2 = UserDTO(
            id=2,
            username='User 2',
            role='USER',
            pin_code='2222',
            apartment=None,
            accepted_terms=0
        )
        self.normal_user_3 = UserDTO(
            id=3,
            username='User 3',
            role='USER',
            pin_code='some_random_string',
            apartment=None,
            accepted_terms=1
        )

        self.normal_users = [
            self.normal_user_1,
            self.normal_user_2,
            self.normal_user_3
        ]

        self.all_users = [self.admin_user] + self.normal_users

    # ----------------------------------------------------------------
    # --- HELPERS
    # ----------------------------------------------------------------

    def verify_user_in_output(self, user_dto, response):
        resp_dict = json.loads(response)

        self.assertNotIn('password', resp_dict)

        if isinstance(resp_dict, dict):
            resp_dict = [resp_dict]

        for user_dict in resp_dict:
            user_dto_response = UserDTO(**user_dict)
            self.assertNotIn('pin_code', user_dict)  # Do check that the pin code is not passed to the end user
            user_dto_response.pin_code = user_dto.pin_code  # Manually set the pin code since this is filtered out in the api
            if user_dto == user_dto_response:
                return

        self.fail('Could not find the user: \n{} \nin the output: \n{}'.format(user_dto, resp_dict))

    def verify_user_not_in_output(self, user_dto, response):
        resp_dict = json.loads(response)

        self.assertNotIn('password', resp_dict)

        if isinstance(resp_dict, dict):
            resp_dict = [resp_dict]

        for user_dict in resp_dict:
            user_dto_response = UserDTO(**user_dict)
            self.assertNotIn('pin_code', user_dict)  # Do check that the pin code is not passed to the end user
            user_dto_response.pin_code = user_dto.pin_code  # Manually set the pin code since this is filtered out in the api
            if user_dto == user_dto_response:
                self.fail('Could find the user: \n{} \nin the output: \n{}'.format(user_dto, resp_dict))
        return

    # ----------------------------------------------------------------
    # --- GET
    # ----------------------------------------------------------------

    def test_get_users_list(self):
        with mock.patch.object(self.users_controller, 'load_users', return_value=self.all_users):
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.GET(token=auth_token, role=auth_token.user.role)
            for user in self.all_users:
                self.verify_user_in_output(user, response)

    def test_get_users_list_unauthenticated(self):
        with mock.patch.object(self.users_controller, 'load_users', return_value=self.all_users):
            auth_token = None
            response = self.web.GET(token=auth_token, role=None)
            self.verify_user_not_in_output(self.admin_user, response)
            for user in self.normal_users:
                self.verify_user_in_output(user, response)

    def test_get_users_list_normal_user(self):
        with mock.patch.object(self.users_controller, 'load_users', return_value=self.all_users):
            auth_token = AuthenticationToken(user=self.normal_user_1, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.GET(token=auth_token, role=auth_token.user.role)
            self.verify_user_not_in_output(self.admin_user, response)
            for user in self.normal_users:
                self.verify_user_in_output(user, response)

    def test_get_user_normal_user(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2):
            auth_token = AuthenticationToken(user=self.normal_user_2, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.GET('2', token=auth_token, role=auth_token.user.role)
            print(response)
            self.verify_user_in_output(self.normal_user_2, response)
            self.verify_user_not_in_output(self.normal_user_3, response)

    def test_get_user_normal_user_other_login(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_3):
            auth_token = AuthenticationToken(user=self.normal_user_2, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.GET('3', token=auth_token, role=auth_token.user.role)
            print(response)
            self.verify_user_in_output(self.normal_user_3, response)
            self.verify_user_not_in_output(self.normal_user_2, response)

    def test_get_admin_user_as_normal_user(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.admin_user):
            auth_token = AuthenticationToken(user=self.normal_user_2, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.GET('0', token=auth_token, role=auth_token.user.role)
            self.assertIn(UnAuthorizedException.DESC, response)

    def test_get_admin_user_as_non_authenticated(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.admin_user):
            auth_token = None
            response = self.web.GET('0', token=auth_token, role=None)
            self.assertTrue(response.startswith(UnAuthorizedException.DESC))

