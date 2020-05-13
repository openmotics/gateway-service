# Copyright (C) 2019 OpenMotics BV
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
Tests for GroupAction related actions
"""

from __future__ import absolute_import
import unittest
import xmlrunner
import logging
from mock import Mock
from ioc import SetTestMode, SetUpTestInjections
from master.core.basic_action import BasicAction
from master.core.group_action import GroupActionController
from master.core.memory_file import MemoryTypes, MemoryFile
from master.core.memory_types import MemoryWordField


class GroupActionTest(unittest.TestCase):
    """ Tests for MemoryFile """

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        logger = logging.getLogger('openmotics')
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    @staticmethod
    def _encode_string(value):
        data = []
        for char in value:
            data.append(ord(char))
        data.append(255)
        return data

    @staticmethod
    def _write(memory_page, start_address, data):
        for i in range(len(data)):
            memory_page[start_address + i] = data[i]

    @staticmethod
    def _setup_master_communicator(memory):
        def _do_command(api, payload):
            if api.instruction == 'MW':
                page = payload['page']
                start = payload['start']
                page_data = memory.setdefault(page, [255] * 256)
                for index, data_byte in enumerate(payload['data']):
                    page_data[start + index] = data_byte

        master_communicator = Mock()
        master_communicator.do_command = _do_command
        SetUpTestInjections(master_communicator=master_communicator)
        eeprom_file = MemoryFile(MemoryTypes.EEPROM)
        eeprom_file._cache = memory
        SetUpTestInjections(memory_files={MemoryTypes.EEPROM: eeprom_file,
                                          MemoryTypes.FRAM: MemoryFile(MemoryTypes.FRAM)})

    def test_list_group_actions(self):
        memory = {}
        for page in range(256, 381):
            memory[page] = [255] * 256
        GroupActionTest._setup_master_communicator(memory)

        group_actions = GroupActionController.load_group_actions()
        self.assertEqual(256, len(group_actions), 'There should be 256 GAs')
        for i in range(256):
            self.assertFalse(group_actions[i].in_use, 'GA {0} should not be in use'.format(i))

        # Set valid start address
        GroupActionTest._write(memory[256], 0 * 4, MemoryWordField.encode(0))

        group_actions = GroupActionController.load_group_actions()
        self.assertEqual(256, len(group_actions), 'There should still be 256 GAs')
        for i in range(256):
            self.assertFalse(group_actions[i].in_use, 'GA {0} should not be in use'.format(i))

        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(group_actions[0], group_action, 'The GA is equal (same id, same name, same in_use state)')
        self.assertFalse(group_action.in_use, 'The GA is still not in use')

        # Add BA at start address and set a name
        basic_action_1 = BasicAction(0, 0)
        GroupActionTest._write(memory[281], 0 * 6, basic_action_1.encode())
        GroupActionTest._write(memory[261], 0 * 16, GroupActionTest._encode_string('test'))

        group_action = GroupActionController.load_group_action(0)
        self.assertNotEqual(group_actions[0], group_action, 'The GA changed (name is set)')
        self.assertEqual('test', group_action.name)
        self.assertFalse(group_action.in_use, 'The GA is still not in use')

        # Write valid end address but remove BA
        GroupActionTest._write(memory[256], 0 * 4 + 2, MemoryWordField.encode(0))
        GroupActionTest._write(memory[281], 0 * 6, [255, 255, 255, 255, 255, 255])

        group_action = GroupActionController.load_group_action(0)
        self.assertFalse(group_action.in_use, 'The GA is not in use yet (no BAs defined)')

        # Restore BA
        GroupActionTest._write(memory[281], 0 * 6, basic_action_1.encode())

        group_action = GroupActionController.load_group_action(0)
        self.assertTrue(group_action.in_use, 'The GA is now in use (has name and BA)')
        self.assertEqual(1, len(group_action.actions), 'There should be one GA')
        self.assertEqual(basic_action_1, group_action.actions[0], 'The expected BA should be configured')

        # Make the GA point to two BAs
        GroupActionTest._write(memory[256], 0 * 4 + 2, MemoryWordField.encode(1))

        group_action = GroupActionController.load_group_action(0)
        self.assertTrue(group_action.in_use, 'The GA is still in use')
        self.assertEqual(1, len(group_action.actions), 'An empty BA should be excluded')
        self.assertEqual(basic_action_1, group_action.actions[0], 'The valid BA should still be included')

        # Write second BA
        basic_action_2 = BasicAction(0, 1)
        GroupActionTest._write(memory[281], 1 * 6, basic_action_2.encode())

        group_action = GroupActionController.load_group_action(0)
        self.assertTrue(group_action.in_use, 'The GA is still in use')
        self.assertEqual(2, len(group_action.actions), 'Both BAs should be included')
        self.assertEqual([basic_action_1, basic_action_2], group_action.actions, 'The valid BAs should be included')

        group_actions = GroupActionController.load_group_actions()
        self.assertEqual(256, len(group_actions), 'There should be 256 GAs')
        for i in range(1, 256):
            self.assertFalse(group_actions[i].in_use, 'GA {0} should not be in use'.format(i))
        self.assertEqual(group_action, group_actions[0], 'The list should correctly point to the first GA')

        # Set name of third GA, store BA and set addresses
        basic_action_3 = BasicAction(0, 2)
        GroupActionTest._write(memory[281], 2 * 6, basic_action_3.encode())
        GroupActionTest._write(memory[261], 2 * 16, GroupActionTest._encode_string('three'))
        GroupActionTest._write(memory[256], 2 * 4, MemoryWordField.encode(2))
        GroupActionTest._write(memory[256], 2 * 4 + 2, MemoryWordField.encode(2))

        group_action_2 = GroupActionController.load_group_action(2)
        group_actions = GroupActionController.load_group_actions()
        self.assertEqual(256, len(group_actions), 'There should be 256 GAs')
        for i in range(0, 256):
            if i in [0, 2]:
                continue
            self.assertFalse(group_actions[i].in_use, 'GA {0} should not be in use'.format(i))
        self.assertEqual(group_action, group_actions[0], 'The list should correctly point to the first GA')
        self.assertEqual(group_action_2, group_actions[2], 'The list should correctly point to the first GA')


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
