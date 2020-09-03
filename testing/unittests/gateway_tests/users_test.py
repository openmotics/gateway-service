# Copyright (C) 2016 OpenMotics BV
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
Tests for the users module.

@author: fryckbos
"""

from __future__ import absolute_import

import time
import unittest
from threading import Lock

import xmlrunner
from pytest import mark

import os
# import fakesleep
import tempfile
from peewee import SqliteDatabase

from gateway.user_controller import UserController
from gateway.dto import UserDTO
from ioc import SetTestMode, SetUpTestInjections

from gateway.models import User

MODELS = [User]



class UserControllerTest(unittest.TestCase):
    """ Tests for UserController. """

    _db_filename = None

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls._db_filename = tempfile.mktemp()
        cls.test_db = SqliteDatabase(cls._db_filename)
        # fakesleep.monkey_patch()

    @classmethod
    def tearDownClass(cls):
        # fakesleep.monkey_restore()
        if os.path.exists(cls._db_filename):
            os.remove(cls._db_filename)

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        UserControllerTest.RETURN_DATA = {}

    def tearDown(self):
        UserControllerTest.RETURN_DATA = {}
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def _get_controller(self):
        """ Get a UserController using FILE. """
        SetUpTestInjections(
            config={'username': 'om', 'password': 'pass'},
            token_timeout=10
        )
        return UserController()


    def test_empty(self):
        """ Test an empty database. """
        user_controller = self._get_controller()
        user_dto = UserDTO("fred", "test", "admin", True)
        users_to_login = [(user_dto, False, 3600)]
        success, data = user_controller.login(users_to_login)
        self.assertFalse(success)
        self.assertEqual(data, 'invalid_credentials')
        self.assertEqual(False, user_controller.check_token('some token 123'))
        self.assertEqual(None, user_controller.get_role('fred'))

        user_dto = UserDTO("om", "pass", "admin", True)
        users_to_login = [(user_dto, False, 3600)]
        success, data = user_controller.login(users_to_login)
        self.assertTrue(success)
        self.assertNotEquals(None, data)

        self.assertTrue(user_controller.check_token(data))

    def test_terms(self):
        """ Tests acceptance of the terms """
        user_controller = self._get_controller()
        # adding test user
        fields = ['username', 'password', 'role', 'enabled', 'accepted_terms']
        user_dto = UserDTO(
            username='om2',
            password='pass',
            role="admin",
            enabled=True
        )
        user_controller.save_users([(user_dto, fields)])

        # check if login is possible
        users_to_login = [(user_dto, False, 0)]
        success, data = user_controller.login(users_to_login)
        self.assertFalse(success)
        self.assertEqual(data, 'terms_not_accepted')

        # login with accepted terms fields set
        users_to_login = [(user_dto, True, 0)]
        success, data = user_controller.login(users_to_login)
        self.assertTrue(success)
        self.assertIsNotNone(data)


        # login again to see if fields has been saved
        users_to_login = [(user_dto, False, 0)]
        success, data = user_controller.login(users_to_login)
        self.assertTrue(success)
        self.assertIsNotNone(data)

    def test_all(self):
        """ Test all methods of UserController. """
        user_controller = self._get_controller()
        fields = ['username', 'password', 'role', 'enabled', 'accepted_terms']
        user_dto = UserDTO(
            username='fred',
            password='test',
            role="admin",
            enabled=True
        )
        user_controller.save_users([(user_dto, fields)])

        user_dto_login = UserDTO(
            username='fred',
            password='123',
            role="admin",
            enabled=True
        )
        users_to_login = [(user_dto_login, True, 0)]
        success, _ = user_controller.login(users_to_login)
        self.assertEqual(False, success)
        self.assertFalse(user_controller.check_token('blah'))

        user_dto_login = UserDTO(
            username='fred',
            password='test',
            role="admin",
            enabled=True
        )
        users_to_login = [(user_dto_login, True, 0)]
        _, token = user_controller.login(users_to_login)
        self.assertNotEquals(None, token)

        self.assertTrue(user_controller.check_token(token))
        self.assertFalse(user_controller.check_token('blah'))

        self.assertEqual('admin', user_controller.get_role('fred'))

    @mark.slow
    def test_token_timeout(self):
        """ Test the timeout on the tokens. """
        SetUpTestInjections(config={'username': 'om', 'password': 'pass'},
                            token_timeout=3)
        user_controller = UserController()

        user_dto_login = UserDTO(
            username='om',
            password='pass',
            role="admin",
            enabled=True,
            accepted_terms=True
        )
        users_to_login = [(user_dto_login, False, None)]
        success, token = user_controller.login(users_to_login)
        self.assertTrue(success)
        self.assertNotEquals(None, token)
        self.assertTrue(user_controller.check_token(token))

        time.sleep(4)

        self.assertFalse(user_controller.check_token(token))

        success, token = user_controller.login(users_to_login)
        self.assertTrue(success)
        self.assertNotEquals(None, token)
        self.assertTrue(user_controller.check_token(token))

    def test_timeout(self):
        """ Test logout. """
        SetUpTestInjections(config={'username': 'om', 'password': 'pass'},
                            token_timeout=3)
        user_controller = UserController()

        user_dto_login = UserDTO(
            username='om',
            password='pass',
            role="admin",
            enabled=True,
            accepted_terms=True
        )
        users_to_login = [(user_dto_login, False, None)]
        success, token = user_controller.login(users_to_login)

        self.assertTrue(success)
        self.assertNotEquals(None, token)
        self.assertTrue(user_controller.check_token(token))

        user_controller.logout(token)
        self.assertFalse(user_controller.check_token(token))

    def test_get_usernames(self):
        """ Test getting all usernames. """
        user_controller = self._get_controller()
        self.assertEqual(['om'], user_controller.get_usernames())

        fields = ['username', 'password', 'role', 'enabled', 'accepted_terms']
        user_dto = UserDTO(
            username='test',
            password='test',
            role="admin",
            enabled=True
        )
        user_controller.save_users([(user_dto, fields)])

        self.assertEqual(['om', 'test'], user_controller.get_usernames())

    def test_remove_user(self):
        """ Test removing a user. """
        user_controller = self._get_controller()
        self.assertEqual(['om'], user_controller.get_usernames())

        fields = ['username', 'password', 'role', 'enabled', 'accepted_terms']
        user_dto = UserDTO(
            username='test',
            password='test',
            role="admin",
            enabled=True,
            accepted_terms=1
        )
        user_controller.save_users([(user_dto, fields)])

        user_dto_login = UserDTO(
            username='test',
            password='test',
            role="admin",
            enabled=True
        )
        users_to_login = [(user_dto_login, False, None)]
        success, token = user_controller.login(users_to_login)
        self.assertTrue(success)
        self.assertTrue(user_controller.check_token(token))

        user_controller.remove_user('test')

        self.assertFalse(user_controller.check_token(token))
        self.assertEqual(['om'], user_controller.get_usernames())

        try:
            user_controller.remove_user('om')
            self.fail('Should have raised exception !')
        except Exception as exception:
            self.assertEqual('Cannot delete last admin account', str(exception))

    def test_case_insensitive(self):
        """ Test the case insensitivity of the username. """
        user_controller = self._get_controller()

        fields = ['username', 'password', 'role', 'enabled', 'accepted_terms']
        user_dto = UserDTO(
            username='TEST',
            password='test',
            role="admin",
            enabled=True,
            accepted_terms=1
        )
        user_controller.save_users([(user_dto, fields)])

        user_dto_login = UserDTO(
            username='test',
            password='test',
            role="admin",
            enabled=True
        )
        users_to_login = [(user_dto_login, False, None)]
        success, token = user_controller.login(users_to_login)
        self.assertTrue(success)
        self.assertTrue(user_controller.check_token(token))

        user_dto_login = UserDTO(
            username='TeSt',
            password='test',
            role="admin",
            enabled=True
        )
        users_to_login = [(user_dto_login, False, None)]
        success, token = user_controller.login(users_to_login)
        self.assertTrue(success)
        self.assertTrue(user_controller.check_token(token))

        user_dto_login = UserDTO(
            username='test',
            password='TeSt',
            role="admin",
            enabled=True
        )
        users_to_login = [(user_dto_login, False, None)]
        success, token = user_controller.login(users_to_login)
        self.assertFalse(success)
        self.assertEqual('invalid_credentials', token)

        self.assertEqual(['om', 'test'], user_controller.get_usernames())


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
