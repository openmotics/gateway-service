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
User serializer tests
"""
import mock
import unittest

from gateway.api.serializers import UserSerializer
from gateway.dto import UserDTO

if False:
    from typing import Dict, Any

class userSerializerTest(unittest.TestCase):

    def assert_dto_match_serial(self, user_dto, user_serial, include_pin=False):
        # type: (UserDTO, Dict[Any, Any], bool) -> None
        for field in user_dto.loaded_fields:
            if field != 'pin_code' or include_pin:
                self.assertEqual(getattr(user_dto, field), user_serial[field])
            else:
                self.assertNotIn('pin_code', user_serial)

    def test_user_serialize(self):
        # empty
        dto = UserDTO()
        data = UserSerializer.serialize(dto)
        self.assertEqual(set(), set(dto.loaded_fields))
        self.assertEqual(data,
                         {
                          'username': None,
                          'first_name': '',
                          'last_name': '',
                          'id': None,
                          'is_active': None,
                          'language': 'en',
                          'role': None,
                          'accepted_terms': 0,
                          'email': None})

        # only username
        dto = UserDTO(username='test')
        data = UserSerializer.serialize(dto)
        self.assertEqual({'username'}, set(dto.loaded_fields))
        self.assertEqual(data,
                         {
                          'username': 'test',
                          'first_name': '',
                          'last_name': '',
                          'id': None,
                          'is_active': None,
                          'language': 'en',
                          'role': None,
                          'accepted_terms': 0,
                          'email': None})

        # only first and last name
        dto = UserDTO(first_name='first', last_name='last')
        data = UserSerializer.serialize(dto)
        self.assertEqual({'username', 'first_name', 'last_name'}, set(dto.loaded_fields))
        self.assertEqual('first.last', dto.username)
        self.assertEqual(data,
                         {
                          'username': 'first.last',
                          'first_name': 'first',
                          'last_name': 'last',
                          'id': None,
                          'is_active': None,
                          'language': 'en',
                          'role': None,
                          'accepted_terms': 0,
                          'email':None})

        # only role
        dto = UserDTO(role='USER')
        data = UserSerializer.serialize(dto)
        self.assertEqual({'role'}, set(dto.loaded_fields))
        self.assertEqual(data,
                         {
                          'username': None,
                          'first_name': '',
                          'last_name': '',
                          'id': None,
                          'is_active': None,
                          'language': 'en',
                          'role': 'USER',
                          'accepted_terms': 0,
                          'email': None})

        # full
        dto = UserDTO(id=37, first_name='first', last_name='last', role='USER',
                      pin_code='1234', is_active=False, language='Nederlands',
                      accepted_terms=1, email='test@test.com')
        data = UserSerializer.serialize(dto)
        fields = {'username', 'first_name', 'accepted_terms', 'language', 'is_active', 'last_name', 'role', 'id', 'pin_code', 'email'}
        self.assertEqual(fields, set(dto.loaded_fields))
        self.assertEqual(data,
                         {
                          'username': 'first.last',
                          'first_name': 'first',
                          'last_name': 'last',
                          'id': 37,
                          'is_active': False,
                          'language': 'Nederlands',
                          'role': 'USER',
                          'accepted_terms': 1,
                          'email': 'test@test.com'})

        dto = UserDTO(id=37, first_name='first', last_name='last', role='USER',
                      pin_code='1234', is_active=False, language='Nederlands',
                      accepted_terms=1)
        data = UserSerializer.serialize(dto)
        fields = {'username', 'first_name', 'accepted_terms', 'language', 'is_active', 'last_name', 'role', 'id', 'pin_code'}
        self.assertEqual(fields, set(dto.loaded_fields))
        self.assertEqual(data,
                         {
                          'username': 'first.last',
                          'first_name': 'first',
                          'last_name': 'last',
                          'id': 37,
                          'is_active': False,
                          'language': 'Nederlands',
                          'role': 'USER',
                          'accepted_terms': 1,
                          'email': None})
        user_dto = UserDTO(
            id=37,
            first_name='first',
            last_name='last',
            role='ADMIN',
            pin_code='1234',
            language='en',
            accepted_terms=1,
            is_active=True,
            email='test@test.com'
        )
        # validate the basic serialization usecase
        user_serial = UserSerializer.serialize(user_dto)
        self.assert_dto_match_serial(user_dto, user_serial, include_pin=False)

        # validate that when the pin_code is included it is added
        user_serial_with_pin = UserSerializer.serialize(user_dto, show_pin_code=True)
        self.assert_dto_match_serial(user_dto, user_serial_with_pin, include_pin=True)

    def test_user_deserialize(self):
        user_serial = {
            'username': 'first.last',
            'last_name': 'last',
            'accepted_terms': 1,
            'is_active': True,
            'id': 37,
            'pin_code': '1234',
            'first_name': 'first',
            'language': 'en',
            'role': 'ADMIN',
            'email': 'test@test.com'
        }
        user_dto = UserSerializer.deserialize(user_serial)
        self.assert_dto_match_serial(user_dto, user_serial, include_pin=True)

        # only first name
        serial = {
            'first_name': 'first'
        }
        dto = UserSerializer.deserialize(serial)
        # set first name afterwards to not set the username
        expected = UserDTO()
        expected.first_name = 'first'
        self.assertEqual(expected, dto)

        # email
        serial = {
            'email': 'test@test.com'
        }
        dto = UserSerializer.deserialize(serial)
        # set first name afterwards to not set the username
        expected = UserDTO()
        expected.email = 'test@test.com'
        self.assertEqual(expected, dto)

        serial = {
            'email': 'wrong_@testcom'
        }
        with self.assertRaises(ValueError):
            UserSerializer.deserialize(serial)

        # full
        serial = {
            'first_name': 'first',
            'last_name': 'last',
            'role': 'USER',
            'id': 37,
            'pin_code': '1234',
            'is_active': False,
        }
        dto = UserSerializer.deserialize(serial)
        expected = UserDTO(first_name=serial['first_name'],
                           last_name=serial['last_name'],
                           role=serial['role'],
                           id=serial['id'],
                           is_active=serial['is_active'],
                           pin_code=serial['pin_code'])
        expected.username = None
        self.assertEqual(expected, dto)

