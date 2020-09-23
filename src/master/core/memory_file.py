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
Contains a memory representation
"""
from __future__ import absolute_import
import copy
import logging
from ioc import Inject, INJECTED
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer, CoreCommunicator
from master.core.events import Event
from master.core.memory_types import MemoryAddress

if False:  # MYPY
    from typing import List, Dict, Callable, Any, Optional, Iterator

logger = logging.getLogger("openmotics")


class MemoryTypes(object):
    FRAM = 'F'
    EEPROM = 'E'


class MemoryFile(object):

    WRITE_TIMEOUT = 5
    READ_TIMEOUT = 5
    ACTIVATE_TIMEOUT = 5
    WRITE_CHUNK_SIZE = 32
    SIZES = {MemoryTypes.EEPROM: (512, 256),
             MemoryTypes.FRAM: (128, 256)}

    @Inject
    def __init__(self, memory_type, master_communicator=INJECTED):  # type: (str, CoreCommunicator) -> None
        """
        Initializes the MemoryFile instance, reprensenting one of the supported memory types.
        It provides caching for EEPROM, and direct write/read through for FRAM
        """
        if not master_communicator:
            raise RuntimeError('Could not inject argument: core_communicator')

        self._core_communicator = master_communicator
        self.type = memory_type
        self._cache = {}  # type: Dict[int, bytearray]
        self._eeprom_change_callback = None  # type: Optional[Callable[[], None]]
        self._pages, self._page_length = MemoryFile.SIZES[memory_type]  # type: int, int

        if memory_type == MemoryTypes.EEPROM:
            self._core_communicator.register_consumer(
                BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
            )

    def subscribe_eeprom_change(self, callback):  # type: (Callable[[], None]) -> None
        self._eeprom_change_callback = callback

    def _handle_event(self, data):  # type: (Dict[str, Any]) -> None
        core_event = Event(data)
        if core_event.type == Event.Types.SYSTEM and core_event.data['type'] == Event.SystemEventTypes.EEPROM_ACTIVATE:
            self.invalidate_cache()
            if self._eeprom_change_callback is not None:
                self._eeprom_change_callback()
            logger.info('Cache cleared: EEPROM_ACTIVATE')

    def read(self, addresses):  # type: (List[MemoryAddress]) -> Dict[MemoryAddress, bytearray]
        data = {}
        for address in addresses:
            page_data = self.read_page(address.page)
            data[address] = page_data[address.offset:address.offset + address.length]
        return data

    def write(self, data_map):  # type: (Dict[MemoryAddress, bytearray]) -> None
        for address, data in data_map.items():
            page_data = self.read_page(address.page)
            for index, data_byte in enumerate(data):
                page_data[address.offset + index] = data_byte
            self.write_page(address.page, page_data)

    def read_page(self, page):  # type: (int) -> bytearray
        def _read_page():
            page_data = bytearray()
            for i in range(self._page_length // 32):
                page_data += self._core_communicator.do_command(
                    command=CoreAPI.memory_read(),
                    fields={'type': self.type, 'page': page, 'start': i * 32, 'length': 32},
                    timeout=MemoryFile.READ_TIMEOUT
                )['data']
            return page_data

        if self.type == MemoryTypes.FRAM:
            return _read_page()

        if page not in self._cache:
            self._cache[page] = _read_page()
        return copy.copy(self._cache[page])

    def write_page(self, page, data):  # type: (int, bytearray) -> None
        cached_data = None
        if self.type == MemoryTypes.EEPROM:
            cached_data = self._cache.get(page)

        for i in range(self._page_length // MemoryFile.WRITE_CHUNK_SIZE):
            start = i * MemoryFile.WRITE_CHUNK_SIZE
            cache_chunk = None
            if cached_data is not None:
                cache_chunk = cached_data[start:start + MemoryFile.WRITE_CHUNK_SIZE]
            data_chunk = data[start:start + MemoryFile.WRITE_CHUNK_SIZE]
            if data_chunk != cache_chunk:
                logger.info('MEMORY.{0}: Write P{1} S{2} D[{3}]'.format(self.type, page, start, ' '.join(str(b) for b in data_chunk)))
                self._core_communicator.do_command(
                    command=CoreAPI.memory_write(MemoryFile.WRITE_CHUNK_SIZE),
                    fields={'type': self.type, 'page': page, 'start': start, 'data': data_chunk},
                    timeout=MemoryFile.WRITE_TIMEOUT
                )

        if self.type == MemoryTypes.EEPROM:
            self._cache[page] = data

    def activate(self):  # type: () -> None
        if self.type == MemoryTypes.EEPROM:
            logger.info('MEMORY.{0}: Activate'.format(self.type))
            self._core_communicator.do_basic_action(action_type=200, action=1, timeout=MemoryFile.ACTIVATE_TIMEOUT)

    def invalidate_cache(self, page=None):  # type: (Optional[int]) -> None
        if page is None:
            pages = list(range(self._pages))  # type: List[int]
        else:
            pages = [page]
        for page in pages:
            self._cache.pop(page, None)
