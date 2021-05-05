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
from __future__ import absolute_import

import unittest
from gateway.dto import UserDTO, ApartmentDTO
from gateway.api.serializers import UserSerializer


class UserSerializerTest(unittest.TestCase):
    def test_serialize(self):
        # empty
        dto = UserDTO()
        data = UserSerializer.serialize(dto)
        self.assertEqual(set(), set(dto.loaded_fields))
        self.assertEqual(data,
                         {'apartment': None,
                          'first_name': '',
                          'last_name': '',
                          'id': None,
                          'is_active': None,
                          'language': 'English',
                          'role': None,
                          'accepted_terms': 0})

        # only username
        dto = UserDTO(username='test')
        data = UserSerializer.serialize(dto)
        self.assertEqual({'username'}, set(dto.loaded_fields))
        self.assertEqual(data,
                         {'apartment': None,
                          'first_name': '',
                          'last_name': '',
                          'id': None,
                          'is_active': None,
                          'language': 'English',
                          'role': None,
                          'accepted_terms': 0})

        # only first and last name
        dto = UserDTO(first_name='first', last_name='last')
        data = UserSerializer.serialize(dto)
        self.assertEqual({'username', 'first_name', 'last_name'}, set(dto.loaded_fields))
        self.assertEqual('first.last', dto.username)
        self.assertEqual(data,
                         {'apartment': None,
                          'first_name': 'first',
                          'last_name': 'last',
                          'id': None,
                          'is_active': None,
                          'language': 'English',
                          'role': None,
                          'accepted_terms': 0})

        # only role
        dto = UserDTO(role='USER')
        data = UserSerializer.serialize(dto)
        self.assertEqual({'role'}, set(dto.loaded_fields))
        self.assertEqual(data,
                         {'apartment': None,
                          'first_name': '',
                          'last_name': '',
                          'id': None,
                          'is_active': None,
                          'language': 'English',
                          'role': 'USER',
                          'accepted_terms': 0})

        # full
        dto = UserDTO(id=37, first_name='first', last_name='last', role='USER',
                      pin_code='1234', apartment=None, is_active=False, language='Nederlands',
                      accepted_terms=1)
        data = UserSerializer.serialize(dto)
        fields = {'username', 'first_name', 'apartment', 'accepted_terms', 'language', 'is_active', 'last_name', 'role', 'id', 'pin_code'}
        self.assertEqual(fields, set(dto.loaded_fields))
        self.assertEqual(data,
                         {'apartment': None,
                          'first_name': 'first',
                          'last_name': 'last',
                          'id': 37,
                          'is_active': False,
                          'language': 'Nederlands',
                          'role': 'USER',
                          'accepted_terms': 1})

        # TODO: add an apartment test

    def test_deserialize(self):
        # only first name
        serial = {
            'first_name': 'first'
        }
        dto = UserSerializer.deserialize(serial)
        # set first name afterwards to not set the username
        expected = UserDTO()
        expected.first_name = 'first'
        self.assertEqual(expected, dto)

        # username
        serial = {
            'username': 'username'
        }
        dto = UserSerializer.deserialize(serial)
        # username is not accepted
        expected = UserDTO()
        self.assertEqual(expected, dto)

        # full
        serial = {
            'first_name': 'first',
            'last_name': 'last',
            'role': 'USER',
            'id': 37,
            'apartment': None,
            'pin_code': '1234',
            'is_active': False,
        }
        dto = UserSerializer.deserialize(serial)
        expected = UserDTO(first_name=serial['first_name'],
                           last_name=serial['last_name'],
                           role=serial['role'],
                           id=serial['id'],
                           apartment=serial['apartment'],
                           is_active=serial['is_active'],
                           pin_code=serial['pin_code'])
        expected.username = None
        self.assertEqual(expected, dto)

        # TODO: Add an apartment test