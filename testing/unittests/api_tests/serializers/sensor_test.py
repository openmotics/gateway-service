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
from gateway.dto import SensorDTO, SensorSourceDTO
from gateway.api.serializers import SensorSerializer


class SensorSerializerTest(unittest.TestCase):
    def test_serialize(self):
        # Valid room
        data = SensorSerializer.serialize(SensorDTO(id=1, name='foo', room=5),
                                          fields=['id', 'name', 'room'])
        self.assertEqual({'id': 1,
                          'name': 'foo',
                          'room': 5}, data)
        # Empty room
        data = SensorSerializer.serialize(SensorDTO(id=1, name='foo'),
                                          fields=['id', 'name', 'room'])
        self.assertEqual({'id': 1,
                          'name': 'foo',
                          'room': 255}, data)
        # No room
        data = SensorSerializer.serialize(SensorDTO(id=1, name='foo', room=5),
                                          fields=['id', 'name'])
        self.assertEqual({'id': 1,
                          'name': 'foo'}, data)

    def test_deserialize(self):
        # Valid room
        dto = SensorSerializer.deserialize({'id': 5,
                                            'external_id': '0',
                                            'source': {'type': 'master'},
                                            'physical_quantity': 'temperature',
                                            'unit': 'celcius',
                                            'name': 'bar',
                                            'room': 10})
        expected_dto = SensorDTO(id=5,
                                 external_id='0',
                                 source=SensorSourceDTO('master', name=None),
                                 physical_quantity='temperature',
                                 unit='celcius',
                                 name='bar',
                                 room=10)
        assert expected_dto == dto
        self.assertEqual(expected_dto, dto)
        self.assertEqual(['external_id', 'id', 'name', 'physical_quantity', 'room', 'source', 'unit'], sorted(dto.loaded_fields))
        # Empty room
        dto = SensorSerializer.deserialize({'id': 5,
                                            'name': 'bar',
                                            'room': 255})
        self.assertEqual(SensorDTO(id=5, name='bar'), dto)
        self.assertEqual(['id', 'name', 'room'], sorted(dto.loaded_fields))
        # No room
        dto = SensorSerializer.deserialize({'id': 5,
                                            'name': 'bar'})
        self.assertEqual(SensorDTO(id=5, name='bar'), dto)
        self.assertEqual(['id', 'name'], sorted(dto.loaded_fields))

        # Invalid physical_quantity
        with self.assertRaises(ValueError):
            _ = SensorSerializer.deserialize({'id': 5,
                                              'physical_quantity': 'something',
                                              'unit': 'celcius',
                                              'name': 'bar'})
        # Invalid unit
        with self.assertRaises(ValueError):
            _ = SensorSerializer.deserialize({'id': 5,
                                              'physical_quantity': 'temperature',
                                              'unit': 'unicorns',
                                              'name': 'bar'})
