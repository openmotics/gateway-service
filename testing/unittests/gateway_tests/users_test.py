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

import fakesleep
import time
import unittest

from peewee import SqliteDatabase

from gateway.authentication_controller import AuthenticationController, TokenStore, LoginMethod, AuthenticationToken
from gateway.dto import UserDTO, RfidDTO
from gateway.enums import UserEnums
from gateway.exceptions import GatewayException
from gateway.mappers.user import UserMapper
from gateway.models import User, RFID
from gateway.rfid_controller import RfidController
from gateway.user_controller import UserController
from ioc import SetTestMode, SetUpTestInjections

MODELS = [User, RFID]


class UserControllerTest(unittest.TestCase):
    """ Tests for UserController. """
    TOKEN_TIMEOUT = 3

    @classmethod
    def setUpClass(cls):
        super(UserControllerTest, cls).setUpClass()
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')
        fakesleep.monkey_patch()

    @classmethod
    def tearDownClass(cls):
        super(UserControllerTest, cls).tearDownClass()
        fakesleep.monkey_restore()

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        SetUpTestInjections(config={'username': 'om', 'password': 'pass'},
                            token_timeout=UserControllerTest.TOKEN_TIMEOUT)
        SetUpTestInjections(token_store=TokenStore())
        self.rfid_controller = RfidController()
        SetUpTestInjections(rfid_controller=self.rfid_controller)
        SetUpTestInjections(authentication_controller=AuthenticationController())
        self.controller = UserController()
        self.controller.start()

        self.test_super = UserDTO(
            username='om',
            role='SUPER',
            language='English'
        )
        self.test_super.set_password('pass')

    def tearDown(self):
        self.controller.stop()
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_save_user(self):
        """ Test that the users are saved correctly """
        # first test that the cloud user has been saved
        num_users = self.controller.get_number_of_users()
        self.assertEqual(1, num_users)

        num_users = User.select().count()
        self.assertEqual(1, num_users)

        # setup test credentials
        user_dto = UserDTO(username='fred',
                           role=User.UserRoles.ADMIN,
                           pin_code='1234')
        user_dto.set_password("test")
        self.controller.save_user(user_dto)

        user_orm = User.select().where(User.username == 'fred').first()
        self.assertIsNotNone(user_orm)

        num_users = self.controller.get_number_of_users()
        self.assertEqual(2, num_users)

        # setup test credentials
        user_dto = UserDTO(username='TEST',
                           role=User.UserRoles.USER,
                           pin_code='1234',
                           language='TEST')
        user_dto.set_password("test")
        self.assertRaises(RuntimeError, self.controller.save_user, user_dto)

        num_users = self.controller.get_number_of_users()
        self.assertEqual(2, num_users)

    def test_empty(self):
        """ Test an empty database. """
        # setup test credentials
        user_dto = UserDTO(username="fred")
        user_dto.set_password("test")

        # verify that the test credentials do not work
        success, data = self.controller.login(user_dto)
        self.assertFalse(success)
        self.assertEqual(data, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS)

        # check that a random token is not valid when empty
        self.assertEqual(False, self.controller.check_token('some token 123'))

        # create the cloud user credentials
        user_dto = UserDTO(username="om")
        user_dto.set_password("pass")

        # verify that the cloud user can login
        success, data = self.controller.login(user_dto)
        self.assertTrue(success)
        self.assertNotEqual(None, data)

        # verify that the cloud user token is valid.
        self.assertTrue(self.controller.check_token(data))

    def test_terms(self):
        """ Tests acceptance of the terms """
        # adding test user to the DB
        user_to_add = User(
            username='test',
            password=UserDTO._hash_password('test'),
            accepted_terms=False,
            pin_code='1234',
            role=User.UserRoles.ADMIN
        )
        user_to_add.save()

        # setup test credentials
        user_dto = UserDTO(username='test')
        user_dto.set_password('test')

        # check if login is possible
        success, data = self.controller.login(user_dto)
        self.assertFalse(success)
        self.assertEqual(data, 'terms_not_accepted')

        # login with accepted terms fields set
        success, data = self.controller.login(user_dto, accept_terms=True)
        self.assertTrue(success)
        self.assertIsNotNone(data)

        # login again to see if fields has been saved
        success, data = self.controller.login(user_dto)
        self.assertTrue(success)
        self.assertIsNotNone(data)

    def test_all(self):
        """ Test all methods of UserController. """
        # create a new user to test with
        user_dto = UserDTO(username='fred', pin_code='1234', role=User.UserRoles.ADMIN)
        user_dto.set_password('test')
        self.controller.save_users([user_dto])

        # check if the user has been added to the list
        users_in_controller = self.controller.load_users()
        self.assertEqual(2, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('fred', users_in_controller[1].username)
        self.assertEqual(2, self.controller.get_number_of_users())

        # try if user is able to login without accepting the terms
        success, token = self.controller.login(user_dto)
        self.assertEqual(False, success)
        self.assertEqual(UserEnums.AuthenticationErrors.TERMS_NOT_ACCEPTED, token)
        self.assertFalse(self.controller.check_token('blah'))

        # try if the user is able to login with terms accepted
        success, token = self.controller.login(user_dto, accept_terms=True)
        self.assertEqual(True, success)
        self.assertNotEqual(None, token)

        # check if the token is valid
        self.assertTrue(self.controller.check_token(token))
        self.assertFalse(self.controller.check_token('blah'))

        # try to logout the user
        self.controller.logout(token)
        self.assertFalse(self.controller.check_token(token))

        # try if the user is able to login with terms accepted
        success, token = self.controller.login(user_dto, accept_terms=True)
        self.assertEqual(True, success)
        self.assertNotEqual(None, token)

        # try to remove the user
        self.controller.remove_user(user_dto)
        self.assertFalse(self.controller.check_token(token))

        # check if the user has been deleted
        users_in_controller = self.controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual(1, self.controller.get_number_of_users())

        # try if the user is able to login with terms accepted
        success, token = self.controller.login(user_dto, accept_terms=True)
        self.assertEqual(False, success)
        self.assertEqual(UserEnums.AuthenticationErrors.INVALID_CREDENTIALS, token)

        # create multiple new users
        users_dto = []
        user_dto = UserDTO(username='simon', pin_code='5678', role=User.UserRoles.ADMIN)
        user_dto.set_password('test')
        users_dto.append(user_dto)
        user_dto = UserDTO(username='test', pin_code='9876', role=User.UserRoles.ADMIN)
        user_dto.set_password('test')
        users_dto.append(user_dto)
        self.controller.save_users(users_dto)

        # check if the user has been deleted
        users_in_controller = self.controller.load_users()
        self.assertEqual(3, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('simon', users_in_controller[1].username)
        self.assertEqual('test', users_in_controller[2].username)
        self.assertEqual(3, self.controller.get_number_of_users())

        # try if the user is able to login with terms accepted
        user_dto = UserDTO(username='simon')
        user_dto.set_password('test')
        success, token = self.controller.login(user_dto, accept_terms=True)
        self.assertEqual(True, success)
        self.assertNotEqual(None, token)

        # try to logout with the new users
        self.controller.logout(token)
        self.assertFalse(self.controller.check_token(token))

    def test_token_timeout(self):
        """ Test the timeout on the tokens. """

        # Setup credentials
        user_dto = UserDTO(username='om')
        user_dto.set_password('pass')
        # verify that the user can login
        success, token = self.controller.login(user_dto, accept_terms=True)
        self.assertEqual(True, success)
        self.assertNotEqual(None, token)

        # verify that the token is still valid
        self.assertTrue(self.controller.check_token(token))

        time.sleep(4)

        # verify that the token is no longer valid after timeout
        self.assertFalse(self.controller.check_token(token))

        # login again tot verify that the token is then again valid
        success, token = self.controller.login(user_dto, accept_terms=True)
        self.assertTrue(success)
        self.assertNotEqual(None, token)
        self.assertTrue(self.controller.check_token(token))

    def test_logout(self):
        """ Test logout. """
        # Setup the user credentials
        user_dto = UserDTO(username='om')
        user_dto.set_password('pass')

        # test to see if you are able to login
        success, token = self.controller.login(user_dto, accept_terms=True)
        self.assertTrue(success)
        self.assertNotEqual(None, token)
        self.assertTrue(self.controller.check_token(token))

        # check if after logout te user has a valid token
        self.controller.logout(token)
        self.assertFalse(self.controller.check_token(token))

    def test_load_users(self):
        """ Test getting all usernames. """
        # get first list of users in the user controller
        users_in_controller = self.controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('SUPER', users_in_controller[0].role)

        user_to_add = User(
            username='admin_1',
            password=UserDTO._hash_password('test'),
            pin_code='1111',
            role=User.UserRoles.ADMIN,
            accepted_terms=True
        )
        user_to_add.save()

        # check if the user has been added to the list
        users_in_controller = self.controller.load_users()
        self.assertEqual(2, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('admin_1', users_in_controller[1].username)

        # check if the number of users is correct
        num_users = self.controller.get_number_of_users()
        self.assertEqual(2, num_users)

        # Add a normal user and then load only normal users
        user_to_add = User(
            username='user_1',
            password=UserDTO._hash_password('test'),
            pin_code='2222',
            role=User.UserRoles.USER,
            accepted_terms=True
        )
        user_to_add.save()

        user_to_add = User(
            username='user_2',
            password=UserDTO._hash_password('test'),
            pin_code='3333',
            role=User.UserRoles.USER,
            accepted_terms=True,
            is_active=False
        )
        user_to_add.save()

        user_to_add = User(
            username='courier_1',
            password=UserDTO._hash_password('test'),
            pin_code='4444',
            role=User.UserRoles.COURIER,
            accepted_terms=True
        )
        user_to_add.save()

        # check if the number of users is correct
        num_users = self.controller.get_number_of_users()
        self.assertEqual(5, num_users)

        loaded_users = self.controller.load_users(roles=[User.UserRoles.USER], include_inactive=False)
        self.assertEqual(1, len(loaded_users))
        for user in loaded_users:
            self.assertEqual('USER', user.role)

        loaded_users = self.controller.load_users(roles=[User.UserRoles.USER], include_inactive=True)
        self.assertEqual(2, len(loaded_users))
        for user in loaded_users:
            self.assertEqual('USER', user.role)

        roles = [User.UserRoles.USER, User.UserRoles.ADMIN]
        loaded_users = self.controller.load_users(roles=roles)
        self.assertEqual(2, len(loaded_users))  # 1 admin users plus one regular user
        for user in loaded_users:
            self.assertIn(user.role, roles)

        roles = [User.UserRoles.USER, User.UserRoles.ADMIN, User.UserRoles.SUPER]
        loaded_users = self.controller.load_users(roles=roles)
        self.assertEqual(3, len(loaded_users))  # one super, one admin users plus one regular user
        for user in loaded_users:
            self.assertIn(user.role, roles)

    def test_remove_user(self):
        """ Test removing a user. """
        # check that there is only one user in the system
        users_in_controller = self.controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual(1, self.controller.get_number_of_users())

        # create a new user to test with
        user_to_add = User(
            username='test',
            password=UserDTO._hash_password('test'),
            pin_code='1234',
            role=User.UserRoles.ADMIN,
            accepted_terms=True
        )
        user_to_add.save()

        user_to_add = User(
            username='test2',
            password=UserDTO._hash_password('test'),
            pin_code=None,
            role=User.UserRoles.USER,
            accepted_terms=True
        )
        user_to_add.save()

        # creating equal credentials to use
        user_dto = UserDTO(username='test')
        user_dto.set_password('test')

        # verify that the user has been added
        users_in_controller = self.controller.load_users()
        self.assertEqual(3, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('test', users_in_controller[1].username)
        self.assertEqual(3, self.controller.get_number_of_users())

        # verify that the new user can log in to the system
        success, token = self.controller.login(user_dto, accept_terms=True)
        self.assertTrue(success)
        self.assertTrue(self.controller.check_token(token))

        # remove the newly created user
        self.controller.remove_user(user_dto)

        # Verify that the user is logged out of the system
        self.assertFalse(self.controller.check_token(token))

        # verify that the user is deleted from the system
        users_in_controller = self.controller.load_users()
        self.assertEqual(2, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual(2, self.controller.get_number_of_users())

        # Delete the user with capitals in the username, should not matter
        user_dto_2 = UserDTO(username='teST2')

        # remove the newly created user
        self.controller.remove_user(user_dto_2)
        # verify that the user is deleted from the system
        users_in_controller = self.controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual(1, self.controller.get_number_of_users())

        # verify that the last user cannot be deleted.
        try:
            last_user_dto = UserDTO(username='om')
            self.controller.remove_user(last_user_dto)
            self.fail('Should have raised exception !')
        except GatewayException as ex:
            self.assertIn(UserEnums.DeleteErrors.LAST_ACCOUNT, ex.message)

    def test_case_insensitive(self):
        """ Test the case insensitivity of the username. """
        # check that there is only one user in the system
        users_in_controller = self.controller.load_users()
        self.assertEqual(1, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)

        # create a new user to test with
        user_dto = UserDTO(username='test', pin_code='1234', role=User.UserRoles.ADMIN)
        user_dto.set_password('test')
        self.controller.save_users([user_dto])

        # verify that the user can log in with regular username
        success, token = self.controller.login(user_dto, accept_terms=True)
        self.assertTrue(success)
        self.assertTrue(self.controller.check_token(token))

        # verify that the user can log in with capitals
        user_dto.username = 'TeSt'
        success, token = self.controller.login(user_dto)
        self.assertTrue(success)
        self.assertTrue(self.controller.check_token(token))

        # verify that the user can not login with password with changed capitals
        user_dto.set_password('TeSt')
        success, token = self.controller.login(user_dto)
        self.assertFalse(success)
        self.assertEqual(UserEnums.AuthenticationErrors.INVALID_CREDENTIALS, token)

        # verify that the user has been added
        users_in_controller = self.controller.load_users()
        self.assertEqual(2, len(users_in_controller))
        self.assertEqual('om', users_in_controller[0].username)
        self.assertEqual('test', users_in_controller[1].username)
        self.assertEqual(2, self.controller.get_number_of_users())

    def test_user_mapper(self):

        def validate_two_way(user):
            user_orm = UserMapper.dto_to_orm(user)
            user_dto_converted = UserMapper.orm_to_dto(user_orm)
            for field in user.loaded_fields:
                if field != 'password':
                    self.assertEqual(getattr(user, field), getattr(user_dto_converted, field))

        def convert_back_and_forth(user):
            user_orm = UserMapper.dto_to_orm(user)

            self.assertEqual(True, hasattr(user_orm, "username"))
            self.assertEqual(True, hasattr(user_orm, "password"))
            self.assertEqual(True, hasattr(user_orm, "accepted_terms"))
            self.assertEqual(True, hasattr(user_orm, "role"))

            self.assertEqual(User.UserRoles.USER, user_orm.role)
            self.assertEqual(user.pin_code, user_orm.pin_code)

            self.assertEqual(user.username, user_orm.username)
            self.assertEqual(UserDTO._hash_password('test'), user_orm.password)
            self.assertEqual(user.accepted_terms, user_orm.accepted_terms)

            user_dto_converted = UserMapper.orm_to_dto(user_orm)
            self.assertEqual(user.username, user_dto_converted.username)
            self.assertEqual(user_orm.password, user_dto_converted.hashed_password)
            self.assertEqual(user.accepted_terms, user_dto_converted.accepted_terms)

        user_dto = UserDTO(username='test',
                           role=User.UserRoles.USER,
                           pin_code='1234',
                           accepted_terms=1)
        user_dto.set_password('test')

        convert_back_and_forth(user_dto)
        validate_two_way(user_dto)

        user_dto = UserDTO(first_name='first',
                           last_name='last',
                           role='USER',
                           accepted_terms=1)
        user_dto.set_password('test')
        convert_back_and_forth(user_dto)
        validate_two_way(user_dto)

        user_dto = UserDTO(first_name='first',
                           last_name='last',
                           accepted_terms=1)
        user_dto.set_password('test')
        convert_back_and_forth(user_dto)
        validate_two_way(user_dto)

    def test_login_user_code(self):
        user_dto = UserDTO(username='fred', pin_code='1234', role=User.UserRoles.USER)
        user_dto.set_password('test')
        self.controller.save_users([user_dto])
        self.assertEqual(2, self.controller.get_number_of_users())

        success, data = self.controller.authentication_controller.login_with_user_code('1234', accept_terms=True)
        self.assertTrue(success)
        self.assertEqual(data.user.username, 'fred')
        self.assertEqual(LoginMethod.PIN_CODE, data.login_method)

        success, data = self.controller.authentication_controller.login_with_user_code('9876', accept_terms=True)
        self.assertFalse(success)
        self.assertEqual(data, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS)

    def test_login_rfid_tags(self):
        user_dto = UserDTO(username='fred', pin_code='1234', role=User.UserRoles.USER)
        user_dto.set_password('test')
        user_dto = self.controller.save_user(user_dto)
        self.assertEqual(2, self.controller.get_number_of_users())

        # add an rfid to fred to test the login
        rfid_dto = RfidDTO(tag_string='rfid-test-tag', label='test-badge', user=user_dto, enter_count=-1, uid_manufacturer='test-uid-manufact')
        self.rfid_controller.save_rfid(rfid_dto)

        success, data = self.controller.authentication_controller.login_with_rfid_tag('rfid-test-tag', accept_terms=True)
        self.assertTrue(success)
        self.assertEqual(data.user.username, 'fred')
        self.assertEqual(LoginMethod.RFID, data.login_method)

        success, data = self.controller.authentication_controller.login_with_rfid_tag('9876', accept_terms=True)
        self.assertFalse(success)
        self.assertEqual(data, UserEnums.AuthenticationErrors.INVALID_CREDENTIALS)

        # Add in a third user
        user_pol_dto = UserDTO(username='pol', pin_code='9876', role=User.UserRoles.USER)
        user_pol_dto.set_password('test')
        user_pol_dto = self.controller.save_user(user_pol_dto)
        self.assertEqual(3, self.controller.get_number_of_users())
        # add an rfid to pol to test the login
        rfid_pol_dto = RfidDTO(tag_string='rfid-test-tag-pol', label='test-badge', user=user_pol_dto, enter_count=-1, uid_manufacturer='test-uid-manufact_pol')
        self.rfid_controller.save_rfid(rfid_pol_dto)

        success, data = self.controller.authentication_controller.login_with_rfid_tag('rfid-test-tag-pol', accept_terms=True)
        self.assertTrue(success)
        self.assertEqual(data.user.username, 'pol')
        self.assertEqual(LoginMethod.RFID, data.login_method)

    def test_impersonate_happy(self):
        user_dto = UserDTO(username='fred', pin_code='1234', role=User.UserRoles.USER)
        user_dto.set_password('test')
        user_dto = self.controller.save_user(user_dto)
        self.assertEqual(2, self.controller.get_number_of_users())

        success, data = self.controller.login(self.test_super, accept_terms=False, timeout=None, impersonate='fred')
        self.assertTrue(success)
        self.assertTrue(isinstance(data, AuthenticationToken))

        impersonate_token = data

        token_is_valid = self.controller.check_token(impersonate_token)
        self.assertTrue(token_is_valid)

        token = self.controller.authentication_controller.check_token(impersonate_token)
        self.assertEqual('USER', token.user.role)
        self.assertEqual('fred', token.user.username)
        self.assertEqual(self.test_super.username, token.impersonator.username)
        self.assertEqual(LoginMethod.PASSWORD, token.login_method)


