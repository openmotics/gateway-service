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

import logging
import time
import threading
from threading import Lock, Event as ThreadingEvent

from gateway.daemon_thread import BaseThread
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Singleton
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer, CoreCommunicator
from master.core.events import Event
from master.core.memory_types import MemoryAddress

if False:  # MYPY
    from typing import List, Dict, Callable, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)


class MemoryTypes(object):
    FRAM = 'F'
    EEPROM = 'E'


@Singleton
class MemoryFile(object):

    WRITE_TIMEOUT = 5
    READ_TIMEOUT = 5
    ACTIVATE_TIMEOUT = 5
    ACTIVATION_HOLD_TIME = 1
    FRAM_TIMEOUT = 5
    WRITE_CHUNK_SIZE = 32
    SIZES = {MemoryTypes.EEPROM: (512, 256),
             MemoryTypes.FRAM: (128, 256)}

    @Inject
    def __init__(self, master_communicator=INJECTED, pubsub=INJECTED):
        # type: (CoreCommunicator, PubSub) -> None
        """
        Initializes the MemoryFile instance, reprensenting read/write to EEPROM and FRAM
        """
        if not master_communicator:
            raise RuntimeError('Could not inject argument: core_communicator')

        self._core_communicator = master_communicator
        self._pubsub = pubsub

        self._eeprom_cache = {}  # type: Dict[int, bytearray]
        self._fram_cache = {}  # type: Dict[int, Tuple[float, bytearray]]

        # The write-cache is a per-thread/per-type cache of all changes that need to be written that has the page
        # as key, and a list of tuples as value, where the tuples holds the start byte and contents
        self._write_cache = {}  # type: Dict[int, Dict[str, Dict[int, Dict[int, int]]]]
        self._write_cache_lock = {}  # type: Dict[int, Lock]
        self._select_write_cache_lock = Lock()
        self._commit_lock = Lock()

        self._stop = False
        self._activate_lock = Lock()
        self._activator_thread = None  # type: Optional[BaseThread]
        self._activation_event = ThreadingEvent()
        self._needs_activation = ThreadingEvent()

        self._eeprom_change_callback = None  # type: Optional[Callable[[], None]]

        self._core_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
        )

    def start(self):
        self._stop = False
        self._activator_thread = BaseThread(name='memoryfile', target=self._activator)
        self._activator_thread.setDaemon(True)
        self._activator_thread.start()

    def stop(self):
        self._stop = True
        if self._activator_thread is not None:
            self._activator_thread.join()

    def _activator(self):
        while not self._stop:
            try:
                if self._needs_activation.wait(timeout=0.25):
                    time.sleep(MemoryFile.ACTIVATION_HOLD_TIME)  # Allow multiple commits in a single activation
                    self._needs_activation.clear()
                    self._activate()
            except Exception:
                logger.exception('Unexpected error while activating')
                time.sleep(5)

    def _handle_event(self, data):  # type: (Dict[str, Any]) -> None
        core_event = Event(data)
        if core_event.type == Event.Types.SYSTEM:
            if core_event.data['type'] == Event.SystemEventTypes.EEPROM_ACTIVATE:
                self._activation_event.set()

    def _get_write_cache(self):  # type: () -> Tuple[Dict[str, Dict[int, Dict[int, int]]], Lock]
        thread_id = threading.current_thread().ident or 0
        if thread_id not in self._write_cache:
            with self._select_write_cache_lock:
                if thread_id not in self._write_cache:
                    self._write_cache[thread_id] = {MemoryTypes.EEPROM: {},
                                                    MemoryTypes.FRAM: {}}
                    self._write_cache_lock[thread_id] = Lock()
        return self._write_cache[thread_id], self._write_cache_lock[thread_id]

    def _clear_write_cache(self):  # type: () -> None
        thread_id = threading.current_thread().ident or 0
        with self._select_write_cache_lock:
            self._write_cache.pop(thread_id, None)
            self._write_cache_lock.pop(thread_id, None)

    @staticmethod
    def _create_read_map(addresses):  # type: (List[MemoryAddress]) -> Dict[str, Set[int]]
        read_map = {}  # type: Dict[str, Set[int]]
        for address in addresses:
            if address.memory_type not in read_map:
                read_map[address.memory_type] = set()
            read_map[address.memory_type].add(address.page)
        return read_map

    def read(self, addresses, read_through=False):  # type: (List[MemoryAddress], bool) -> Dict[MemoryAddress, bytearray]
        read_map = MemoryFile._create_read_map(addresses)
        raw_data = self._load_data(read_map, read_through)
        data = {}
        for address in addresses:
            # No need to copy, as bytearray.slice doesn't return references
            data[address] = raw_data[address.memory_type][address.page][address.offset:address.offset + address.length]
        return data

    def _load_data(self, read_map, read_through):
        # type: (Dict[str, Set[int]], bool) -> Dict[str, Dict[int, bytearray]]
        raw_data = {MemoryTypes.EEPROM: {},
                    MemoryTypes.FRAM: {}}  # type: Dict[str, Dict[int, bytearray]]
        for page in read_map.get(MemoryTypes.EEPROM, set()):
            if page not in self._eeprom_cache or read_through:
                self._eeprom_cache[page] = self._read_data(MemoryTypes.EEPROM, page)
            raw_data[MemoryTypes.EEPROM][page] = self._eeprom_cache[page]
        time_limit = time.time() - MemoryFile.FRAM_TIMEOUT
        for page in read_map.get(MemoryTypes.FRAM, set()):
            if page not in self._fram_cache or self._fram_cache[page][0] < time_limit or read_through:
                self._fram_cache[page] = (time.time(), self._read_data(MemoryTypes.FRAM, page))
            raw_data[MemoryTypes.FRAM][page] = self._fram_cache[page][1]
        return raw_data

    def _read_data(self, memory_type, page):
        page_data = bytearray()
        for i in range(MemoryFile.SIZES[memory_type][1] // 32):
            page_data += self._core_communicator.do_command(
                command=CoreAPI.memory_read(),
                fields={'type': memory_type, 'page': page, 'start': i * 32, 'length': 32},
                timeout=MemoryFile.READ_TIMEOUT
            )['data']
        return page_data

    def write(self, data_map):  # type: (Dict[MemoryAddress, bytearray]) -> None
        write_cache, lock = self._get_write_cache()
        with lock:
            for address, data in data_map.items():
                page_cache = write_cache[address.memory_type].setdefault(address.page, {})
                for index, data_byte in enumerate(data):
                    page_cache[address.offset + index] = data_byte

    def _store_data(self, write_cache):  # type: (Dict[str, Dict[int, Dict[int, int]]]) -> bool
        data_written = False
        for memory_type, type_data in write_cache.items():
            for page, page_data in type_data.items():
                byte_numbers = list(page_data.keys())
                while len(byte_numbers) > 0:
                    # Get contiguous series of bytes
                    start = min(byte_numbers)
                    end = max(byte_numbers)
                    if start <= 127:
                        # Prevent writing over the 127/128 byte boundary
                        end = min(127, end)
                    data = bytearray()
                    for byte_number in range(start, end + 1):
                        if byte_number in page_data:
                            data.append(page_data[byte_number])
                            byte_numbers.remove(byte_number)
                        else:
                            break
                    # Compare with cache (is anything changed)
                    if memory_type == MemoryTypes.EEPROM:
                        cached_data = None
                        if page in self._eeprom_cache:
                            cached_data = self._eeprom_cache[page][start:start + len(data)]
                        if data == cached_data:
                            continue
                    # Write in chuncks
                    for i in range(0, len(data), MemoryFile.WRITE_CHUNK_SIZE):
                        chunk = data[i:i + MemoryFile.WRITE_CHUNK_SIZE]
                        logger.info('MEMORY.{0}: Write P{1} S{2} D[{3}]'.format(memory_type, page, start + i, ' '.join(str(b) for b in chunk)))
                        self._core_communicator.do_command(
                            command=CoreAPI.memory_write(len(chunk)),
                            fields={'type': memory_type, 'page': page, 'start': start + i, 'data': chunk},
                            timeout=MemoryFile.WRITE_TIMEOUT
                        )
                        data_written = True
                    # Cache updated values
                    if memory_type == MemoryTypes.EEPROM:
                        if page in self._eeprom_cache:
                            for index, data_byte in enumerate(data):
                                self._eeprom_cache[page][start + index] = data_byte
        return data_written

    def commit(self):  # type: () -> None
        with self._commit_lock:
            logger.info('MEMORY: Writing')
            write_cache, write_lock = self._get_write_cache()
            with write_lock:
                data_written = self._store_data(write_cache)
                self._clear_write_cache()
            if data_written:
                logger.info('MEMORY: Activate requested')
                self._needs_activation.set()
            else:
                logger.info('MEMORY: No activation required')

    def _activate(self):  # type: () -> None
        with self._activate_lock, self._commit_lock:
            logger.info('MEMORY: Activating')
            self._activation_event.clear()
            self._core_communicator.do_command(
                command=CoreAPI.basic_action(),
                fields={'type': 200, 'action': 1, 'device_nr': 0, 'extra_parameter': 0},
                timeout=MemoryFile.ACTIVATE_TIMEOUT
            )
            self._activation_event.wait(timeout=60.0)
            logger.info('MEMORY: Activated')
            self._notify_eeprom_changed()

    def invalidate_cache(self, reason):  # type: (str) -> None
        for page in range(MemoryFile.SIZES[MemoryTypes.EEPROM][0]):
            self._eeprom_cache.pop(page, None)
        for page in range(MemoryFile.SIZES[MemoryTypes.FRAM][0]):
            self._fram_cache.pop(page, None)
        logger.info('MEMORY: Cache cleared ({0})'.format(reason))
        self._notify_eeprom_changed()

    def _notify_eeprom_changed(self):
        master_event = MasterEvent(MasterEvent.Types.EEPROM_CHANGE, {})
        self._pubsub.publish_master_event(PubSub.MasterTopics.EEPROM, master_event)
