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

from gateway.authentication_controller import AuthenticationController, TokenStore, LoginMethod, AuthenticationToken, UnAuthorizedException
from gateway.dto.user import UserDTO
from gateway.models import User
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
            accepted_terms=1
        )

        user_dto_2 = UserDTO(
            id=7,
            username='tester',
            role='ADMIN',
            pin_code='1234',
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


from peewee import SqliteDatabase
from gateway.mappers import UserMapper
from gateway.exceptions import ItemDoesNotExistException

MODELS = [User]


class TokenStoreTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def save_user(self, user):
        _ = self
        user_orm = UserMapper.dto_to_orm(user)
        user_orm.save()
        user.id = user_orm.id

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

        SetUpTestInjections(token_timeout=3)
        self.store = TokenStore()

        self.test_super_1 = UserDTO(
            username='test_super_1',
            role='SUPER',
            language='en'
        )
        self.test_super_1.set_password('test')
        self.save_user(self.test_super_1)

        self.test_super_2 = UserDTO(
            username='test_super_2',
            role='SUPER',
            language='en'
        )
        self.test_super_2.set_password('test')
        self.save_user(self.test_super_2)

        self.test_admin_1 = UserDTO(
            username='test_admin_1',
            role='ADMIN',
            language='en'
        )
        self.test_admin_1.set_password('test')
        self.save_user(self.test_admin_1)

        self.test_admin_2 = UserDTO(
            username='test_admin_2',
            role='ADMIN',
            language='en'
        )
        self.test_admin_2.set_password('test')
        self.save_user(self.test_admin_2)

        self.test_technician_1 = UserDTO(
            username='test_technician_1',
            role='TECHNICIAN',
            language='en'
        )
        self.test_technician_1.set_password('test')
        self.save_user(self.test_technician_1)

        self.test_user_1 = UserDTO(
            username='test_user_1',
            role='USER',
            language='en'
        )
        self.test_user_1.set_password('test')
        self.save_user(self.test_user_1)
        self.test_user_2 = UserDTO(
            username='test_user_2',
            role='USER',
            language='en'
        )
        self.test_user_2.set_password('test')
        self.save_user(self.test_user_2)

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def assert_token_valid(self, token):
        # check both string and authentication token verification
        self.assertEqual(token, self.store.check_token(token))
        self.assertEqual(token, self.store.check_token(token.token))

    def assert_token_not_valid(self, token):
        # check both string and authentication token verification
        self.assertIsNone(self.store.check_token(token))
        self.assertIsNone(self.store.check_token(token.token))

    def test_create_token(self):
        token_1 = self.store.create_token(self.test_user_1, login_method=LoginMethod.PASSWORD)
        self.assert_token_valid(token_1)

        token_2 = self.store.create_token(self.test_user_2, login_method=LoginMethod.PASSWORD)
        self.assert_token_valid(token_1)
        self.assert_token_valid(token_2)

        token_3 = self.store.create_token(self.test_admin_1, login_method=LoginMethod.PASSWORD)
        self.assert_token_valid(token_1)
        self.assert_token_valid(token_2)
        self.assert_token_valid(token_3)

        # Impersonate as test user 1 with super 1
        token_4 = self.store.create_token(self.test_user_1, login_method=LoginMethod.PASSWORD, impersonator=self.test_super_1)
        self.assert_token_valid(token_4)
        self.assertNotEqual(token_1.token, token_4.token)
        self.assertEqual('USER', token_4.user.role)

        # Impersonate as test user 1 with super 2
        token_5 = self.store.create_token(self.test_user_1, login_method=LoginMethod.PASSWORD, impersonator=self.test_super_2)
        self.assert_token_valid(token_5)
        self.assertNotEqual(token_1.token, token_5.token)
        self.assertEqual('USER', token_5.user.role)

        # Impersonate as test user 1 with Non super
        with self.assertRaises(UnAuthorizedException):
            token_5 = self.store.create_token(self.test_user_1, login_method=LoginMethod.PASSWORD, impersonator=self.test_admin_1)

    def test_remove_token(self):
        token_1 = self.store.create_token(self.test_user_1, login_method=LoginMethod.PASSWORD)
        token_2 = self.store.create_token(self.test_user_2, login_method=LoginMethod.PASSWORD)
        token_3 = self.store.create_token(self.test_admin_1, login_method=LoginMethod.PASSWORD)
        token_4 = self.store.create_token(self.test_user_1, login_method=LoginMethod.PASSWORD, impersonator=self.test_super_1)
        token_5 = self.store.create_token(self.test_user_1, login_method=LoginMethod.PASSWORD, impersonator=self.test_super_2)
        token_6 = self.store.create_token(self.test_admin_2, login_method=LoginMethod.PASSWORD)

        self.assert_token_valid(token_1)
        self.assert_token_valid(token_2)
        self.assert_token_valid(token_3)
        self.assert_token_valid(token_4)
        self.assert_token_valid(token_5)
        self.assert_token_valid(token_6)

        # Remove single tokens from the token store
        self.store.remove_token(token_6.token)
        self.assert_token_not_valid(token_6)
        self.assert_token_valid(token_3)
        self.assertEqual(5, len(self.store.tokens))

        self.store.remove_token(token_3.token)
        self.assert_token_not_valid(token_6)
        self.assert_token_not_valid(token_3)
        self.assertEqual(4, len(self.store.tokens))

        # Remove all the tokens for one user, this is usefull when a user is deleted
        self.store.remove_tokens_for_user(self.test_user_1)
        self.assert_token_not_valid(token_1)
        self.assert_token_not_valid(token_4)
        self.assert_token_not_valid(token_5)
        self.assertEqual(1, len(self.store.tokens))

        # The only token left
        self.assert_token_valid(token_2)

        with self.assertRaises(ItemDoesNotExistException):
            self.store.remove_token('un-existing_token')
            self.store.remove_token(AuthenticationToken(self.test_user_1, token='un-existing', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD, impersonator=None))

    def test_login_method(self):
        token_1 = self.store.create_token(self.test_user_1, login_method=LoginMethod.PASSWORD)
        token_2 = self.store.create_token(self.test_user_2, login_method=LoginMethod.PIN_CODE)

        self.assertEqual(LoginMethod.PASSWORD, token_1.login_method)
        self.assertEqual(LoginMethod.PIN_CODE, token_2.login_method)
