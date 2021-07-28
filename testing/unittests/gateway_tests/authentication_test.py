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
Tests for the Authentication module.
"""

from __future__ import absolute_import

import fakesleep
import mock
import time
import unittest

from gateway.authentication_controller import AuthenticationController, TokenStore, LoginMethod
from gateway.dto.user import UserDTO
from gateway.rfid_controller import RfidController
from ioc import SetTestMode, SetUpTestInjections


class AuthenticationControllerTest(unittest.TestCase):
    """ Tests for AuthenticationController. """
    TOKEN_TIMEOUT = 3

    @classmethod
    def setUpClass(cls):
        super(AuthenticationControllerTest, cls).setUpClass()
        SetTestMode()
        fakesleep.monkey_patch()

    @classmethod
    def tearDownClass(cls):
        super(AuthenticationControllerTest, cls).tearDownClass()
        fakesleep.monkey_restore()

    def setUp(self):
        self.rfid_controller = mock.Mock(RfidController)
        SetUpTestInjections(rfid_controller=self.rfid_controller)
        SetUpTestInjections(token_timeout=AuthenticationControllerTest.TOKEN_TIMEOUT)
        self.token_store = TokenStore()
        SetUpTestInjections(token_store=self.token_store)
        self.controller = AuthenticationController()

    def tearDown(self):
        pass


    def test_create_token(self):
        user_dto = UserDTO(
            id=5,
            username='tester',
            role='ADMIN',
            pin_code='1234',
            apartment=None,
            accepted_terms=1
        )
        with mock.patch.object(self.token_store, '_get_full_user_dto', return_value=user_dto):
            token = self.token_store.create_token(user_dto, timeout=AuthenticationControllerTest.TOKEN_TIMEOUT, login_method=LoginMethod.PASSWORD)
            self.assertEqual(5, token.user.id)
            self.assertEqual('tester', token.user.username)
            self.assertLess(time.time() + AuthenticationControllerTest.TOKEN_TIMEOUT - 2, token.expire_timestamp)
            self.assertGreater(time.time() + AuthenticationControllerTest.TOKEN_TIMEOUT + 2, token.expire_timestamp)


    def test_verify_token(self):
        user_dto = UserDTO(
            id=5,
            username='tester',
            role='ADMIN',
            pin_code='1234',
            apartment=None,
            accepted_terms=1
        )
        with mock.patch.object(self.token_store, '_get_full_user_dto', return_value=user_dto):
            token = self.token_store.create_token(user_dto, timeout=AuthenticationControllerTest.TOKEN_TIMEOUT, login_method=LoginMethod.PASSWORD)
            result = self.token_store.check_token(token)
            self.assertIsNotNone(result)
            self.assertEqual(token, result)

            # Also test with the string version
            result = self.token_store.check_token(token.token)
            self.assertIsNotNone(result)
            self.assertEqual(token, result)


    def test_remove_token(self):
        user_dto = UserDTO(
            id=5,
            username='tester',
            role='ADMIN',
            pin_code='1234',
            apartment=None,
            accepted_terms=1
        )
        with mock.patch.object(self.token_store, '_get_full_user_dto', return_value=user_dto):
            token = self.token_store.create_token(user_dto, timeout=AuthenticationControllerTest.TOKEN_TIMEOUT, login_method=LoginMethod.PASSWORD)
            result = self.token_store.check_token(token)
            self.assertIsNotNone(result)
            self.assertEqual(token, result)

            # Now remove the token
            self.token_store.remove_token(token)
            result = self.token_store.check_token(token)
            self.assertIsNone(result)

            token = self.token_store.create_token(user_dto, timeout=AuthenticationControllerTest.TOKEN_TIMEOUT, login_method=LoginMethod.PASSWORD)
            result = self.token_store.check_token(token)
            self.assertIsNotNone(result)
            self.assertEqual(token, result)

            # Now remove the token
            self.token_store.remove_token(token.token)
            result = self.token_store.check_token(token.token)
            self.assertIsNone(result)


    def test_all_token_store(self):
        user_dto_1 = UserDTO(
            id=5,
            username='tester',
            role='ADMIN',
            pin_code='1234',
            apartment=None,
            accepted_terms=1
        )

        user_dto_2 = UserDTO(
            id=7,
            username='tester',
            role='ADMIN',
            pin_code='1234',
            apartment=None,
            accepted_terms=1
        )

        with mock.patch.object(self.token_store, '_get_full_user_dto') as full_user_mock:
            full_user_mock.return_value = user_dto_1
            token = self.token_store.create_token(user_dto_1, timeout=AuthenticationControllerTest.TOKEN_TIMEOUT, login_method=LoginMethod.PASSWORD)
            result = self.token_store.check_token(token)
            self.assertIsNotNone(result)
            self.assertEqual(token, result)

            # Now remove the token
            self.token_store.remove_token(token)
            result = self.token_store.check_token(token)
            self.assertIsNone(result)

            token = self.token_store.create_token(user_dto_1, timeout=AuthenticationControllerTest.TOKEN_TIMEOUT, login_method=LoginMethod.PASSWORD)
            result = self.token_store.check_token(token)
            self.assertIsNotNone(result)
            self.assertEqual(token, result)

            # Now remove the token
            self.token_store.remove_token(token.token)
            result = self.token_store.check_token(token.token)
            self.assertIsNone(result)

            token = self.token_store.create_token(user_dto_1, timeout=AuthenticationControllerTest.TOKEN_TIMEOUT, login_method=LoginMethod.PASSWORD)
            result = self.token_store.check_token(token)
            self.assertIsNotNone(result)
            self.assertEqual(token, result)
            self.assertEqual(5, token.user.id)

            time.sleep(AuthenticationControllerTest.TOKEN_TIMEOUT + 1)

            # Timeout
            result = self.token_store.check_token(token)
            self.assertIsNone(result)

            # multiple user
            full_user_mock.return_value = user_dto_1
            token_1 = self.token_store.create_token(user_dto_1, timeout=AuthenticationControllerTest.TOKEN_TIMEOUT, login_method=LoginMethod.PASSWORD)
            result_1 = self.token_store.check_token(token_1)
            self.assertIsNotNone(result_1)
            self.assertEqual(token_1, result_1)

            full_user_mock.return_value = user_dto_2
            token_2 = self.token_store.create_token(user_dto_2, timeout=AuthenticationControllerTest.TOKEN_TIMEOUT, login_method=LoginMethod.PASSWORD)
            result_2 = self.token_store.check_token(token_2)
            self.assertIsNotNone(result_2)
            self.assertEqual(token_2, result_2)

            self.assertNotEqual(token_1.token, token_2.token)

            result_1 = self.token_store.check_token(token_1)
            self.assertIsNotNone(result_1)
            self.assertEqual(token_1, result_1)

            self.token_store.remove_token(token_2)
            result_2 = self.token_store.check_token(token_2.token)
            self.assertIsNone(result_2)

            result_1 = self.token_store.check_token(token_1.token)
            self.assertIsNotNone(result_1)
            self.assertEqual(token_1, result_1)
