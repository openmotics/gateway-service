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
Module to communicate with the Core.

"""

from __future__ import absolute_import

import logging
import select
import struct
import time
import six
from threading import Lock
from collections import Counter
from six.moves.queue import Empty, Queue
from gateway.daemon_thread import BaseThread
from ioc import INJECTED, Inject
from master.core.core_api import CoreAPI
from master.core.core_command import CoreCommandSpec
from master.core.fields import WordField
from master.core.toolbox import Toolbox
from serial_utils import CommunicationTimedOutException, Printable

if False:  # MYPY
    from master.core.basic_action import BasicAction
    from typing import Dict, Any, Optional, TypeVar, Union, Callable, Set, List
    from serial import Serial
    T_co = TypeVar('T_co', bound=None, covariant=True)

logger = logging.getLogger(__name__)


class CoreCommunicator(object):
    """
    Uses a serial port to communicate with the Core and updates the output state.
    Provides methods to send CoreCommands.
    """

    # Message constants. There are here for better code readability, you can't just simply change them
    START_OF_REQUEST = bytearray(b'STR')
    END_OF_REQUEST = bytearray(b'\r\n\r\n')
    START_OF_REPLY = bytearray(b'RTR')
    END_OF_REPLY = bytearray(b'\r\n')

    @Inject
    def __init__(self, controller_serial=INJECTED):
        # type: (Serial) -> None
        self._verbose = logger.level >= logging.DEBUG
        self._serial = controller_serial
        self._serial_write_lock = Lock()
        self._cid_lock = Lock()
        self._serial_bytes_written = 0
        self._serial_bytes_read = 0

        self._cid = None  # type: Optional[int]  # Reserved CIDs: 0 = Core events, 1 = uCAN transport, 2 = Slave transport
        self._cids_in_use = set()  # type: Set[int]
        self._consumers = {}  # type: Dict[int, List[Union[Consumer, BackgroundConsumer]]]
        self._last_success = 0.0
        self._stop = False

        self._word_helper = WordField('')
        self._read_thread = None  # type: Optional[BaseThread]

        self._command_total_histogram = Counter()  # type: Counter
        self._command_success_histogram = Counter()  # type: Counter
        self._command_timeout_histogram = Counter()  # type: Counter

        self._communication_stats = {'calls_succeeded': [],
                                     'calls_timedout': [],
                                     'bytes_written': 0,
                                     'bytes_read': 0}  # type: Dict[str,Any]
        self._debug_buffer = {'read': {},
                              'write': {}}  # type: Dict[str, Dict[float, bytearray]]
        self._debug_buffer_duration = 300

    def start(self):
        """ Start the CoreComunicator, this starts the background read thread. """
        self._stop = False
        self._read_thread = BaseThread(name='coreread', target=self._read)
        self._read_thread.setDaemon(True)
        self._read_thread.start()

    def stop(self):
        self._stop = True
        if self._read_thread is not None:
            self._read_thread.join()
            self._read_thread = None

    def is_running(self):
        return not self._stop and self._read_thread is not None

    def get_communication_statistics(self):
        return self._communication_stats

    def reset_communication_statistics(self):
        self._communication_stats = {'calls_succeeded': [],
                                     'calls_timedout': [],
                                     'bytes_written': 0,
                                     'bytes_read': 0}

    def get_command_histograms(self):
        return {'total': dict(self._command_total_histogram),
                'success': dict(self._command_success_histogram),
                'timeout': dict(self._command_timeout_histogram)}

    def reset_command_histograms(self):
        self._command_total_histogram.clear()
        self._command_success_histogram.clear()
        self._command_timeout_histogram.clear()

    def get_debug_buffer(self):
        # type: () -> Dict[str,Dict[float,str]]
        def process(buffer):
            return {k: str(Printable(v)) for k, v in six.iteritems(buffer)}

        return {'read': process(self._debug_buffer['read']),
                'write': process(self._debug_buffer['write'])}

    def get_seconds_since_last_success(self):  # type: () -> float
        """ Get the number of seconds since the last successful communication. """
        if self._last_success == 0:
            return 0.0  # No communication - return 0 sec since last success
        else:
            return time.time() - self._last_success

    def _get_cid(self):  # type: () -> int
        """ Get a communication id. 0 and 1 are reserved. """
        def _increment_cid(current_cid):  # type: (Optional[int]) -> int
            # Reserved CIDs: 0 = Core events, 1 = uCAN transport, 2 = Slave transport
            return current_cid + 1 if (current_cid is not None and current_cid < 255) else 3

        def _available(candidate_cid):  # type: (Optional[int]) -> bool
            if candidate_cid is None:
                return False
            if candidate_cid == self._cid:
                return False
            if candidate_cid in self._cids_in_use:
                return False
            return True

        with self._cid_lock:
            cid = self._cid  # type: Optional[int]  # Initial value
            while not _available(cid):
                cid = _increment_cid(cid)
                if cid == self._cid:
                    # Seems there is no CID available at this moment
                    raise RuntimeError('No available CID')
            if cid is None:
                # This is impossible due to `_available`, but mypy doesn't know that
                raise RuntimeError('CID should not be None')
            self._cid = cid
            self._cids_in_use.add(cid)
            return cid

    def _write_to_serial(self, data):  # type: (bytearray) -> None
        """
        Write data to the serial port.

        :param data: the data to write
        """
        with self._serial_write_lock:
            logger.debug('Writing to Core serial:   %s', Printable(data))

            threshold = time.time() - self._debug_buffer_duration
            self._debug_buffer['write'][time.time()] = data
            for t in self._debug_buffer['write'].keys():
                if t < threshold:
                    del self._debug_buffer['write'][t]

            self._serial.write(data)
            self._serial_bytes_written += len(data)
            self._communication_stats['bytes_written'] += len(data)

    def register_consumer(self, consumer):  # type: (Union[Consumer, BackgroundConsumer]) -> None
        """
        Register a consumer
        :param consumer: The consumer to register.
        """
        self._consumers.setdefault(consumer.get_hash(), []).append(consumer)

    def discard_cid(self, cid):  # type: (int) -> None
        """
        Discards a Command ID.
        """
        with self._cid_lock:
            self._cids_in_use.discard(cid)

    def unregister_consumer(self, consumer):  # type: (Union[Consumer, BackgroundConsumer]) -> None
        """
        Unregister a consumer
        """
        consumers = self._consumers.get(consumer.get_hash(), [])
        if consumer in consumers:
            consumers.remove(consumer)
        self.discard_cid(consumer.cid)

    def do_command(self, command, fields, timeout=2):
        # type: (CoreCommandSpec, Dict[str, Any], Union[T_co, int]) -> Union[T_co, Dict[str, Any]]
        """
        Send a command over the serial port and block until an answer is received.
        If the Core does not respond within the timeout period, a CommunicationTimedOutException is raised

        :param command: specification of the command to execute
        :param fields: A dictionary with the command input field values
        :param timeout: maximum allowed time before a CommunicationTimedOutException is raised
        """
        cid = self._get_cid()
        consumer = Consumer(command, cid)
        command = consumer.command

        try:
            self._command_total_histogram.update({str(command.instruction): 1})
            self._consumers.setdefault(consumer.get_hash(), []).append(consumer)
            self._send_command(cid, command, fields)
        except Exception:
            self.discard_cid(cid)
            raise

        try:
            result = None  # type: Any
            if isinstance(consumer, Consumer) and timeout is not None:
                result = consumer.get(timeout)
            self._last_success = time.time()
            self._communication_stats['calls_succeeded'].append(time.time())
            self._communication_stats['calls_succeeded'] = self._communication_stats['calls_succeeded'][-50:]
            self._command_success_histogram.update({str(command.instruction): 1})
            return result
        except CommunicationTimedOutException:
            self.unregister_consumer(consumer)
            self._communication_stats['calls_timedout'].append(time.time())
            self._communication_stats['calls_timedout'] = self._communication_stats['calls_timedout'][-50:]
            self._command_timeout_histogram.update({str(command.instruction): 1})
            raise

    def _send_command(self, cid, command, fields):  # type: (int, CoreCommandSpec, Dict[str, Any]) -> None
        """
        Send a command over the serial port

        :param cid: The command ID
        :param command: The Core CommandSpec
        :param fields: A dictionary with the command input field values
        """

        payload = command.create_request_payload(fields)

        checked_payload = (bytearray([cid]) +
                           command.instruction +
                           self._word_helper.encode(len(payload)) +
                           payload)

        data = (CoreCommunicator.START_OF_REQUEST +
                checked_payload +
                bytearray(b'C') +
                CoreCommunicator._calculate_crc(checked_payload) +
                CoreCommunicator.END_OF_REQUEST)

        self._write_to_serial(data)

    @staticmethod
    def _calculate_crc(data):  # type: (bytearray) -> bytearray
        """
        Calculate the CRC of the data.

        :param data: Data for which to calculate the CRC
        :returns: CRC
        """
        crc = 0
        for byte in data:
            crc += byte
        return bytearray([crc % 256])

    def _read(self):
        """
        Code for the background read thread: reads from the serial port and forward certain messages to waiting
        consumers

        Request format: 'STR' + {CID, 1 byte} + {command, 2 bytes} + {length, 2 bytes} + {payload, `length` bytes} + 'C' + {checksum, 1 byte} + '\r\n\r\n'
        Response format: 'RTR' + {CID, 1 byte} + {command, 2 bytes} + {length, 2 bytes} + {payload, `length` bytes} + 'C' + {checksum, 1 byte} + '\r\n'

        """
        data = bytearray()
        message_length = None
        header_fields = None
        header_length = len(CoreCommunicator.START_OF_REPLY) + 1 + 2 + 2  # RTR + CID (1 byte) + command (2 bytes) + length (2 bytes)
        footer_length = 1 + 1 + len(CoreCommunicator.END_OF_REPLY)  # 'C' + checksum (1 byte) + \r\n
        need_more_data = False

        while not self._stop:
            try:
                # Wait for data if more data is expected
                if need_more_data:
                    readers, _, _ = select.select([self._serial], [], [], 1)
                    if not readers:
                        continue
                    need_more_data = False

                # Read what's now on the serial port
                num_bytes = self._serial.inWaiting()
                if num_bytes > 0:
                    data += self._serial.read(num_bytes)
                    # Update counters
                    self._serial_bytes_read += num_bytes
                    self._communication_stats['bytes_read'] += num_bytes

                # Wait for the full message, or the header length
                min_length = message_length or header_length
                if len(data) < min_length:
                    need_more_data = True
                    continue

                if message_length is None:
                    # Check if the data contains the START_OF_REPLY
                    if CoreCommunicator.START_OF_REPLY not in data:
                        need_more_data = True
                        continue

                    # Align with START_OF_REPLY
                    if not data.startswith(CoreCommunicator.START_OF_REPLY):
                        data = CoreCommunicator.START_OF_REPLY + data.split(CoreCommunicator.START_OF_REPLY, 1)[-1]
                        if len(data) < header_length:
                            continue

                    header_fields = CoreCommunicator._parse_header(data)
                    message_length = header_fields['length'] + header_length + footer_length

                    # If not all data is present, wait for more data
                    if len(data) < message_length:
                        continue

                message = data[:message_length]  # type: bytearray
                data = data[message_length:]

                # A possible message is received, log where appropriate
                logger.debug('Reading from Core serial: %s', Printable(message))
                threshold = time.time() - self._debug_buffer_duration
                self._debug_buffer['read'][time.time()] = message
                for t in self._debug_buffer['read'].keys():
                    if t < threshold:
                        del self._debug_buffer['read'][t]

                # Validate message boundaries
                correct_boundaries = message.startswith(CoreCommunicator.START_OF_REPLY) and message.endswith(CoreCommunicator.END_OF_REPLY)
                if not correct_boundaries:
                    logger.warning('Unexpected boundaries: %s', Printable(message))
                    # Reset, so we'll wait for the next RTR
                    message_length = None
                    data = message[3:] + data  # Strip the START_OF_REPLY, and restore full data
                    continue

                # Validate message CRC
                crc = bytearray([message[-3]])
                payload = message[8:-4]  # type: bytearray
                checked_payload = message[3:-4]  # type: bytearray
                expected_crc = CoreCommunicator._calculate_crc(checked_payload)
                if crc != expected_crc:
                    logger.warning('Unexpected CRC (%s vs expected %s): %s', crc, expected_crc, Printable(checked_payload))
                    # Reset, so we'll wait for the next RTR
                    message_length = None
                    data = message[3:] + data  # Strip the START_OF_REPLY, and restore full data
                    continue

                # A valid message is received, reliver it to the correct consumer
                consumers = self._consumers.get(header_fields['hash'], [])
                for consumer in consumers[:]:
                    logger.debug('Delivering payload to consumer %s.%s: %s', header_fields['command'], header_fields['cid'], Printable(payload))
                    consumer.consume(payload)
                    if isinstance(consumer, Consumer):
                        self.unregister_consumer(consumer)

                self.discard_cid(header_fields['cid'])

                # Message processed, cleaning up
                message_length = None
            except Exception:
                logger.exception('Unexpected exception at Core read thread')
                data = bytearray()
                message_length = None

    @staticmethod
    def _parse_header(data):  # type: (bytearray) -> Dict[str, Union[int, bytearray]]
        base = len(CoreCommunicator.START_OF_REPLY)
        return {'cid': data[base],
                'command': data[base + 1:base + 3],
                'hash': Toolbox.hash(data[:base + 3]),
                'length': struct.unpack('>H', data[base + 3:base + 5])[0]}


class Consumer(object):
    """
    A consumer is registered to the read thread before a command is issued.  If an output
    matches the consumer, the output will unblock the get() caller.
    """

    def __init__(self, command, cid):  # type: (CoreCommandSpec, int) -> None
        self.cid = cid
        self.command = command
        self._queue = Queue()  # type: Queue[Dict[str, Any]]

    def get_hash(self):  # type: () -> int
        """ Get an identification hash for this consumer. """
        return Toolbox.hash(CoreCommunicator.START_OF_REPLY +
                            bytearray([self.cid]) +
                            self.command.response_instruction)

    def consume(self, payload):  # type: (bytearray) -> None
        """ Consume payload. """
        data = self.command.consume_response_payload(payload)
        self._queue.put(data)

    def get(self, timeout):  # type: (Union[T_co, int]) -> Dict[str, Any]
        """
        Wait until the Core replies or the timeout expires.

        :param timeout: timeout in seconds
        :returns: dict containing the output fields of the command
        """
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            raise CommunicationTimedOutException('No Core data received in {0}s'.format(timeout))


class BackgroundConsumer(object):
    """
    A consumer that runs in the background. The BackgroundConsumer does not provide get()
    but does a callback to a function whenever a message was consumed.
    """

    def __init__(self, command, cid, callback):  # type: (CoreCommandSpec, int, Callable[[Dict[str, Any]], None]) -> None
        """
        Create a background consumer using a cmd, cid and callback.

        :param command: the CoreCommand to consume.
        :param cid: the communication id.
        :param callback: function to call when an instance was found.
        """
        self.cid = cid
        self.command = command
        self._callback = callback
        self._queue = Queue()  # type: Queue[Dict[str, Any]]

        self._callback_thread = BaseThread(name='coredelivery', target=self._consumer)
        self._callback_thread.setDaemon(True)
        self._callback_thread.start()

    def _consumer(self):
        while True:
            try:
                self.deliver()
            except Exception:
                logger.exception('Unexpected exception delivering background consumer data')
                time.sleep(1)

    def get_hash(self):  # type: () -> int
        """ Get an identification hash for this consumer. """
        return Toolbox.hash(CoreCommunicator.START_OF_REPLY +
                            bytearray([self.cid]) +
                            self.command.response_instruction)

    def consume(self, payload):  # type: (bytearray) -> None
        """ Consume payload. """
        data = self.command.consume_response_payload(payload)
        self._queue.put(data)

    def deliver(self):
        """ Deliver data to the callback functions. """
        self._callback(self._queue.get())
