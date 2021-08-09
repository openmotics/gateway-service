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
"""
Holds virtual core
"""

from __future__ import absolute_import
import mock
from ioc import SetUpTestInjections
from gateway.pubsub import PubSub
from gateway.hal.master_controller_core import MasterCoreController
from master.core.memory_file import MemoryFile, MemoryTypes
from master.core.core_communicator import CoreCommunicator
from master.core.ucan_communicator import UCANCommunicator
from master.core.slave_communicator import SlaveCommunicator


class MockedCore(object):

    def __init__(self, memory_is_cache=False):
        self.memory = {MemoryTypes.FRAM: {}, MemoryTypes.EEPROM: {}}
        self.return_data = {}

        self.communicator = mock.Mock(CoreCommunicator)
        self.communicator.do_command = self._do_command
        self.pubsub = PubSub()
        SetUpTestInjections(master_communicator=self.communicator,
                            pubsub=self.pubsub)

        self.memory_file = MemoryFile()
        if memory_is_cache:
            self.memory_file._eeprom_cache = self.memory[MemoryTypes.EEPROM]
        SetUpTestInjections(memory_file=self.memory_file,
                            ucan_communicator=UCANCommunicator(),
                            slave_communicator=SlaveCommunicator())
        self.controller = MasterCoreController()
        self.write_log = []

    def _do_command(self, command, fields, timeout=None):
        _ = timeout
        instruction = ''.join(str(chr(c)) for c in command.instruction)
        if instruction == 'MR':
            mtype = fields['type']
            page = fields['page']
            start = fields['start']
            length = fields['length']
            return {'data': self.memory.setdefault(mtype, {}).get(page, bytearray([255] * 256))[start:start + length]}
        elif instruction == 'MW':
            mtype = fields['type']
            page = fields['page']
            start = fields['start']
            page_data = self.memory.setdefault(mtype, {}).setdefault(page, bytearray([255] * 256))
            self.write_log.append(fields)
            for index, data_byte in enumerate(fields['data']):
                page_data[start + index] = data_byte
        elif instruction == 'BA':
            if fields['type'] == 200 and fields['action'] == 1:
                # Send EEPROM_ACTIVATE event
                self.memory_file._handle_event({'type': 248, 'action': 0, 'device_nr': 0, 'data': 0})
        elif instruction in self.return_data:
            return self.return_data[instruction]
        else:
            raise AssertionError('unexpected instruction: {0}'.format(instruction))
