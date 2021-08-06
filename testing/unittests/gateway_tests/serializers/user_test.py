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

import mock
import unittest
from gateway.dto import UserDTO, ApartmentDTO
from gateway.api.serializers import UserSerializer
from gateway.apartment_controller import ApartmentController


class UserSerializerTest(unittest.TestCase):
    def test_serialize(self):
        # empty
        dto = UserDTO()
        data = UserSerializer.serialize(dto)
        self.assertEqual(set(), set(dto.loaded_fields))
        self.assertEqual(data,
                         {'apartment': None,
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
                         {'apartment': None,
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
                         {'apartment': None,
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
                         {'apartment': None,
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
                      pin_code='1234', apartment=None, is_active=False, language='Nederlands',
                      accepted_terms=1, email='test@test.com')
        data = UserSerializer.serialize(dto)
        fields = {'username', 'first_name', 'apartment', 'accepted_terms', 'language', 'is_active', 'last_name', 'role', 'id', 'pin_code', 'email'}
        self.assertEqual(fields, set(dto.loaded_fields))
        self.assertEqual(data,
                         {'apartment': None,
                          'username': 'first.last',
                          'first_name': 'first',
                          'last_name': 'last',
                          'id': 37,
                          'is_active': False,
                          'language': 'Nederlands',
                          'role': 'USER',
                          'accepted_terms': 1,
                          'email': 'test@test.com'})

        # apartment
        apartment_dto = ApartmentDTO(id=37, name='test_app', mailbox_rebus_id=37, doorbell_rebus_id=37)
        dto = UserDTO(id=37, first_name='first', last_name='last', role='USER',
                      pin_code='1234', apartment=apartment_dto, is_active=False, language='Nederlands',
                      accepted_terms=1)
        data = UserSerializer.serialize(dto)
        fields = {'username', 'first_name', 'apartment', 'accepted_terms', 'language', 'is_active', 'last_name', 'role', 'id', 'pin_code'}
        self.assertEqual(fields, set(dto.loaded_fields))
        self.assertEqual(data,
                         {'apartment': {
                             'id': 37,
                             'name': 'test_app',
                             'mailbox_rebus_id': 37,
                             'doorbell_rebus_id': 37
                           },
                          'username': 'first.last',
                          'first_name': 'first',
                          'last_name': 'last',
                          'id': 37,
                          'is_active': False,
                          'language': 'Nederlands',
                          'role': 'USER',
                          'accepted_terms': 1,
                          'email': None})

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

        # apartment
        serial = {
            'first_name': 'first',
            'last_name': 'last',
            'role': 'USER',
            'id': 37,
            'apartment': [2],
            'pin_code': '1234',
            'is_active': False,
        }
        apartment_dto = ApartmentDTO(id=2, name='app_2', mailbox_rebus_id=37, doorbell_rebus_id=37)
        with mock.patch.object(ApartmentController, 'apartment_id_exists', return_value=True) as apartment_id_exists_func, \
                mock.patch.object(ApartmentController, 'load_apartment', return_value=apartment_dto) as load_apartment_func:
            dto = UserSerializer.deserialize(serial)
            apartment_id_exists_func.assert_called_once_with(2)
            load_apartment_func.assert_called_once_with(2)
            expected = UserDTO(first_name=serial['first_name'],
                               last_name=serial['last_name'],
                               role=serial['role'],
                               id=serial['id'],
                               apartment=apartment_dto,
                               is_active=serial['is_active'],
                               pin_code=serial['pin_code'])
            expected.username = None
            self.assertEqual(expected, dto)
