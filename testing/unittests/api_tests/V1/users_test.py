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
            language='English',
            accepted_terms=1
        )
        self.normal_user_2 = UserDTO(
            id=2,
            username='User 2',
            role='USER',
            pin_code='2222',
            apartment=None,
            language='Nederlands',
            accepted_terms=0
        )
        self.normal_user_3 = UserDTO(
            id=3,
            username='User 3',
            role='USER',
            pin_code='some_random_string',
            apartment=None,
            language='Francais',
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
            response = self.web.get_users(role=auth_token.user.role)
            for user in self.all_users:
                self.verify_user_in_output(user, response)

    def test_get_users_list_unauthenticated(self):
        with mock.patch.object(self.users_controller, 'load_users', return_value=self.all_users):
            auth_token = None
            response = self.web.get_users(role=None)
            self.verify_user_not_in_output(self.admin_user, response)
            for user in self.normal_users:
                self.verify_user_in_output(user, response)

    def test_get_users_list_normal_user(self):
        with mock.patch.object(self.users_controller, 'load_users', return_value=self.all_users):
            auth_token = AuthenticationToken(user=self.normal_user_1, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.get_users(role=auth_token.user.role)
            self.verify_user_not_in_output(self.admin_user, response)
            for user in self.normal_users:
                self.verify_user_in_output(user, response)

    def test_get_user_normal_user(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2):
            auth_token = AuthenticationToken(user=self.normal_user_2, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.get_user('2', role=auth_token.user.role)
            self.verify_user_in_output(self.normal_user_2, response)
            self.verify_user_not_in_output(self.normal_user_3, response)

    def test_get_user_normal_user_other_login(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_3):
            auth_token = AuthenticationToken(user=self.normal_user_2, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.get_user('3', role=auth_token.user.role)
            self.verify_user_in_output(self.normal_user_3, response)
            self.verify_user_not_in_output(self.normal_user_2, response)

    def test_get_admin_user_as_normal_user(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.admin_user):
            auth_token = AuthenticationToken(user=self.normal_user_2, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.get_user('0', role=auth_token.user.role)
            self.assertTrue(UnAuthorizedException.bytes_message() in response)

    def test_get_admin_user_as_non_authenticated(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.admin_user):
            auth_token = None
            response = self.web.get_user('0', role=None)
            self.assertTrue(UnAuthorizedException.bytes_message() in response)

    # ----------------------------------------------------------------
    # --- POST
    # ----------------------------------------------------------------
    def verify_user_created(self, user_to_create, response):
        resp_dict = json.loads(response)
        for field in user_to_create:
            self.assertIn(field, resp_dict)
            user_to_create_field = user_to_create[field]
            resp_user_field = resp_dict[field]
            self.assertEqual(user_to_create_field, resp_user_field, "values are not equal for field: {}".format(field))

    def test_create_user_only_name(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func:
            user_to_create_return = user_to_create.copy()
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.post_user(role=auth_token.user.role,
                                          request_body=json.dumps(user_to_create))
            user_dto_to_save = UserDTO(**user_to_create)
            save_user_func.assert_called_once_with(user_dto_to_save)
            self.verify_user_created(user_to_create, response)

    def test_create_user_empty(self):
        user_to_create = {}
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func:
            exception_message = 'TEST_EXCEPTION'
            save_user_func.side_effect = RuntimeError(exception_message)
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.post_user(role=auth_token.user.role,
                                          request_body=json.dumps(user_to_create))
            self.assertTrue(WrongInputParametersException.bytes_message() in response)

    def test_create_user_credentials_not_allowed(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
            'pin_code': '1234',
            'password': 'Test',
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func:
            user_to_create_return = user_to_create.copy()
            del user_to_create_return['pin_code']
            del user_to_create_return['password']
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.post_user(role=auth_token.user.role,
                                          request_body=json.dumps(user_to_create))
            # remove the password and the pin code to check they are not saved
            del user_to_create['pin_code']
            del user_to_create['password']
            user_dto_to_save = UserDTO(**user_to_create)
            user_dto_to_save.set_password('Test')
            save_user_func.assert_called_once_with(user_dto_to_save)
            self.verify_user_created(user_to_create, response)

    def test_create_user_not_known_language(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
            'language': 'TEST',
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func:
            # mock the behaviour of the usercontroller sending back an exception that the language is not known
            exception_message = 'TEST_EXCEPTION'
            save_user_func.side_effect = RuntimeError(exception_message)
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.post_user(role=auth_token.user.role,
                                          request_body=json.dumps(user_to_create))
            self.assertTrue(WrongInputParametersException.bytes_message() in response)

    def test_create_user_null_apartment(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
            'apartment': None
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func:
            user_to_create_return = user_to_create.copy()
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.post_user(role=auth_token.user.role,
                                          request_body=json.dumps(user_to_create))
            user_dto_to_save = UserDTO(**user_to_create)
            user_dto_to_save.set_password('Test')
            save_user_func.assert_called_once_with(user_dto_to_save)
            self.verify_user_created(user_to_create, response)

    def test_create_user_all(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
            'apartment': None,
            'pin_code': '1234',
            'password': 'TEST',
            'accepted_terms': 1
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func:
            user_to_create_return = user_to_create.copy()
            del user_to_create_return['pin_code']
            del user_to_create_return['password']
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.post_user(role=auth_token.user.role,
                                          request_body=json.dumps(user_to_create))
            del user_to_create['pin_code']
            del user_to_create['password']
            user_dto_to_save = UserDTO(**user_to_create)
            save_user_func.assert_called_once_with(user_dto_to_save)
            self.verify_user_created(user_to_create, response)

    def test_activate_user(self):
        user_code = {'code': self.normal_user_2.pin_code}
        with mock.patch.object(self.users_controller, 'activate_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2):
            response = self.web.post_activate_user('2',
                                                   request_body=json.dumps(user_code))
            self.assertEqual(b'OK', response)

    def test_activate_user_wrong_code(self):
        user_code = {'code': 'WRONG_CODE'}
        with mock.patch.object(self.users_controller, 'activate_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2):
            response = self.web.post_activate_user('2',
                                                   request_body=json.dumps(user_code))
            self.assertTrue(UnAuthorizedException.bytes_message() in response)

    def test_activate_user_no_body(self):
        with mock.patch.object(self.users_controller, 'activate_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2):
            response = self.web.post_activate_user('2',
                                                   request_body=None)
            self.assertTrue(WrongInputParametersException.bytes_message() in response)

    # ----------------------------------------------------------------
    # --- PUT
    # ----------------------------------------------------------------

    def test_update_user(self):
        user_to_update = {
            'first_name': 'CHANGED'
        }
        # Change the user so that it will be correctly loaded
        self.normal_user_2.first_name = user_to_update['first_name']
        with mock.patch.object(self.users_controller, 'activate_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2) as load_user_func:
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.put_update_user('2',
                                                token=auth_token,
                                                role=auth_token.user.role,
                                                request_body=json.dumps(user_to_update))

            resp_dict = json.loads(response)

            self.assertNotIn('password', resp_dict)
            user_dto_response = UserDTO(**resp_dict)
            self.assertNotIn('pin_code', resp_dict)  # Do check that the pin code is not passed to the end user
            user_dto_response.pin_code = self.normal_user_2.pin_code  # Manually set the pin code since this is filtered out in the api
            self.assertEqual(self.normal_user_2, user_dto_response)

    def test_update_user_wrong_permission(self):
        user_to_update = {
            'first_name': 'CHANGED'
        }
        # Change the user so that it will be correctly loaded
        self.normal_user_2.first_name = user_to_update['first_name']
        with mock.patch.object(self.users_controller, 'activate_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2) as load_user_func:
            auth_token = AuthenticationToken(user=self.normal_user_3, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.put_update_user('2',
                                                token=auth_token,
                                                role=auth_token.user.role,
                                                request_body=json.dumps(user_to_update))

            self.assertTrue(UnAuthorizedException.bytes_message() in response)

    # ----------------------------------------------------------------
    # --- DELETE
    # ----------------------------------------------------------------

    def test_delete_user(self):
        with mock.patch.object(self.users_controller, 'remove_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2) as load_user_func:
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.delete_user('2',
                                            token=auth_token)
            self.assertEqual(b'OK', response)

    def test_delete_user_unauthorized(self):
        with mock.patch.object(self.users_controller, 'remove_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2) as load_user_func:
            response = self.web.delete_user('2',
                                            token=None)
            self.assertTrue(UnAuthorizedException.bytes_message() in response)
