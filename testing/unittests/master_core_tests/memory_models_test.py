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
Tests for the models
"""

from __future__ import absolute_import
import unittest
import xmlrunner
import logging
from mock import Mock
from ioc import SetTestMode, SetUpTestInjections
from master.core.memory_models import *
from master.core.memory_file import MemoryTypes, MemoryFile, MemoryAddress

logger = logging.getLogger('openmotics')


class MemoryModelsTest(unittest.TestCase):
    """
    Steps to extend this test whenever a new model is added to master/core/memory_models.py (wherever applicable):
    * Add the maximum amount of modules to the constants
    * Register the maximum amount in the `setUp` method
    * Add the new models to the `TEST_MATRIX` constant
    * Add certain fields to the `ALLOW_OVERLAP` constant (e.g. `device_type` is part of `address`)
    """

    AMOUNT_OF_OUTPUT_MODULES = 80
    AMOUNT_OF_OUTPUTS = AMOUNT_OF_OUTPUT_MODULES * 8
    AMOUNT_OF_INPUT_MODULES = 79
    AMOUNT_OF_INPUTS = AMOUNT_OF_INPUT_MODULES * 8
    AMOUNT_OF_SENSOR_MODULES = 16
    AMOUNT_OF_SENSORS = AMOUNT_OF_SENSOR_MODULES * 8
    AMOUNT_OF_SHUTTERS = 256
    AMOUNT_OF_CAN_CONTROLS = 16
    AMOUNT_OF_UCANS = 128
    AMOUNT_OF_EXTRA_SENSORS = 64
    AMOUNT_OF_VALIDATION_BITS = 256
    AMOUNT_OF_GROUP_ACTIONS = 256
    AMOUNT_OF_GROUP_ACTION_BASIC_ACTIONS = 4200

    TEST_MATRIX = {'A': (GlobalConfiguration, None),
                   'I': (InputModuleConfiguration, AMOUNT_OF_INPUT_MODULES),
                   'i': (InputConfiguration, AMOUNT_OF_INPUTS),
                   'O': (OutputModuleConfiguration, AMOUNT_OF_OUTPUT_MODULES),
                   'o': (OutputConfiguration, AMOUNT_OF_OUTPUTS),
                   'S': (SensorModuleConfiguration, AMOUNT_OF_SENSOR_MODULES),
                   's': (SensorConfiguration, AMOUNT_OF_SENSORS),
                   'r': (ShutterConfiguration, AMOUNT_OF_SHUTTERS),
                   'C': (CanControlModuleConfiguration, AMOUNT_OF_CAN_CONTROLS),
                   'c': (UCanModuleConfiguration, AMOUNT_OF_UCANS),
                   'e': (ExtraSensorConfiguration, AMOUNT_OF_EXTRA_SENSORS),
                   'b': (ValidationBitConfiguration, AMOUNT_OF_VALIDATION_BITS),
                   'g': (GroupActionAddressConfiguration, AMOUNT_OF_GROUP_ACTIONS),
                   'G': (GroupActionConfiguration, AMOUNT_OF_GROUP_ACTIONS),
                   'B': (GroupActionBasicAction, AMOUNT_OF_GROUP_ACTION_BASIC_ACTIONS)}
    ALLOW_OVERLAP = [['I.address', 'I.device_type'],
                     ['O.address', 'O.device_type'],
                     ['S.address', 'S.device_type'],
                     ['C.address', 'C.device_type'],
                     ['c.address', 'c.device_type']]

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    def setUp(self):
        self._memory_access = {MemoryTypes.EEPROM: {}, MemoryTypes.FRAM: {}}
        self._memory_map = {MemoryTypes.EEPROM: {}, MemoryTypes.FRAM: {}}
        for memory_type in [MemoryTypes.EEPROM, MemoryTypes.FRAM]:
            for page in range(MemoryFile.SIZES[memory_type][0]):
                self._memory_map[memory_type][page] = bytearray([255] * MemoryFile.SIZES[memory_type][1])
        self._memory_map[MemoryTypes.EEPROM][0][1] = MemoryModelsTest.AMOUNT_OF_OUTPUT_MODULES
        self._memory_map[MemoryTypes.EEPROM][0][2] = MemoryModelsTest.AMOUNT_OF_INPUT_MODULES
        self._memory_map[MemoryTypes.EEPROM][0][3] = MemoryModelsTest.AMOUNT_OF_SENSOR_MODULES
        self._memory_map[MemoryTypes.EEPROM][0][7] = MemoryModelsTest.AMOUNT_OF_UCANS
        self._memory_map[MemoryTypes.EEPROM][0][9] = MemoryModelsTest.AMOUNT_OF_CAN_CONTROLS
        MemoryModelsTest._mock_memory(self._memory_map)

    def test_models(self):
        for code, specs in MemoryModelsTest.TEST_MATRIX.items():
            orm_type, amount = specs
            if amount is None:
                self._enumerate_instance(orm_type(), code)
            else:
                for i in range(amount):
                    self._enumerate_instance(orm_type(i), code)
        self._validate_and_report(print_overview=False)  # Set to `True` when debugging or when a visual overview is wanted

    def _enumerate_instance(self, instance, code):
        fields = instance._get_fields()
        if isinstance(instance, GlobalConfiguration):
            id = '{0}.{{0}}'.format(code)
        else:
            id = '{0}.{1}.{{0}}'.format(code, instance.id)
        for field_name, _ in fields['fields'] + fields['enums']:
            self._register_address(id.format(field_name), getattr(instance, '_{0}'.format(field_name))._memory_address)
        for field_name, _ in fields['relations']:
            container = getattr(instance, '_{0}'.format(field_name))._field_container
            if container is not None:
                self._register_address(id.format(field_name), container._memory_address)
        for field_name, _ in fields['compositions']:
            self._register_address(id.format(field_name), getattr(instance, '_{0}'.format(field_name))._field_container._memory_address)

    def _register_address(self, id, address):  # type: (str, MemoryAddress) -> None
        self.assertLess(address.page, 512, 'Page overflow: {0} > {1}'.format(id, address.page))
        page = self._memory_access[address.memory_type].setdefault(address.page, [[] for _ in range(256)])
        for i in range(address.offset, address.offset + address.length):
            self.assertLess(i, 256, 'Memory range overflow: {0} > {1}'.format(id, address))
            self.assertNotIn(id, page[i], 'Duplicate entry: {0} > {1}'.format(id, address))
            page[i].append(id)

    def _validate_and_report(self, print_overview=False):
        for memory_type, memory_type_name in {MemoryTypes.EEPROM: 'EEPROM',
                                              MemoryTypes.FRAM: 'FRAM'}.items():
            overview = {i: ['.'] * MemoryFile.SIZES[memory_type][1] for i in range(MemoryFile.SIZES[memory_type][0])}
            for page in self._memory_access[memory_type]:
                for byte, values in enumerate(self._memory_access[memory_type][page]):
                    fields = []
                    for entry in values:
                        entry_parts = entry.split('.')
                        fields.append('{0}.{1}'.format(entry_parts[0], entry_parts[-1]))
                        overview[page][byte] = entry[0]
                    if len(fields) > 1:
                        self.assertIn(sorted(fields), MemoryModelsTest.ALLOW_OVERLAP, 'Unexpected overlap: P{0} B{1}: {2}'.format(page, byte, values))
            if print_overview:
                print('{0}:'.format(memory_type_name))
                for page, values in overview.items():
                    print('  {0}: {1}'.format(page, ''.join(values)))
        if print_overview:
            print('Legend:')
            for code, specs in MemoryModelsTest.TEST_MATRIX.items():
                print('  {0}: {1}'.format(code, specs[0].__name__))

    @staticmethod
    def _mock_memory(memory_map):
        def _read(addresses):
            data_ = {}
            for address in addresses:
                data_[address] = memory_map[address.memory_type][address.page][address.offset:address.offset + address.length]
            return data_

        def _write(data_map):
            for address, data_ in data_map.items():
                for index, data_byte in enumerate(data_):
                    memory_map[address.memory_type][address.page][address.offset + index] = data_byte

        memory_file_mock = Mock(MemoryFile)
        memory_file_mock.read = _read
        memory_file_mock.write = _write

        SetUpTestInjections(memory_files={MemoryTypes.EEPROM: memory_file_mock,
                                          MemoryTypes.FRAM: memory_file_mock})


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
