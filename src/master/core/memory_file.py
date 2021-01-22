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
from threading import Event as ThreadingEvent

from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer, CoreCommunicator
from master.core.events import Event
from master.core.memory_types import MemoryAddress

if False:  # MYPY
    from typing import List, Dict, Callable, Any, Optional

logger = logging.getLogger("openmotics")


class MemoryTypes(object):
    FRAM = 'F'
    EEPROM = 'E'


class MemoryFile(object):

    # TODO:
    #  * Multiple writes in a single page should only write the page once
    #  * Writes to FRAM must only overwrite the changed data, not the entire page
    #  * Optimize eeprom activates so there's only a single activation if both EEPROM and FRAM are updated

    WRITE_TIMEOUT = 5
    READ_TIMEOUT = 5
    ACTIVATE_TIMEOUT = 5
    WRITE_CHUNK_SIZE = 32
    SIZES = {MemoryTypes.EEPROM: (512, 256),
             MemoryTypes.FRAM: (128, 256)}

    @Inject
    def __init__(self, memory_type, master_communicator=INJECTED, pubsub=INJECTED):
        # type: (str, CoreCommunicator, PubSub) -> None
        """
        Initializes the MemoryFile instance, reprensenting one of the supported memory types.
        It provides caching for EEPROM, and direct write/read through for FRAM
        """
        if not master_communicator:
            raise RuntimeError('Could not inject argument: core_communicator')

        self._core_communicator = master_communicator
        self._pubsub = pubsub
        self.type = memory_type
        self._cache = {}  # type: Dict[int, bytearray]
        self._eeprom_change_callback = None  # type: Optional[Callable[[], None]]
        self._pages, self._page_length = MemoryFile.SIZES[memory_type]  # type: int, int
        self._self_activated = False
        self._dirty = False
        self._activation_event = ThreadingEvent()

        self._core_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
        )

    def _handle_event(self, data):  # type: (Dict[str, Any]) -> None
        core_event = Event(data)
        if core_event.type == Event.Types.SYSTEM and core_event.data['type'] == Event.SystemEventTypes.EEPROM_ACTIVATE:
            if self.type == MemoryTypes.EEPROM:
                if self._self_activated:
                    # Ignore self-activations, since those changes are already in the EEPROM cache
                    self._self_activated = False
                    logger.info('MEMORY.E: Ignore EEPROM_ACTIVATE due to self-activation')
                else:
                    # EEPROM might have been changed, so clear caches
                    self.invalidate_cache()
                    logger.info('MEMORY.E: Cache cleared: EEPROM_ACTIVATE')
                master_event = MasterEvent(MasterEvent.Types.EEPROM_CHANGE, {})
                self._pubsub.publish_master_event(PubSub.MasterTopics.EEPROM, master_event)
            else:
                logger.info('MEMORY.F: Processed EEPROM_ACTIVATE')
            self._activation_event.set()

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
                self._dirty = True

        if self.type == MemoryTypes.EEPROM:
            self._cache[page] = data

    def activate(self):  # type: () -> bool
        activated = False
        if self._dirty:
            self._dirty = False
            self._self_activated = True
            logger.info('MEMORY.{0}: Activate'.format(self.type))
            self._activation_event.clear()
            self._core_communicator.do_basic_action(action_type=200, action=1, timeout=MemoryFile.ACTIVATE_TIMEOUT)
            self._activation_event.wait(timeout=60.0)
            activated = True
        else:
            logger.info('MEMORY.{0}: Ignore activation, not dirty'.format(self.type))
        return activated

    def invalidate_cache(self, page=None):  # type: (Optional[int]) -> None
        if page is None:
            pages = list(range(self._pages))  # type: List[int]
        else:
            pages = [page]
        for page in pages:
            self._cache.pop(page, None)
