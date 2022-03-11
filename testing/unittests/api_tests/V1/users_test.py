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

import cherrypy
import ujson as json
import time
import unittest

import mock

from gateway.authentication_controller import AuthenticationController, AuthenticationToken, LoginMethod
from gateway.dto import UserDTO
from gateway.exceptions import UnAuthorizedException, WrongInputParametersException
from gateway.user_controller import UserController
from gateway.api.V1.webservice import AuthenticationLevel
from gateway.api.V1.users import Users

from .base import BaseCherryPyUnitTester

from ioc import SetTestMode, SetUpTestInjections


class ApiUsersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.authentication_controller = mock.Mock(AuthenticationController)
        self.users_controller = mock.Mock(UserController)
        SetUpTestInjections(authentication_controller=self.authentication_controller)
        SetUpTestInjections(user_controller=self.users_controller)
        self.web = Users()

        self.super_user = UserDTO(
            id=0,
            username='SUPER',
            first_name='',
            last_name='',
            role='SUPER',
            pin_code='1234568',
            apartment=None,
            accepted_terms=1
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
            accepted_terms=1
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
            email='user_1@test.com'
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
            email='user_2@test.com'
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
            accepted_terms=1
        )

        self.normal_user_4 = UserDTO(
            id=4,
            username='test_user_name',
            first_name='User',
            last_name='4',
            role='USER',
            pin_code='some_random_string',
            apartment=None,
            language='en',
            accepted_terms=1,
            is_active=False
        )

        self.normal_users = [
            self.normal_user_1,
            self.normal_user_2,
            self.normal_user_3,
            self.normal_user_4
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
            all_equal = True
            for field in ['first_name', 'last_name', 'role', 'language', 'accepted_terms']:
                if not getattr(user_dto, field) == user_dict.get(field, None):
                    all_equal = False
                    break
            if all_equal:
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
        with mock.patch.object(self.users_controller, 'load_users', return_value=self.all_users) as load_users_func:
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_users(auth_token=auth_token)
            for user in self.all_users:
                self.verify_user_in_output(user, response)

            # pass some arguments
            load_users_func.reset_mock()
            load_users_func.return_value = [user for user in self.all_users if user.role == 'ADMIN']
            response = self.web.get_users(auth_token=auth_token, role='ADMIN')
            load_users_func.assert_called_once_with(roles=['ADMIN'], include_inactive=False)
            for user in self.all_users:
                if user.role == 'ADMIN':
                    self.verify_user_in_output(user, response)
                else:
                    self.verify_user_not_in_output(user, response)

            load_users_func.reset_mock()
            load_users_func.return_value = [user for user in self.all_users if user.role == 'USER']
            response = self.web.get_users(auth_token=auth_token, role='USER', include_inactive=True)
            load_users_func.assert_called_once_with(roles=['USER'], include_inactive=True)
            for user in self.all_users:
                if user.role == 'USER':
                    self.verify_user_in_output(user, response)
                else:
                    self.verify_user_not_in_output(user, response)

            load_users_func.reset_mock()
            load_users_func.return_value = [user for user in self.all_users if user.role == 'USER' and user.is_active]
            response = self.web.get_users(auth_token=auth_token, role='USER', include_inactive=False)
            load_users_func.assert_called_once_with(roles=['USER'], include_inactive=False)
            for user in self.all_users:
                if user.role == 'USER' and user.is_active:
                    self.verify_user_in_output(user, response)
                else:
                    self.verify_user_not_in_output(user, response)

    def test_get_users_list_unauthenticated(self):
        with mock.patch.object(self.users_controller, 'load_users', return_value=self.normal_users):
            response = self.web.get_users(auth_token=None)
            self.verify_user_not_in_output(self.admin_user, response)
            for user in self.normal_users:
                self.verify_user_in_output(user, response)

    def test_get_users_list_normal_user(self):
        with mock.patch.object(self.users_controller, 'load_users', return_value=self.normal_users):
            auth_token = AuthenticationToken(user=self.normal_user_1, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PIN_CODE)
            response = self.web.get_users(auth_token=auth_token)
            self.verify_user_not_in_output(self.admin_user, response)
            for user in self.normal_users:
                self.verify_user_in_output(user, response)

    def test_get_user_normal_user(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2):
            auth_token = AuthenticationToken(user=self.normal_user_2, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_user('2', auth_token=auth_token)
            self.verify_user_in_output(self.normal_user_2, response)
            self.verify_user_not_in_output(self.normal_user_3, response)

    def test_get_user_normal_user_other_login(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_3):
            auth_token = AuthenticationToken(user=self.normal_user_2, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_user('3', auth_token=auth_token)
            self.verify_user_in_output(self.normal_user_3, response)
            self.verify_user_not_in_output(self.normal_user_2, response)

    def test_get_admin_user_as_normal_user(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.admin_user):
            auth_token = AuthenticationToken(user=self.normal_user_2, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_user('0', auth_token=auth_token)
            self.assertTrue(UnAuthorizedException.bytes_message() in response)

    def test_get_admin_user_as_non_authenticated(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.admin_user):
            response = self.web.get_user('0', auth_token=None)
            self.assertTrue(UnAuthorizedException.bytes_message() in response)

    # ----------------------------------------------------------------
    # --- POST
    # ----------------------------------------------------------------
    def verify_user_created(self, user_to_create, response, check_for_pin=False):
        resp_dict = json.loads(response)
        if check_for_pin:
            self.assertIn('pin_code', resp_dict)
            self.assertEqual(resp_dict['pin_code'], '1234')
        for field in user_to_create:
            self.assertIn(field, resp_dict)
            user_to_create_field = user_to_create[field]
            resp_user_field = resp_dict[field]
            self.assertEqual(user_to_create_field, resp_user_field, "values are not equal for field: {}".format(field))

    def test_create_user_only_name(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'USER'
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'generate_new_pin_code', return_value='1234'):
            user_to_create_return = user_to_create.copy()
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_user(auth_token=auth_token,
                                          request_body=user_to_create)
            self.verify_user_created(user_to_create, response, check_for_pin=True)

    def test_create_admin(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'ADMIN',
            'role': 'ADMIN'
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'generate_new_pin_code', return_value='000123'):
            user_to_create_return = user_to_create.copy()
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_user(auth_token=auth_token,
                                          request_body=user_to_create)
            resp_json = json.loads(response)
            self.assertEqual('000123', resp_json['pin_code'])
            self.verify_user_created(user_to_create, response)

    def test_create_admin_no_auth(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'ADMIN',
            'role': 'ADMIN'
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'generate_new_pin_code', return_value=123):
            user_to_create_return = user_to_create.copy()
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.normal_user_1, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_user(auth_token=auth_token,
                                          request_body=user_to_create)
            self.assertIn(UnAuthorizedException.bytes_message(), response)

    def test_create_user_empty(self):
        user_to_create = {}
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func:
            exception_message = 'TEST_EXCEPTION'
            save_user_func.side_effect = RuntimeError(exception_message)
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_user(auth_token=auth_token,
                                          request_body=json.dumps(user_to_create))
            self.assertTrue(WrongInputParametersException.bytes_message() in response)

    def test_create_user_no_role(self):
        user_to_create = {
            'first_name': 'test'
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func:
            exception_message = 'TEST_EXCEPTION'
            save_user_func.side_effect = RuntimeError(exception_message)
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_user(auth_token=auth_token,
                                          request_body=json.dumps(user_to_create))
            self.assertTrue(WrongInputParametersException.bytes_message() in response)

    def test_create_user_credentials_not_allowed(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
            'pin_code': '6789',
            'password': 'Test',
            'role': 'USER'
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'generate_new_pin_code', return_value='1234'):
            user_to_create_return = user_to_create.copy()
            del user_to_create_return['pin_code']
            del user_to_create_return['password']
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_user(auth_token=auth_token,
                                          request_body=user_to_create.copy())
            # remove the password and the pin code to check they are not saved
            del user_to_create['pin_code']
            del user_to_create['password']
            self.verify_user_created(user_to_create, response)

    def test_create_user_not_known_language(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
            'language': 'TEST',
            'role': 'USER'
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func:
            # mock the behaviour of the usercontroller sending back an exception that the language is not known
            exception_message = 'TEST_EXCEPTION'
            save_user_func.side_effect = RuntimeError(exception_message)
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_user(auth_token=auth_token,
                                          request_body=user_to_create)
            self.assertTrue(WrongInputParametersException.bytes_message() in response)

    def test_create_user_null_apartment(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
            'apartment': None,
            'role': 'USER'
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'generate_new_pin_code', return_value='1234'):
            user_to_create_return = user_to_create.copy()
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_user(auth_token=auth_token,
                                          request_body=user_to_create)
            self.verify_user_created(user_to_create, response, check_for_pin=True)

    def test_create_user_all(self):
        user_to_create = {
            'first_name': 'Test',
            'last_name': 'User',
            'apartment': None,
            'pin_code': '6789',
            'password': 'TEST',
            'accepted_terms': 1,
            'role': 'USER',
            'email': 'tester@test.com'
        }
        with mock.patch.object(self.users_controller, 'save_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'generate_new_pin_code', return_value='0123'):
            user_to_create_return = user_to_create.copy()
            del user_to_create_return['password']
            user_to_create_return['id'] = 5
            user_dto_to_return = UserDTO(**user_to_create_return)
            user_dto_to_return.set_password('Test')
            save_user_func.return_value = user_dto_to_return

            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_user(auth_token=auth_token,
                                          request_body=user_to_create.copy())
            del user_to_create['password']
            self.verify_user_created(user_to_create, response)

    def test_activate_user(self):
        user_code = {'pin_code': self.normal_user_2.pin_code}
        with mock.patch.object(self.users_controller, 'activate_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2):
            response = self.web.post_activate_user('2',
                                                   request_body=user_code)
            self.assertEqual(None, response)

    def test_activate_user_wrong_code(self):
        user_code = {'pin_code': 'WRONG_CODE'}
        with mock.patch.object(self.users_controller, 'activate_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2):
            response = self.web.post_activate_user('2',
                                                   request_body=user_code)
            self.assertTrue(UnAuthorizedException.bytes_message() in response)

    # ----------------------------------------------------------------
    # --- PUT
    # ----------------------------------------------------------------

    def test_update_user(self):
        user_to_update = {
            'first_name': 'CHANGED',
            'email': 'test@test.com'
        }
        # Change the user so that it will be correctly loaded
        self.normal_user_2.first_name = user_to_update['first_name']
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2) as load_user_func, \
                mock.patch.object(self.users_controller, 'save_user', return_value=self.normal_user_2) as save_user_func:
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.put_update_user('2',
                                                auth_token=auth_token,
                                                auth_security_level=AuthenticationLevel.HIGH,
                                                request_body=user_to_update)

            resp_dict = json.loads(response)

            self.assertNotIn('password', resp_dict)
            user_dto_response = UserDTO(**resp_dict)
            user_dto_response.username = self.normal_user_2.username
            self.assertNotIn('pin_code', resp_dict)  # Do check that the pin code is not passed to the end user
            user_dto_response.pin_code = self.normal_user_2.pin_code  # Manually set the pin code since this is filtered out in the api
            self.assertEqual(self.normal_user_2, user_dto_response)
            self.assertEqual('CHANGED', resp_dict['first_name'])
            self.assertEqual('test@test.com', resp_dict['email'])


    def test_update_user_wrong_permission(self):
        user_to_update = {
            'first_name': 'CHANGED'
        }
        # Change the user so that it will be correctly loaded
        self.normal_user_2.first_name = user_to_update['first_name']
        with mock.patch.object(self.users_controller, 'activate_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2) as load_user_func:
            auth_token = AuthenticationToken(user=self.normal_user_3, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.put_update_user('2',
                                                auth_token=auth_token,
                                                auth_security_level=AuthenticationLevel.HIGH,
                                                request_body=user_to_update)

            self.assertTrue(UnAuthorizedException.bytes_message() in response)

    # ----------------------------------------------------------------
    # --- DELETE
    # ----------------------------------------------------------------

    def test_delete_user(self):
        with mock.patch.object(self.users_controller, 'remove_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2) as load_user_func:
            auth_token = AuthenticationToken(user=self.admin_user, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.delete_user('2',
                                            auth_token=auth_token)
            self.assertEqual(None, response)

    def test_delete_user_unauthorized(self):
        with mock.patch.object(self.users_controller, 'remove_user') as save_user_func, \
                mock.patch.object(self.users_controller, 'load_user', return_value=self.normal_user_2) as load_user_func:
            response = self.web.delete_user('2',
                                            auth_token=None)
            self.assertTrue(UnAuthorizedException.bytes_message() in response)


class OpenMoticsApiTest(BaseCherryPyUnitTester):

    def setUp(self):
        self.test_admin = UserDTO(
            id=1,
            username='ADMIN',
            role='ADMIN',
            pin_code='0000'
        )
        self.test_user = UserDTO(
            id=2,
            username='USER',
            role='USER',
            pin_code='1111'
        )
        self.test_technician = UserDTO(
            id=3,
            username='TECHNICIAN',
            role='TECHNICIAN',
            pin_code='2222'
        )
        self.test_courier = UserDTO(
            id=4,
            username='COURIER',
            role='COURIER',
            pin_code='3333'
        )
        super(OpenMoticsApiTest, self).setUp()

        web = Users()
        cherrypy.tree.mount(root=web,
                            script_name=web.API_ENDPOINT,
                            config={'/': {'request.dispatch': web.route_dispatcher}})

    def test_get(self):
        # use the original implementation
        current_pins = ['1234', '5678', '123456', '567890']

        def mock_generate_new_pin(length):
            return UserController._generate_new_pin_code(length, current_pins)

        with mock.patch.object(self.users_controller, 'generate_new_pin_code', wraps=mock_generate_new_pin):
            # Test all the 4 roles in a normal way
            for user_role in ['USER', 'ADMIN', 'COURIER', 'TECHNICIAN', 'SUPER']:
                status, headers, body = self.GET('/api/v1/users/available_code?role={}'.format(user_role), login_user=self.test_admin, login_method=LoginMethod.PASSWORD)
                self.assertStatus('200 OK')
                number_of_digits = UserController.PinCodeLength[user_role]
                body_dict = json.loads(body)
                self.assertEqual(number_of_digits, len(body_dict['code']))
                body_int = int(body_dict['code'])
                self.assertLess(body_int, int('1' + '0' * number_of_digits))
                self.assertNotIn(body_dict['code'], current_pins)

            # Don't pass the role in
            status, headers, body = self.GET('/api/v1/users/available_code', login_user=self.test_admin, login_method=LoginMethod.PASSWORD)
            self.assertStatus('404 Not Found')
            body_json = json.loads(body)
            self.assertEqual({"msg": "Missing parameters: role", "success": False}, body_json)

            # pass in the wrong role
            status, headers, body = self.GET('/api/v1/users/available_code?role=WRONG', login_user=self.test_admin, login_method=LoginMethod.PASSWORD)
            self.assertStatus('400 Bad Request')
            self.assertTrue(body.startswith(b"Wrong input parameter: Role needs to be one of"))

    def test_get_user_pin_code(self):
        with mock.patch.object(self.users_controller, 'load_user', return_value=self.test_user):
            # Do not pass authentication as a normal user
            status, headers, body = self.GET('/api/v1/users/1/pin', login_user=self.test_user)
            self.assertStatus('401 Unauthorized')

            status, headers, body = self.GET('/api/v1/users/1/pin', login_user=self.test_admin, login_method=LoginMethod.PIN_CODE)
            self.assertStatus('401 Unauthorized')

            # As a normal user
            status, headers, body = self.GET('/api/v1/users/1/pin', login_user=self.test_user)
            self.assertStatus('401 Unauthorized')

            # login with password
            status, headers, body = self.GET('/api/v1/users/1/pin', login_user=self.test_admin, login_method=LoginMethod.PASSWORD)
            self.assertStatus('200 OK')
            self.assertEqual(json.loads(body), {'pin_code': self.test_user.pin_code})

    def test_delete_user(self):
        with mock.patch.object(self.users_controller, 'remove_user') as delete_user_func:
            status, headers, body = self.DELETE('/api/v1/users/1', login_user=self.test_admin)
            self.assertStatus('204 No Content')
            self.assertBody('')

