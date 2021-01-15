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
from master.core.group_action import GroupActionController, GroupAction
from master.core.memory_file import MemoryTypes, MemoryFile
from master.core.fields import WordField


class GroupActionTest(unittest.TestCase):
    """ Tests for MemoryFile """

    ADDRESS_START_PAGE = 256
    ACTIONS_START_PAGE = 281
    GANAMES_START_PAGE = 261

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

    def setUp(self):
        self.maxDiff = None
        self._word_helper = WordField('')

    @staticmethod
    def _encode_string(value):
        data = []
        for char in value:
            data.append(ord(char))
        data.append(255)
        return bytearray(data)

    @staticmethod
    def _write(memory_page, start_address, data):
        for i in range(len(data)):
            memory_page[start_address + i] = data[i]

    @staticmethod
    def _get_readable_ba_block(memory):
        entries = []
        for i in range(42):
            action_type = memory[GroupActionTest.ACTIONS_START_PAGE][i * 6]
            if action_type == 255:
                entries.append('_')
            elif action_type >= 100:
                entries.append('X')
            else:
                entries.append(str(action_type))
        return ''.join(entries)

    @staticmethod
    def _setup_master_communicator(memory):
        def _do_command(command, fields, timeout=None):
            _ = timeout
            if command.instruction == 'MW':
                page = fields['page']
                start = fields['start']
                page_data = memory.setdefault(page, [255] * 256)
                for index, data_byte in enumerate(fields['data']):
                    page_data[start + index] = data_byte

        def _do_basic_action(action_type, action, device_nr=0, extra_parameter=0, timeout=2, log=True):
            _ = device_nr, extra_parameter, timeout, log
            if action_type == 200 and action == 1:
                # Send EEPROM_ACTIVATE event
                eeprom_file._handle_event({'type': 254, 'action': 0, 'device_nr': 0, 'data': 0})

        master_communicator = Mock()
        master_communicator.do_command = _do_command
        master_communicator.do_basic_action = _do_basic_action

        SetUpTestInjections(master_communicator=master_communicator,
                            pubsub=Mock())
        eeprom_file = MemoryFile(MemoryTypes.EEPROM)
        eeprom_file._cache = memory
        SetUpTestInjections(memory_files={MemoryTypes.EEPROM: eeprom_file,
                                          MemoryTypes.FRAM: MemoryFile(MemoryTypes.FRAM)})

    def test_list_group_actions(self):
        memory = {}
        for page in range(256, 381):
            memory[page] = bytearray([255] * 256)
        GroupActionTest._setup_master_communicator(memory)

        group_actions = GroupActionController.load_group_actions()
        self.assertEqual(256, len(group_actions), 'There should be 256 GAs')
        for i in range(256):
            self.assertFalse(group_actions[i].in_use, 'GA {0} should not be in use'.format(i))

        # Set valid start address
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 0 * 4, self._word_helper.encode(0))

        group_actions = GroupActionController.load_group_actions()
        self.assertEqual(256, len(group_actions), 'There should still be 256 GAs')
        for i in range(256):
            self.assertFalse(group_actions[i].in_use, 'GA {0} should not be in use'.format(i))

        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(group_actions[0], group_action, 'The GA is equal (same id, same name, same in_use state)')
        self.assertFalse(group_action.in_use, 'The GA is still not in use')

        # Add BA at start address and set a name
        basic_action_1 = BasicAction(0, 0)
        GroupActionTest._write(memory[GroupActionTest.ACTIONS_START_PAGE], 0 * 6, basic_action_1.encode())
        GroupActionTest._write(memory[GroupActionTest.GANAMES_START_PAGE], 0 * 16, GroupActionTest._encode_string('test'))

        group_action = GroupActionController.load_group_action(0)
        self.assertNotEqual(group_actions[0], group_action, 'The GA changed (name is set)')
        self.assertEqual('test', group_action.name)
        self.assertFalse(group_action.in_use, 'The GA is still not in use')

        # Write valid end address but remove BA
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 0 * 4 + 2, self._word_helper.encode(0))
        GroupActionTest._write(memory[GroupActionTest.ACTIONS_START_PAGE], 0 * 6, [255, 255, 255, 255, 255, 255])

        group_action = GroupActionController.load_group_action(0)
        self.assertFalse(group_action.in_use, 'The GA is not in use yet (no BAs defined)')

        # Restore BA
        GroupActionTest._write(memory[GroupActionTest.ACTIONS_START_PAGE], 0 * 6, basic_action_1.encode())

        group_action = GroupActionController.load_group_action(0)
        self.assertTrue(group_action.in_use, 'The GA is now in use (has name and BA)')
        self.assertEqual(1, len(group_action.actions), 'There should be one GA')
        self.assertEqual(basic_action_1, group_action.actions[0], 'The expected BA should be configured')

        # Make the GA point to two BAs
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 0 * 4 + 2, self._word_helper.encode(1))

        group_action = GroupActionController.load_group_action(0)
        self.assertTrue(group_action.in_use, 'The GA is still in use')
        self.assertEqual(1, len(group_action.actions), 'An empty BA should be excluded')
        self.assertEqual(basic_action_1, group_action.actions[0], 'The valid BA should still be included')

        # Write second BA
        basic_action_2 = BasicAction(0, 1)
        GroupActionTest._write(memory[GroupActionTest.ACTIONS_START_PAGE], 1 * 6, basic_action_2.encode())

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
        GroupActionTest._write(memory[GroupActionTest.ACTIONS_START_PAGE], 2 * 6, basic_action_3.encode())
        GroupActionTest._write(memory[GroupActionTest.GANAMES_START_PAGE], 2 * 16, GroupActionTest._encode_string('three'))
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 2 * 4, self._word_helper.encode(2))
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 2 * 4 + 2, self._word_helper.encode(2))

        group_action_2 = GroupActionController.load_group_action(2)
        group_actions = GroupActionController.load_group_actions()
        self.assertEqual(256, len(group_actions), 'There should be 256 GAs')
        for i in range(0, 256):
            if i in [0, 2]:
                continue
            self.assertFalse(group_actions[i].in_use, 'GA {0} should not be in use'.format(i))
        self.assertEqual(group_action, group_actions[0], 'The list should correctly point to the first GA')
        self.assertEqual(group_action_2, group_actions[2], 'The list should correctly point to the first GA')

    def test_space_map(self):
        memory = {}
        for page in range(256, 381):
            memory[page] = bytearray([255] * 256)
        GroupActionTest._setup_master_communicator(memory)

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual({4200: [0]}, space_map, 'An empty map is expected')

        # Write a single start address
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 0 * 4, self._word_helper.encode(0))

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual({4200: [0]}, space_map, 'There should still be an empty map')

        # Write an end address
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 0 * 4 + 2, self._word_helper.encode(0))

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual({4199: [1]}, space_map, 'First address is used')

        # Write a few more addresses:
        # Range 0-0 already used by above code
        # Range 1-9 (0)
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 1 * 4, self._word_helper.encode(10) + self._word_helper.encode(14))
        # Range 15-19 (5)
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 2 * 4, self._word_helper.encode(20) + self._word_helper.encode(24))
        # Range 25-29 (5)
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 4 * 4, self._word_helper.encode(30) + self._word_helper.encode(34))
        # Range 35-99 (65)
        GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], 3 * 4, self._word_helper.encode(100) + self._word_helper.encode(163))
        # Range 164-4199 (4036)

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual({9: [1],
                          5: [15, 25],
                          65: [35],
                          4036: [164]}, space_map, 'Expect a few gaps')

    def test_save_configuration(self):
        memory = {}
        for page in range(256, 381):
            memory[page] = bytearray([255] * 256)
        GroupActionTest._setup_master_communicator(memory)

        group_action = GroupAction(id=5, name='five')
        GroupActionController.save_group_action(group_action, ['name'])

        self.assertEqual(GroupActionTest._encode_string('five'), memory[GroupActionTest.GANAMES_START_PAGE][5 * 16:5 * 16 + 5])

    def test_save_allocations(self):
        """
        This test validates whether writing a GA will store its BAs in the appropriate location. This
        is checked on two ways:
        1. A free space map is generated that is used to validate where the free slots are located
        2. A human readable / visual overview is generated of all BA's action type values in the first 42 addresses
           Legend: X = Used by a few pre-defined GAs
                   n = Actual data, as every insert uses different action types, this can be used to verify
                       whether data is written correctly, as whether the old data is overwritten when needed.
                   _ = Slot that was never used
        Note: As an allocation table is used, the BA space is not cleared, only the reference is removed!
        """
        memory = {}
        for page in range(256, 381):
            memory[page] = bytearray([255] * 256)
        GroupActionTest._setup_master_communicator(memory)

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('__________________________________________', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({4200: [0]}, space_map)

        # Generate "pre-defined" GAs
        for group_action_id, address in {10: 0, 11: 2, 12: 5, 13: 8, 14: 14, 15: 25, 16: (41, 4199)}.items():
            start, end = (address[0], address[1]) if isinstance(address, tuple) else (address, address)
            GroupActionTest._write(memory[GroupActionTest.ADDRESS_START_PAGE], group_action_id * 4, self._word_helper.encode(start) + self._word_helper.encode(end))
            memory[GroupActionTest.ACTIONS_START_PAGE][start * 6] = 100 + group_action_id

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X_X__X__X_____X__________X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({1: [1],
                          2: [3, 6],
                          5: [9],
                          10: [15],
                          15: [26]}, space_map)

        # Store GA with 1 BA
        group_action_1 = GroupAction(id=1, actions=[BasicAction(1, 0)])
        GroupActionController.save_group_action(group_action_1, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X1X__X__X_____X__________X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({2: [3, 6],
                          5: [9],
                          10: [15],
                          15: [26]}, space_map)

        # Store another GA with 1 BA
        group_action_2 = GroupAction(id=2, actions=[BasicAction(2, 0)])
        GroupActionController.save_group_action(group_action_2, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X1X2_X__X_____X__________X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({1: [4],
                          2: [6],
                          5: [9],
                          10: [15],
                          15: [26]}, space_map)

        # GA is update dto two BAs
        group_action_2 = GroupAction(id=2, actions=[BasicAction(3, 0),
                                                    BasicAction(3, 0)])
        GroupActionController.save_group_action(group_action_2, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X1X33X__X_____X__________X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({2: [6],
                          5: [9],
                          10: [15],
                          15: [26]}, space_map)

        # First GA is extended
        group_action_1 = GroupAction(id=1, actions=[BasicAction(4, 0),
                                                    BasicAction(4, 0)])
        GroupActionController.save_group_action(group_action_1, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X1X33X44X_____X__________X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({1: [1],
                          5: [9],
                          10: [15],
                          15: [26]}, space_map)

        # Add large GA
        group_action_3 = GroupAction(id=3, actions=[BasicAction(5, 0), BasicAction(5, 0), BasicAction(5, 0),
                                                    BasicAction(5, 0), BasicAction(5, 0), BasicAction(5, 0)])
        GroupActionController.save_group_action(group_action_3, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X1X33X44X_____X555555____X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({1: [1],
                          4: [21],
                          5: [9],
                          15: [26]}, space_map)

        # Large GA is reduced
        group_action_3 = GroupAction(id=3, actions=[BasicAction(6, 0), BasicAction(6, 0), BasicAction(6, 0)])
        GroupActionController.save_group_action(group_action_3, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X1X33X44X666__X555555____X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({1: [1],
                          2: [12],
                          10: [15],
                          15: [26]}, space_map, 'Reduced GA should be moved')

        # Another GA is added with only one BA
        group_action_4 = GroupAction(id=4, actions=[BasicAction(7, 0)])
        GroupActionController.save_group_action(group_action_4, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X7X33X44X666__X555555____X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({2: [12],
                          10: [15],
                          15: [26]}, space_map, 'Reduced GA should be moved')

        # Another large GA is added
        group_action_5 = GroupAction(id=5, actions=[BasicAction(8, 0), BasicAction(8, 0), BasicAction(8, 0),
                                                    BasicAction(8, 0)])
        GroupActionController.save_group_action(group_action_5, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X7X33X44X666__X888855____X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({2: [12],
                          6: [19],
                          15: [26]}, space_map, 'Reduced GA should be moved')

        # Large GA is "deleted"
        group_action_5 = GroupAction(id=5, actions=[])
        GroupActionController.save_group_action(group_action_5, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X7X33X44X666__X888855____X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({2: [12],
                          10: [15],
                          15: [26]}, space_map, 'Reduced GA should be moved')

        # A GA with too many BAs is added
        group_action_6 = GroupAction(id=6, actions=[BasicAction(8, 0)] * 16)
        with self.assertRaises(RuntimeError):
            GroupActionController.save_group_action(group_action_6, ['actions'])

        space_map = GroupActionController._free_address_space_map()
        self.assertEqual('X7X33X44X666__X888855____X_______________X', GroupActionTest._get_readable_ba_block(memory))
        #                 |    |    |    |    |    |    |    |    |
        #                 0    5    10   15   20   25   30   35   40
        self.assertEqual({2: [12],
                          10: [15],
                          15: [26]}, space_map, 'Memory is not changed')


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
