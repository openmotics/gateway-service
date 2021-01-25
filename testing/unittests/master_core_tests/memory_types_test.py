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
import xmlrunner
from peewee import DoesNotExist
from mock import Mock
from ioc import SetTestMode, SetUpTestInjections
from master.core.basic_action import BasicAction  # Must be imported
from master.core.memory_types import *
from master.core.memory_file import MemoryTypes, MemoryFile
from logs import Logs

logger = logging.getLogger('openmotics')


class MemoryTypesTest(unittest.TestCase):
    """ Tests for types """

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        Logs.setup_logger(log_level=logging.DEBUG)

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
        self._test_field(MemoryStringField, [[[1], 'a', bytearray([97])],
                                             [[1], 'ab', ValueError],
                                             [[3], 'abc', bytearray([97, 98, 99])]])

    def test_byte_field(self):
        self._test_field(MemoryByteField, [[[], -1, ValueError],
                                           [[], 0, bytearray([0])],
                                           [[], 20, bytearray([20])],
                                           [[], 2 ** 8 - 1, bytearray([255])],
                                           [[], 2 ** 8, ValueError]])

    def test_word_field(self):
        self._test_field(MemoryWordField, [[[], -1, ValueError],
                                           [[], 0, bytearray([0, 0])],
                                           [[], 2 ** 8, bytearray([1, 0])],
                                           [[], 2 ** 16 - 1, bytearray([255, 255])],
                                           [[], 2 ** 16, ValueError]])

    def test_3bytes_field(self):
        self._test_field(Memory3BytesField, [[[], -1, ValueError],
                                             [[], 0, bytearray([0, 0, 0])],
                                             [[], 2 ** 8, bytearray([0, 1, 0])],
                                             [[], 2 ** 16 - 1, bytearray([0, 255, 255])],
                                             [[], 2 ** 16, bytearray([1, 0, 0])],
                                             [[], 2 ** 24 - 1, bytearray([255, 255, 255])],
                                             [[], 2 ** 24, ValueError]])

    def test_bytearray_field(self):
        self._test_field(MemoryByteArrayField, [[[1], [], ValueError],
                                                [[1], [-1], ValueError],
                                                [[1], [0], bytearray([0])],
                                                [[2], [0], ValueError],
                                                [[2], [0, 0, 0], ValueError],
                                                [[2], [10, 0], bytearray([10, 0])],
                                                [[2], [10, 265], ValueError]])

    def test_memoryarray_field(self):
        self._test_field(MemoryWordArrayField, [[[1], [], ValueError],
                                                [[1], [-1], ValueError],
                                                [[1], [0], bytearray([0, 0])],
                                                [[2], [0], ValueError],
                                                [[2], [0, 0], bytearray([0, 0, 0, 0])],
                                                [[2], [2 ** 8, 2 ** 16 - 1], bytearray([1, 0, 255, 255])],
                                                [[2], [2 ** 8, 2 ** 16], ValueError]])

    def test_basicaction_field(self):
        self._test_field(MemoryBasicActionField, [[[], BasicAction(10, 10, 0, 0), bytearray([10, 10, 0, 0, 0, 0])],
                                                  [[], BasicAction(10, 20, 256, 256), bytearray([10, 20, 1, 0, 1, 0])]])

    def test_address_field(self):
        self._test_field(MemoryAddressField, [[[], '0', ValueError],
                                              [[], '0.0.0.0', bytearray([0, 0, 0, 0]), '000.000.000.000'],
                                              [[], '1.2.3.4', bytearray([1, 2, 3, 4]), '001.002.003.004']])

    def test_version_field(self):
        self._test_field(MemoryVersionField, [[[], '0', ValueError],
                                              [[], '0.0.0', bytearray([0, 0, 0])],
                                              [[], '1.2.3', bytearray([1, 2, 3])]])

    def _test_field(self, field_type, scenario):
        for item in scenario:
            if len(item) == 3:
                args, value, expected_bytes = item
                expected_value = value
            else:
                args, value, expected_bytes, expected_value = item
            field = field_type(MemoryTypes.EEPROM, (None, None), *args)
            if expected_bytes == ValueError:
                with self.assertRaises(expected_bytes):
                    field.encode(value)
                continue
            result_bytes = field.encode(value)
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
                                         memory_files={MemoryTypes.EEPROM: memory_file_mock})
        data = container.decode()
        self.assertEqual(1, data)
        memory_file_mock.read.assert_called_with([address])
        container.encode(2)
        data = container.decode()
        self.assertEqual(2, data)
        container.save()
        memory_file_mock.write.assert_called_with({address: bytearray([2])})

    def test_model_definition(self):
        memory_map = {0: bytearray([30, 31, 32]),
                      1: bytearray([40, 0b0101]),
                      2: bytearray([41, 0b1011]),
                      3: bytearray([42, 0b1000]),
                      4: bytearray([43, 0b0000])}
        MemoryTypesTest._mock_memory(memory_map)

        class Parent(MemoryModelDefinition):
            info = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, id))

        class Child(MemoryModelDefinition):
            class _ChildComposed(CompositeMemoryModelDefinition):
                info = CompositeNumberField(start_bit=0, width=3, value_offset=2)
                bit = CompositeBitField(bit=3)

            parent = MemoryRelation(Parent, id_spec=lambda id: id // 2)
            info = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (id, 0))
            composed = _ChildComposed(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (id, 1)))

        parent_0 = {'id': 0, 'info': 30}
        parent_1 = {'id': 1, 'info': 31}
        parent_2 = {'id': 2, 'info': 32}
        for entry in [[1, {'id': 1, 'info': 40, 'composed': {'bit': False, 'info': 3}}, parent_0],
                      [2, {'id': 2, 'info': 41, 'composed': {'bit': True, 'info': 1}}, parent_1],
                      [3, {'id': 3, 'info': 42, 'composed': {'bit': True, 'info': -2}}, parent_1],
                      [4, {'id': 4, 'info': 43, 'composed': {'bit': False, 'info': -2}}, parent_2]]:
            child_id, child_data, parent_data = entry
            child = Child(child_id)
            self.assertEqual(child_data, child.serialize())
            self.assertEqual(parent_data, child.parent.serialize())
            self.assertEqual(child_data['info'], child.info)
            self.assertEqual(child_data['composed']['bit'], child.composed.bit)
            self.assertEqual(child_data['composed']['info'], child.composed.info)

        parent = Parent(0)
        with self.assertRaises(ValueError):
            child.deserialize({'id': 1,
                               'foo': 2})
        child = Child.deserialize({'id': 4,
                                   'info': 10,
                                   'composed': {'bit': True},
                                   'parent': {'id': 0,
                                              'info': 5}})
        self.assertEqual({'id': 4,
                          'info': 10,
                          'composed': {'bit': True,
                                       'info': -2}}, child.serialize())
        self.assertEqual({'id': 0,
                          'info': 5}, child.parent.serialize())
        with self.assertRaises(ValueError):
            child.info = 256
        child.info = 20
        with self.assertRaises(AttributeError):
            child.parent = parent
        child.save()
        self.assertEqual(bytearray([20, 0b1000]), memory_map[4])
        child.composed.bit = False
        child.composed.info = 4
        self.assertEqual({'id': 4,
                          'info': 20,
                          'composed': {'bit': False,
                                       'info': 4}}, child.serialize())
        child.save()
        self.assertEqual(bytearray([20, 0b0110]), memory_map[4])

    def test_fk_relation(self):
        memory_map = {0: bytearray([10]),
                      1: bytearray([0, 20]),
                      2: bytearray([1, 30])}
        MemoryTypesTest._mock_memory(memory_map)

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
        memory_map = {0: bytearray([0])}
        MemoryTypesTest._mock_memory(memory_map)

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
        self.assertEqual(7, memory_map[0][0])

        memory_map[0][0] = 100
        instance = Object(0)
        self.assertEqual(200, instance.composed.field_0)
        self.assertEqual(201, instance.composed.field_1)

        memory_map[0][0] = 255
        instance = Object(0)
        self.assertEqual(510, instance.composed.field_0)
        self.assertEqual(511, instance.composed.field_1)

    def test_enums(self):
        memory_map = {0: bytearray([0])}
        MemoryTypesTest._mock_memory(memory_map)

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
        self.assertEqual(0, memory_map[0][0])
        instance.save()
        self.assertEqual(1, memory_map[0][0])

        instance.enum = 'FOO'  # It is allowed to directly use the string representation
        self.assertEqual(Object2.SomeType.FOO, instance.enum)
        self.assertEqual(1, memory_map[0][0])
        instance.save()
        self.assertEqual(0, memory_map[0][0])

        memory_map[0][0] = 255
        instance = Object2(0)
        self.assertEqual(Object2.SomeType.FOO, instance.enum)

        memory_map[0][0] = 123
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
        memory_map = {0: bytearray([0, 0])}
        MemoryTypesTest._mock_memory(memory_map)

        class RObject(MemoryModelDefinition):
            rw = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, 0))
            ro = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, 1), read_only=True)

        instance = RObject(0)
        instance.rw = 1
        instance.save()
        self.assertEqual(1, memory_map[0][0])
        with self.assertRaises(AttributeError):
            instance.ro = 2
        instance.save()
        self.assertEqual(0, memory_map[0][1])

    def test_model_ids(self):
        memory_map = {0: bytearray([2])}
        MemoryTypesTest._mock_memory(memory_map)

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
            with self.assertRaises(RuntimeError if invalid_id is None else DoesNotExist):
                _ = FixedLimitObject(invalid_id)
        for valid_id in [0, 1, 2]:
            self.assertEqual(valid_id, FixedLimitObject(valid_id).id)

        for invalid_id in [None, -1, 2]:
            with self.assertRaises(RuntimeError if invalid_id is None else DoesNotExist):
                _ = FieldLimitObject(invalid_id)
        for valid_id in [0, 1]:
            self.assertEqual(valid_id, FieldLimitObject(valid_id).id)

    def test_checksums(self):
        memory_map = {0: bytearray([255, 255, 255, 255])}
        MemoryTypesTest._mock_memory(memory_map)

        class CheckedObject(MemoryModelDefinition):
            class CheckedEnum(MemoryEnumDefinition):
                FOO = EnumEntry('FOO', values=[0, 255])
                BAR = EnumEntry('BAR', values=[1])

            checked_field = MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, 0),
                                            checksum=MemoryChecksum(field=MemoryByteField(memory_type=MemoryTypes.EEPROM,
                                                                                          address_spec=lambda id: (0, 1)),
                                                                    check=MemoryChecksum.Types.INVERTED))
            checked_enum_field = CheckedEnum(field=MemoryByteField(MemoryTypes.EEPROM, address_spec=lambda id: (0, 2)),
                                             checksum=MemoryChecksum(field=MemoryByteField(memory_type=MemoryTypes.EEPROM,
                                                                                           address_spec=lambda id: (0, 3)),
                                                                     check=MemoryChecksum.Types.INVERTED))
        instance = CheckedObject(0)
        # Checksum does not fail since it's not initialized
        self.assertEqual(255, instance.checked_field)
        self.assertEqual('FOO', instance.checked_enum_field)
        # Set fields and thus checksums
        instance.checked_field = 10
        instance.checked_enum_field = 'BAR'
        instance.save()
        self.assertEqual(bytearray([10, 245, 1, 254]), memory_map[0])

        memory_map[0][1] = 123
        memory_map[0][3] = 123
        instance = CheckedObject(0)
        with self.assertRaises(InvalidMemoryChecksum):
            _ = instance.checked_field
        with self.assertRaises(InvalidMemoryChecksum):
            _ = instance.checked_enum_field
        instance.checked_field = 20
        instance.checked_enum_field = 'FOO'
        instance.save()
        self.assertEqual(bytearray([20, 235, 0, 255]), memory_map[0])

    @staticmethod
    def _mock_memory(memory_map):
        def _read(addresses):
            data_ = {}
            for address in addresses:
                data_[address] = memory_map[address.page][address.offset:address.offset + address.length]
            return data_

        def _write(data_map):
            for address, data_ in data_map.items():
                for index, data_byte in enumerate(data_):
                    memory_map[address.page][address.offset + index] = data_byte

        memory_file_mock = Mock(MemoryFile)
        memory_file_mock.read = _read
        memory_file_mock.write = _write

        SetUpTestInjections(memory_files={MemoryTypes.EEPROM: memory_file_mock})


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
