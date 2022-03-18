# Copyright (C) 2020 OpenMotics BV
#
# This program is free software, you can redistribute it and/or modify
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
Tests for the types module
"""

from __future__ import absolute_import

import unittest

from mock import Mock

from gateway.models import NoResultFound
from ioc import SetTestMode
from logs import Logs
from master.core.basic_action import BasicAction  # Must be imported
from master.core.memory_file import MemoryFile, MemoryTypes
from master.core.memory_types import *
from mocked_core_helper import MockedCore

logger = logging.getLogger(__name__)


class MemoryTypesTest(unittest.TestCase):
    """ Tests for types """

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        Logs.setup_logger(log_level_override=logging.DEBUG)

    def setUp(self):
        self.mocked_core = MockedCore(memory_is_cache=True)
        self.memory = self.mocked_core.memory[MemoryTypes.EEPROM]

    def test_memory_field_addressing(self):
        for item in [[(0, 0), 0, TypeError],
                     [(0, 1), None, (0, 1)],
                     [lambda id: (id, 0), 1, (1, 0)],
                     [lambda id: (id, 0), None, TypeError],
                     [lambda id: (id, id), 2, (2, 2)]]:
            spec, object_id, expected_address = item
            field = MemoryField(MemoryTypes.EEPROM, address_spec=spec, length=1)
            if expected_address == TypeError:
                with self.assertRaises(expected_address):
                    field.get_address(object_id)
                continue
            self.assertEqual(MemoryAddress(MemoryTypes.EEPROM, expected_address[0], expected_address[1], 1), field.get_address(object_id))

    def test_string_field(self):
        self._test_field(MemoryStringField, [[{'length': 1}, 'a', bytearray([97])],
                                             [{'length': 1}, 'ab', ValueError],
                                             [{'length': 3}, 'abc', bytearray([97, 98, 99])]])

    def test_byte_field(self):
        self._test_field(MemoryByteField, [[{}, -1, ValueError],
                                           [{}, 0, bytearray([0])],
                                           [{}, 20, bytearray([20])],
                                           [{}, 2 ** 8 - 1, bytearray([255])],
                                           [{}, 2 ** 8, ValueError]])

    def test_word_field(self):
        self._test_field(MemoryWordField, [[{}, -1, ValueError],
                                           [{}, 0, bytearray([0, 0])],
                                           [{}, 2 ** 8, bytearray([1, 0])],
                                           [{}, 2 ** 16 - 1, bytearray([255, 255])],
                                           [{}, 2 ** 16, ValueError]])

    def test_3bytes_field(self):
        self._test_field(Memory3BytesField, [[{}, -1, ValueError],
                                             [{}, 0, bytearray([0, 0, 0])],
                                             [{}, 2 ** 8, bytearray([0, 1, 0])],
                                             [{}, 2 ** 16 - 1, bytearray([0, 255, 255])],
                                             [{}, 2 ** 16, bytearray([1, 0, 0])],
                                             [{}, 2 ** 24 - 1, bytearray([255, 255, 255])],
                                             [{}, 2 ** 24, ValueError]])

    def test_bytearray_field(self):
        self._test_field(MemoryByteArrayField, [[{'length': 1}, [], ValueError],
                                                [{'length': 1}, [-1], ValueError],
                                                [{'length': 1}, [0], bytearray([0])],
                                                [{'length': 2}, [0], ValueError],
                                                [{'length': 2}, [0, 0, 0], ValueError],
                                                [{'length': 2}, [10, 0], bytearray([10, 0])],
                                                [{'length': 2}, [10, 265], ValueError]])

    def test_memoryarray_field(self):
        self._test_field(MemoryWordArrayField, [[{'length': 1}, [], ValueError],
                                                [{'length': 1}, [-1], ValueError],
                                                [{'length': 1}, [0], bytearray([0, 0])],
                                                [{'length': 2}, [0], ValueError],
                                                [{'length': 2}, [0, 0], bytearray([0, 0, 0, 0])],
                                                [{'length': 2}, [2 ** 8, 2 ** 16 - 1], bytearray([1, 0, 255, 255])],
                                                [{'length': 2}, [2 ** 8, 2 ** 16], ValueError]])

    def test_basicaction_field(self):
        self._test_field(MemoryBasicActionField, [[{}, BasicAction(10, 10, 0, 0), bytearray([10, 10, 0, 0, 0, 0])],
                                                  [{}, BasicAction(10, 20, 256, 256), bytearray([10, 20, 1, 0, 1, 0])]])

    def test_address_field(self):
        self._test_field(MemoryAddressField, [[{}, '0', ValueError],
                                              [{}, '0.0.0.0', bytearray([0, 0, 0, 0]), '000.000.000.000'],
                                              [{}, '1.2.3.4', bytearray([1, 2, 3, 4]), '001.002.003.004']])

    def test_version_field(self):
        self._test_field(MemoryVersionField, [[{}, '0', ValueError],
                                              [{}, '0.0.0', bytearray([0, 0, 0])],
                                              [{}, '1.2.3', bytearray([1, 2, 3])]])

    def test_temperature_field(self):
        self._test_field(MemoryTemperatureField, [[{}, -32.5, ValueError],
                                                  [{}, -32, bytearray([0])],
                                                  [{}, 0, bytearray([64])],
                                                  [{}, 95, bytearray([254])],
                                                  [{}, 95.5, ValueError],
                                                  [{}, None, bytearray([255])],
                                                  [{'limits': (-15, 15)}, -15.5, ValueError],
                                                  [{'limits': (-15, 15)}, -15, bytearray([34])],
                                                  [{'limits': (-15, 15)}, 0, bytearray([64])],
                                                  [{'limits': (-15, 15)}, 15, bytearray([94])],
                                                  [{'limits': (-15, 15)}, 15.5, ValueError]])

    def test_boolean_field(self):
        self._test_field(MemoryBooleanField, [[{'true_value': 0, 'false_value': 255, 'fallback': True}, 0, ValueError],
                                              [{'true_value': 0, 'false_value': 255, 'fallback': True}, 'foo', ValueError],
                                              [{'true_value': 0, 'false_value': 255, 'fallback': True}, True, bytearray([0])],
                                              [{'true_value': 0, 'false_value': 255, 'fallback': True}, False, bytearray([255])]])

    def _test_field(self, field_type, scenario):
        for item in scenario:
            if len(item) == 3:
                kwargs, value, expected_bytes = item
                expected_value = value
            else:
                kwargs, value, expected_bytes, expected_value = item
            field = field_type(memory_type=MemoryTypes.EEPROM,
                               address_spec=(None, None),
                               **kwargs)
            if expected_bytes == ValueError:
                with self.assertRaises(expected_bytes):
                    field.encode(value, None)
                continue
            result_bytes = field.encode(value, None)
            self.assertEqual(expected_bytes, result_bytes)
            result_value = field.decode(result_bytes)
            self.assertEqual(expected_value, result_value)

    def test_memory_field_container(self):
        address = MemoryAddress(MemoryTypes.EEPROM, 0, 1, 1)
        memory_file_mock = Mock(MemoryFile)
        memory_file_mock.read.return_value = {address: bytearray([1])}
        container = MemoryFieldContainer(name='field',
                                         memory_field=MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 1)),
                                         memory_address=address,
                                         memory_file=memory_file_mock,
                                         read_through=False)
        data = container.decode()
        self.assertEqual(1, data)
        memory_file_mock.read.assert_called_with([address], False)
        container.encode(2)
        data = container.decode()
        self.assertEqual(2, data)
        container.save()
        memory_file_mock.write.assert_called_with({address: bytearray([2])})

    def test_model_definition(self):
        self.memory[0] = bytearray([30, 31, 32])
        self.memory[1] = bytearray([40, 0b00010101])  # _x_xxxxx
        self.memory[2] = bytearray([41, 0b00001011])  # x__xxxxx
        self.memory[3] = bytearray([42, 0b00111000])  # __xxxxxx
        self.memory[4] = bytearray([43, 0b00000000])  # _x_xxxxx

        class Parent(MemoryModelDefinition):
            info = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, id))

        class Child(MemoryModelDefinition):
            class _ChildComposed(CompositeMemoryModelDefinition):
                info = CompositeNumberField(start_bit=0, width=3, value_offset=2)
                bit = CompositeBitField(bit=3)
                bit_inverted = CompositeBitField(bit=4, inverted=True)
                moved = CompositeBitField(bit=lambda id: 5 + id % 3)

            parent = MemoryRelation(Parent, id_spec=lambda id: id // 2)
            info = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (id, 0))
            composed = _ChildComposed(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (id, 1)))

        parent_0 = {'id': 0, 'info': 30}
        parent_1 = {'id': 1, 'info': 31}
        parent_2 = {'id': 2, 'info': 32}
        for entry in [[1, {'id': 1, 'info': 40, 'composed': {'bit': False, 'bit_inverted': False, 'info': 3, 'moved': False}}, parent_0],
                      [2, {'id': 2, 'info': 41, 'composed': {'bit': True, 'bit_inverted': True, 'info': 1, 'moved': False}}, parent_1],
                      [3, {'id': 3, 'info': 42, 'composed': {'bit': True, 'bit_inverted': False, 'info': -2, 'moved': True}}, parent_1],
                      [4, {'id': 4, 'info': 43, 'composed': {'bit': False, 'bit_inverted': True, 'info': -2, 'moved': False}}, parent_2]]:
            child_id, child_data, parent_data = entry
            child = Child(child_id)
            self.assertEqual(child_data, child.serialize())
            self.assertEqual(parent_data, child.parent.serialize())
            self.assertEqual(child_data['info'], child.info)
            self.assertEqual(child_data['composed']['bit'], child.composed.bit)
            self.assertEqual(child_data['composed']['info'], child.composed.info)
            self.assertEqual(child_data['composed']['moved'], child.composed.moved)

        parent = Parent(0)
        with self.assertRaises(ValueError):
            Child.deserialize({'id': 1,
                               'foo': 2})
        child = Child.deserialize({'id': 4,
                                   'info': 10,
                                   'composed': {'bit': True,
                                                'bit_inverted': True,
                                                'moved': True},
                                   'parent': {'id': 0,
                                              'info': 5}})
        self.assertEqual({'id': 4,
                          'info': 10,
                          'composed': {'bit': True,
                                       'bit_inverted': True,
                                       'info': -2,
                                       'moved': True}}, child.serialize())
        self.assertEqual({'id': 0,
                          'info': 5}, child.parent.serialize())
        with self.assertRaises(ValueError):
            child.info = 256
        child.info = 20
        with self.assertRaises(AttributeError):
            child.parent = parent
        child.save()
        self.assertEqual(bytearray([20, 0b01001000]), self.memory[4])  # _x_xxxxx
        child.composed.bit = False
        child.composed.bit_inverted = False
        child.composed.info = 4
        child.composed.moved = False
        self.assertEqual({'id': 4,
                          'info': 20,
                          'composed': {'bit': False,
                                       'bit_inverted': False,
                                       'info': 4,
                                       'moved': False}}, child.serialize())
        child.save()
        self.assertEqual(bytearray([20, 0b00010110]), self.memory[4])  # _x_xxxxx

    def test_fk_relation(self):
        self.memory[0] = bytearray([10])
        self.memory[1] = bytearray([0, 20])
        self.memory[2] = bytearray([1, 30])

        class FKParent(MemoryModelDefinition):
            info = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, id))

        class FKChild(MemoryModelDefinition):
            parent = MemoryRelation(FKParent,
                                    field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (id + 1, 0)),
                                    id_spec=lambda id: None if id == 0 else id - 1)
            info = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (id + 1, 1))

        child_0 = FKChild(0)
        self.assertEqual(20, child_0.info)
        self.assertIsNone(child_0.parent)
        child_1 = FKChild(1)
        self.assertEqual(30, child_1.info)
        self.assertIsNotNone(child_1.parent)
        self.assertEqual(10, child_1.parent.info)

    def test_factor_composition(self):
        self.memory[0] = bytearray([0])

        class Object(MemoryModelDefinition):
            class _ObjectComposed(CompositeMemoryModelDefinition):
                field_0 = CompositeNumberField(start_bit=0, width=8, value_factor=2)
                field_1 = CompositeNumberField(start_bit=0, width=8, value_offset=-1, value_factor=2)

            composed = _ObjectComposed(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (id, 0)))

        instance = Object(0)
        self.assertEqual(0, instance.composed.field_0)
        self.assertEqual(1, instance.composed.field_1)

        instance.composed.field_0 = 14
        self.assertEqual(15, instance.composed.field_1)
        instance.save()
        self.assertEqual(7, self.memory[0][0])

        self.memory[0][0] = 100
        instance = Object(0)
        self.assertEqual(200, instance.composed.field_0)
        self.assertEqual(201, instance.composed.field_1)

        self.memory[0][0] = 255
        instance = Object(0)
        self.assertEqual(510, instance.composed.field_0)
        self.assertEqual(511, instance.composed.field_1)

    def test_enums(self):
        self.memory[0] = bytearray([0])

        class Object2(MemoryModelDefinition):
            class SomeType(MemoryEnumDefinition):
                FOO = EnumEntry('FOO', values=[0, 255], default=True)
                BAR = EnumEntry('BAR', values=[1])

            enum = SomeType(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (id, 0)))

        instance = Object2(0)
        self.assertEqual(Object2.SomeType.FOO, instance.enum)
        self.assertEqual(instance.SomeType.FOO, instance.enum)

        instance.enum = Object2.SomeType.BAR
        self.assertEqual(Object2.SomeType.BAR, instance.enum)
        self.assertEqual(0, self.memory[0][0])
        instance.save()
        self.assertEqual(1, self.memory[0][0])

        instance.enum = 'FOO'  # It is allowed to directly use the string representation
        self.assertEqual(Object2.SomeType.FOO, instance.enum)
        self.assertEqual(1, self.memory[0][0])
        instance.save()
        self.assertEqual(0, self.memory[0][0])

        self.memory[0][0] = 255
        instance = Object2(0)
        self.assertEqual(Object2.SomeType.FOO, instance.enum)

        self.memory[0][0] = 123
        instance = Object2(0)
        self.assertEqual(Object2.SomeType.FOO, instance.enum)

        class Object3(MemoryModelDefinition):
            class SomeType(MemoryEnumDefinition):
                FOO = EnumEntry('FOO', values=[0, 255])
                BAR = EnumEntry('BAR', values=[1])

            enum = SomeType(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (id, 0)))

        instance = Object3(0)
        with self.assertRaises(ValueError):
            _ = instance.enum

        with self.assertRaises(ValueError):
            instance.enum = EnumEntry('FOO_', values=[12])

        with self.assertRaises(ValueError):
            instance.enum = 'BAR_'

    def test_readonly(self):
        self.memory[0] = bytearray([0, 0])

        class RObject(MemoryModelDefinition):
            rw = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, 0))
            ro = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, 1), read_only=True)

        instance = RObject(0)
        instance.rw = 1
        instance.save()
        self.assertEqual(1, self.memory[0][0])
        with self.assertRaises(AttributeError):
            instance.ro = 2
        instance.save()
        self.assertEqual(0, self.memory[0][1])

    def test_model_ids(self):
        self.memory[0] = bytearray([2])

        with self.assertRaises(ValueError):
            class InvalidFixedLimitObject(MemoryModelDefinition):
                id = IdField(limits=(0, 2),
                             field=MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 0)))

        with self.assertRaises(ValueError):
            class InvalidFieldLimitObject(MemoryModelDefinition):
                id = IdField(limits=lambda f: (0, f - 1))

        class FixedLimitObject(MemoryModelDefinition):
            id = IdField(limits=(0, 2))

        class FieldLimitObject(MemoryModelDefinition):
            id = IdField(limits=lambda f: (0, f - 1), field=MemoryByteField(MemoryTypes.EEPROM, address_spec=(0, 0)))

        for invalid_id in [None, -1, 3]:
            with self.assertRaises(RuntimeError if invalid_id is None else NoResultFound):
                _ = FixedLimitObject(invalid_id)
        for valid_id in [0, 1, 2]:
            self.assertEqual(valid_id, FixedLimitObject(valid_id).id)

        for invalid_id in [None, -1, 2]:
            with self.assertRaises(RuntimeError if invalid_id is None else NoResultFound):
                _ = FieldLimitObject(invalid_id)
        for valid_id in [0, 1]:
            self.assertEqual(valid_id, FieldLimitObject(valid_id).id)

    def test_checksums(self):
        self.memory[0] = bytearray([255, 255, 255, 255, 255])

        class CheckedObject(MemoryModelDefinition):
            class CheckedEnum(MemoryEnumDefinition):
                FOO = EnumEntry('FOO', values=[0, 255])
                BAR = EnumEntry('BAR', values=[1])

            checked_field = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, 0),
                                            checksum=MemoryChecksum(field=MemoryByteField(memory_type=MemoryTypes.EEPROM,
                                                                                          address_spec=lambda id: (0, 1)),
                                                                    check=MemoryChecksum.Types.INVERTED))
            checked_enum_field = CheckedEnum(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, 3)),
                                             checksum=MemoryChecksum(field=MemoryByteField(memory_type=MemoryTypes.EEPROM,
                                                                                           address_spec=lambda id: (0, 4)),
                                                                     check=MemoryChecksum.Types.INVERTED))
        instance = CheckedObject(0)
        # Checksum does not fail since it's not initialized
        self.assertEqual(255, instance.checked_field)
        self.assertEqual('FOO', instance.checked_enum_field)
        # Set fields and thus checksums
        instance.checked_field = 10
        instance.checked_enum_field = 'BAR'
        instance.save()
        self.assertEqual(bytearray([10, 245, 255, 1, 254]), self.memory[0])

        self.memory[0][1] = 123
        self.memory[0][3] = 123
        instance = CheckedObject(0)
        with self.assertRaises(InvalidMemoryChecksum):
            _ = instance.checked_field
        with self.assertRaises(InvalidMemoryChecksum):
            _ = instance.checked_enum_field
        instance.checked_field = 20
        instance.checked_enum_field = 'FOO'
        instance.save()
        self.assertEqual(bytearray([20, 235, 255, 0, 255]), self.memory[0])
