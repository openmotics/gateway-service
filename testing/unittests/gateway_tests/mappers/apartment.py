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

import unittest
from gateway.dto import ApartmentDTO
from gateway.mappers import ApartmentMapper
from gateway.api.serializers.apartment import ApartmentSerializer


class ApartmentMapperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        pass


    def test_mapper(self):
        apartment_dict = {
            'id': 5,
            'name': 'Test_app',
            'mailbox_rebus_id': 5,
            'doorbell_rebus_id': 37
        }
        deserialized = ApartmentSerializer.deserialize(apartment_dict)
        expected = ApartmentDTO(
            id=5,
            name='Test_app',
            mailbox_rebus_id=5,
            doorbell_rebus_id=37
        )
        self.assertEqual(expected, deserialized)
        self.assertEqual(4, len(deserialized.loaded_fields))

        apartment_orm = ApartmentMapper.dto_to_orm(deserialized)
        apartment_dto = ApartmentMapper.orm_to_dto(apartment_orm)

        self.assertEqual(expected, apartment_dto)

        serialized = ApartmentSerializer.serialize(apartment_dto)

        self.assertEqual(apartment_dict, serialized)
