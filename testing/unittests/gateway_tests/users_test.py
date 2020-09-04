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

import os
import tempfile
import time
import unittest
import xmlrunner
from threading import Lock
from pytest import mark
from peewee import SqliteDatabase

from gateway.user_controller import UserController
from gateway.dto import UserDTO
from gateway.enums import UserEnums
from gateway.mappers.user import UserMapper
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
        user_dto = UserDTO("fred")
        user_dto.set_password("test")
        success, data = user_controller.login(user_dto)
        self.assertFalse(success)
        self.assertEqual(data, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS)
        self.assertEqual(False, user_controller.check_token('some token 123'))

        user_dto = UserDTO("om")
        user_dto.set_password("pass")
        success, data = user_controller.login(user_dto)
        self.assertTrue(success)
        self.assertNotEquals(None, data)

        self.assertTrue(user_controller.check_token(data))

    def test_terms(self):
        """ Tests acceptance of the terms """
        user_controller = self._get_controller()
        # adding test user
        fields = ['username', 'password', 'accepted_terms']
        user_dto = UserDTO(username='om2')
        user_dto.set_password('pass')
        user_controller.save_users([(user_dto, fields)])

        # check if login is possible
        success, data = user_controller.login(user_dto)
        self.assertFalse(success)
        self.assertEqual(data, 'terms_not_accepted')

        # login with accepted terms fields set
        success, data = user_controller.login(user_dto, accept_terms=True)
        self.assertTrue(success)
        self.assertIsNotNone(data)


        # login again to see if fields has been saved
        success, data = user_controller.login(user_dto)
        self.assertTrue(success)
        self.assertIsNotNone(data)

    def test_all(self):
        """ Test all methods of UserController. """
        user_controller = self._get_controller()
        fields = ['username', 'password', 'accepted_terms']

        # create a new user to test with
        user_dto = UserDTO(username='fred')
        user_dto.set_password('test')
        user_controller.save_users([(user_dto, fields)])

        # check if the user has been added to the list
        users_in_controller = user_controller.load_users()
        self.assertEqual(2, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('fred', users_in_controller[1].username)
        self.assertEqual(2, user_controller.get_number_of_users())

        # try if user is able to login without accepting the terms
        success, token = user_controller.login(user_dto)
        self.assertEqual(False, success)
        self.assertEqual(UserEnums.AuthenticationErrors.TERMS_NOT_ACCEPTED, token)
        self.assertFalse(user_controller.check_token('blah'))

        # try if the user is able to login with terms accepted
        success, token = user_controller.login(user_dto, accept_terms=True)
        self.assertEqual(True, success)
        self.assertNotEquals(None, token)

        # check if the token is valid
        self.assertTrue(user_controller.check_token(token))
        self.assertFalse(user_controller.check_token('blah'))

        # try to logout the user
        user_controller.logout(token)
        self.assertFalse(user_controller.check_token(token))

        # try if the user is able to login with terms accepted
        success, token = user_controller.login(user_dto, accept_terms=True)
        self.assertEqual(True, success)
        self.assertNotEquals(None, token)

        # try to remove the user
        user_controller.remove_user(user_dto)
        self.assertFalse(user_controller.check_token(token))

        # check if the user has been deleted
        users_in_controller = user_controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual(1, user_controller.get_number_of_users())

        # try if the user is able to login with terms accepted
        success, token = user_controller.login(user_dto, accept_terms=True)
        self.assertEqual(False, success)
        self.assertEqual(UserEnums.AuthenticationErrors.INVALID_CREDENTIALS, token)

        # create multiple new users
        users_dto = []
        user_dto = UserDTO(username='fred')
        user_dto.set_password('test')
        users_dto.append(user_dto)
        user_dto = UserDTO(username='test')
        user_dto.set_password('test')
        users_dto.append(user_dto)
        to_save_users = [(ud, fields) for ud in users_dto]
        user_controller.save_users(to_save_users)

        # check if the user has been deleted
        users_in_controller = user_controller.load_users()
        self.assertEqual(3, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('fred', users_in_controller[1].username)
        self.assertEqual('test', users_in_controller[2].username)
        self.assertEqual(3, user_controller.get_number_of_users())

        # try if the user is able to login with terms accepted
        user_dto = UserDTO(username='fred')
        user_dto.set_password('test')
        success, token = user_controller.login(user_dto, accept_terms=True)
        self.assertEqual(True, success)
        self.assertNotEquals(None, token)

        # try to logout with the new users
        user_controller.logout(token)
        self.assertFalse(user_controller.check_token(token))



    # @mark.slow
    # def test_token_timeout(self):
    #     """ Test the timeout on the tokens. """
    #     SetUpTestInjections(config={'username': 'om', 'password': 'pass'},
    #                         token_timeout=3)
    #     user_controller = UserController()

    #     fields = ['username', 'password', 'accepted_terms']

    #     # create a new user to test with
    #     user_dto = UserDTO(username='om')
    #     user_dto.set_password('pass')
    #     success, token = user_controller.login(user_dto, accept_terms=True)
    #     self.assertEqual(True, success)
    #     self.assertNotEquals(None, token)
    #     self.assertTrue(user_controller.check_token(token))

    #     time.sleep(4)

    #     self.assertFalse(user_controller.check_token(token))

    #     success, token = user_controller.login(user_dto, accept_terms=True)
    #     self.assertTrue(success)
    #     self.assertNotEquals(None, token)
    #     self.assertTrue(user_controller.check_token(token))

    def test_logout(self):
        """ Test logout. """
        user_controller = UserController()

        # create a new user to test with
        user_dto = UserDTO(username='om')
        user_dto.set_password('pass')

        # test to see if you are able to login
        success, token = user_controller.login(user_dto, accept_terms=True)
        self.assertTrue(success)
        self.assertNotEquals(None, token)
        self.assertTrue(user_controller.check_token(token))

        # check if after logout te user has a valid token
        user_controller.logout(token)
        self.assertFalse(user_controller.check_token(token))

    def test_get_usernames(self):
        """ Test getting all usernames. """
        user_controller = self._get_controller()

        # get first list of users in the user controller
        users_in_controller = user_controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)


        fields = ['username', 'password', 'accepted_terms']

        # create a new user to test with
        user_dto = UserDTO(username='test')
        user_dto.set_password('test')
        user_controller.save_users([(user_dto, fields)])


        # check if the user has been added to the list
        users_in_controller = user_controller.load_users()
        self.assertEqual(2, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('test', users_in_controller[1].username)

        # check if the number of users is correct
        num_users = user_controller.get_number_of_users()
        self.assertEqual(2, num_users)


    def test_remove_user(self):
        """ Test removing a user. """
        user_controller = self._get_controller()

        fields = ['username', 'password', 'accepted_terms']

        # check that there is only one user in the system
        users_in_controller = user_controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual(1, user_controller.get_number_of_users())

        # create a new user to test with
        user_dto = UserDTO(username='test')
        user_dto.set_password('test')
        user_controller.save_users([(user_dto, fields)])

        # verify that the user has been added
        users_in_controller = user_controller.load_users()
        self.assertEqual(2, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('test', users_in_controller[1].username)
        self.assertEqual(2, user_controller.get_number_of_users())

        # verify that the new user can log in to the system
        success, token = user_controller.login(user_dto, accept_terms=True)
        self.assertTrue(success)
        self.assertTrue(user_controller.check_token(token))

        # remove the newly created user
        user_controller.remove_user(user_dto)

        # Verify that the user is logged out of the system
        self.assertFalse(user_controller.check_token(token))

        # verify that the user is deleted from the system
        users_in_controller = user_controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual(1, user_controller.get_number_of_users())

        try:
            last_user_dto = UserDTO(username='om')
            user_controller.remove_user(last_user_dto)
            self.fail('Should have raised exception !')
        except Exception as exception:
            self.assertEqual(UserEnums.DeleteErrors.LAST_ACCOUNT, str(exception))

    def test_case_insensitive(self):
        """ Test the case insensitivity of the username. """
        user_controller = self._get_controller()

        fields = ['username', 'password', 'accepted_terms']

        # check that there is only one user in the system
        users_in_controller = user_controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)

        # create a new user to test with
        user_dto = UserDTO(username='test')
        user_dto.set_password('test')
        user_controller.save_users([(user_dto, fields)])

        # verify that the user can log in with regular username
        success, token = user_controller.login(user_dto, accept_terms=True)
        self.assertTrue(success)
        self.assertTrue(user_controller.check_token(token))

        # verify that the user can log in with capitals
        user_dto.username = 'TeSt'
        success, token = user_controller.login(user_dto)
        self.assertTrue(success)
        self.assertTrue(user_controller.check_token(token))

        # verify that the user can not login with password with changed capitals
        user_dto.set_password('TeSt')
        success, token = user_controller.login(user_dto)
        self.assertFalse(success)
        self.assertEqual(UserEnums.AuthenticationErrors.INVALID_CREDENTIALS, token)

        # verify that the user has been added
        users_in_controller = user_controller.load_users()
        self.assertEqual(2, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('test', users_in_controller[1].username)
        self.assertEqual(2, user_controller.get_number_of_users())


    def test_usermapper(self):
        user_dto = UserDTO(username='test', accepted_terms=1)
        user_dto.set_password('test')

        user_orm = UserMapper.dto_to_orm(user_dto, ['username', 'password'])

        self.assertEqual(True, hasattr(user_orm, "username"))
        self.assertEqual(True, hasattr(user_orm, "password"))
        self.assertEqual(True, hasattr(user_orm, "accepted_terms"))

        self.assertEqual('test', user_orm.username)
        self.assertEqual(UserDTO._hash_password('test'), user_orm.password)
        self.assertEqual(0, user_orm.accepted_terms)


        user_dto = UserMapper.orm_to_dto(user_orm)
        self.assertEqual('test', user_dto.username)
        self.assertEqual(user_orm.password, user_dto.hashed_password)
        self.assertEqual(0, user_dto.accepted_terms)


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
