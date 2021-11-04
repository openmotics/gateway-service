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
from gateway.dto import DeliveryDTO, UserDTO
from gateway.api.serializers import DeliverySerializer, UserSerializer
from gateway.user_controller import UserController
from ioc import SetTestMode, SetUpTestInjections



class DeliverySerializerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.user_controller = mock.Mock(UserController)
        SetUpTestInjections(user_controller=self.user_controller)

    def test_serialize(self):
        # empty
        dto = DeliveryDTO()
        data = DeliverySerializer.serialize(dto)
        self.assertEqual(set(), set(dto.loaded_fields))
        self.assertEqual(data,
                         {'id': None,
                          'type': None,
                          'timestamp_delivery': None,
                          'timestamp_pickup': None,
                          'courier_firm': None,
                          'signature_delivery': None,
                          'signature_pickup': None,
                          'parcelbox_rebus_id': None,
                          'user_id_delivery': None,
                          'user_id_pickup': None})

        # only id
        dto = DeliveryDTO(id=4)
        data = DeliverySerializer.serialize(dto)
        self.assertEqual({'id'}, set(dto.loaded_fields))
        self.assertEqual(data,
                         {'id': 4,
                          'type': None,
                          'timestamp_delivery': None,
                          'timestamp_pickup': None,
                          'courier_firm': None,
                          'signature_delivery': None,
                          'signature_pickup': None,
                          'parcelbox_rebus_id': None,
                          'user_id_delivery': None,
                          'user_id_pickup': None})

        # with users
        dto = DeliveryDTO(id=4)
        user_delivery_dto = UserDTO(id=4, username='test', first_name='first', last_name='last', role='ADMIN')
        user_pickup_dto = UserDTO(id=5, username='test', first_name='first', last_name='last', role='ADMIN')
        dto.user_delivery = user_delivery_dto
        dto.user_pickup = user_pickup_dto
        data = DeliverySerializer.serialize(dto)
        self.assertEqual({'id', 'user_delivery', 'user_pickup'}, set(dto.loaded_fields))
        self.assertEqual(data,
                         {'id': 4,
                          'type': None,
                          'timestamp_delivery': None,
                          'timestamp_pickup': None,
                          'courier_firm': None,
                          'signature_delivery': None,
                          'signature_pickup': None,
                          'parcelbox_rebus_id': None,
                          'user_id_delivery': user_delivery_dto.id,
                          'user_id_pickup': user_pickup_dto.id})
        
        # with timestamps
        dto = DeliveryDTO(id=4, timestamp_delivery='2020-10-07T15:28:19+02:00', timestamp_pickup='2020-10-07T15:28:42+02:00')
        user_delivery_dto = UserDTO(id=4, username='test', first_name='first', last_name='last', role='ADMIN')
        user_pickup_dto = UserDTO(id=5, username='test', first_name='first', last_name='last', role='ADMIN')
        dto.user_delivery = user_delivery_dto
        dto.user_pickup = user_pickup_dto
        data = DeliverySerializer.serialize(dto)
        self.assertEqual({'id', 'user_delivery', 'user_pickup', 'timestamp_delivery', 'timestamp_pickup'}, set(dto.loaded_fields))
        self.assertEqual(data,
                         {'id': 4,
                          'type': None,
                          'timestamp_delivery': '2020-10-07T15:28:19+02:00',
                          'timestamp_pickup': '2020-10-07T15:28:42+02:00',
                          'courier_firm': None,
                          'signature_delivery': None,
                          'signature_pickup': None,
                          'parcelbox_rebus_id': None,
                          'user_id_delivery': user_delivery_dto.id,
                          'user_id_pickup': user_pickup_dto.id})


    def test_deserialize(self):
        # only type and courier_firm
        serial = {
            'type': 'DELIVERY',
            'courier_firm': 'TEST',
        }
        with self.assertRaises(ValueError):
            dto = DeliverySerializer.deserialize(serial)

        # with one user
        serial = {
            'type': 'DELIVERY',
            'courier_firm': 'TEST',
            'parcelbox_rebus_id': 37,
            'user_id_pickup': 5
        }
        user_dto_to_return = UserDTO(id=5, username='testuser')
        with mock.patch.object(self.user_controller, 'load_user', return_value=user_dto_to_return) as load_user_func, \
                mock.patch.object(self.user_controller, 'user_id_exists', return_value=True) as user_exists_func:
            dto = DeliverySerializer.deserialize(serial)
            user_exists_func.assert_called_once_with(5)
            load_user_func.assert_called_once_with(5)
            # set first name afterwards to not set the username
            expected = DeliveryDTO(type=serial['type'], courier_firm=serial['courier_firm'], user_pickup=user_dto_to_return, parcelbox_rebus_id=37)
            self.assertEqual(expected, dto)

        # with users
        serial = {
            'type': 'DELIVERY',
            'courier_firm': 'TEST',
            'parcelbox_rebus_id': 37,
            'user_id_delivery': 5,
            'user_id_pickup': 6
        }
        user_dto_to_return = UserDTO(id=5, username='testuser')
        user_pickup_dto_to_return = UserDTO(id=6, username='testuser')
        with mock.patch.object(self.user_controller, 'load_user') as load_user_func, \
                mock.patch.object(self.user_controller, 'user_id_exists') as user_exists_func:
            user_exists_func.side_effect = [True, True]
            load_user_func.side_effect = [user_dto_to_return, user_pickup_dto_to_return]
            dto = DeliverySerializer.deserialize(serial)
            user_exists_func.assert_has_calls([mock.call(5), mock.call(6)], any_order=False)
            load_user_func.assert_has_calls([mock.call(5), mock.call(6)], any_order=False)
            # set first name afterwards to not set the username
            expected = DeliveryDTO(type=serial['type'], courier_firm=serial['courier_firm'],
                                   user_delivery=user_dto_to_return, user_pickup=user_pickup_dto_to_return,
                                   parcelbox_rebus_id=37)
            self.assertEqual(expected, dto)
            
        # with timestamps
        serial = {
            'type': 'DELIVERY',
            'courier_firm': 'TEST',
            'user_id_delivery': 5,
            'user_id_pickup': 6,
            'timestamp_delivery': '2020-10-07T15:28:19+02:00',
            'timestamp_pickup': '2020-10-07T15:28:42+02:00',
            'parcelbox_rebus_id': 37,
        }
        user_dto_to_return = UserDTO(id=5, username='testuser')
        user_pickup_dto_to_return = UserDTO(id=6, username='testuser')
        with mock.patch.object(self.user_controller, 'load_user') as load_user_func, \
                mock.patch.object(self.user_controller, 'user_id_exists') as user_exists_func:
            user_exists_func.side_effect = [True, True]
            load_user_func.side_effect = [user_dto_to_return, user_pickup_dto_to_return]
            dto = DeliverySerializer.deserialize(serial)
            user_exists_func.assert_has_calls([mock.call(5), mock.call(6)], any_order=False)
            load_user_func.assert_has_calls([mock.call(5), mock.call(6)], any_order=False)
            # set first name afterwards to not set the username
            expected = DeliveryDTO(type=serial['type'], courier_firm=serial['courier_firm'],
                                   user_delivery=user_dto_to_return, user_pickup=user_pickup_dto_to_return,
                                   timestamp_delivery='2020-10-07T15:28:19+02:00', timestamp_pickup='2020-10-07T15:28:42+02:00',
                                   parcelbox_rebus_id=37)
            self.assertEqual(expected, dto)
