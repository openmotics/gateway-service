# Copyright (C) 2020 OpenMotics BV
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
Module to communicate with the Slave bus.
"""

from __future__ import absolute_import
import logging
from six.moves.queue import Queue, Empty
from ioc import Injectable, Inject, INJECTED, Singleton
from master.core.core_api import CoreAPI
from master.core.core_communicator import CoreCommunicator, BackgroundConsumer
from master.core.slave_command import SlaveCommandSpec
from serial_utils import CommunicationTimedOutException, printable

if False:  # MYPY
    from typing import Optional, Dict, Any

logger = logging.getLogger('openmotics')


@Injectable.named('slave_communicator')
@Singleton
class SlaveCommunicator(object):
    """
    Uses a CoreCommunicator to communicate with the slave bus
    """

    @Inject
    def __init__(self, master_communicator=INJECTED, verbose=False):
        """
        :param master_communicator: CoreCommunicator
        :param verbose: Log all communication
        """
        self._verbose = verbose  # type: bool
        self._communicator = master_communicator  # type: CoreCommunicator
        self._read_buffer = []
        self._consumers = []
        self._transparent_mode = False
        self._read_buffer = bytearray()

        self._background_consumer = BackgroundConsumer(CoreAPI.slave_rx_transport_message(), 2, self._process_transport_message)
        self._communicator.register_consumer(self._background_consumer)

    def register_consumer(self, consumer):
        """
        Register a consumer
        :param consumer: The consumer to register.
        :type consumer: Consumer.
        """
        self._consumers.append(consumer)

    def unregister_consumer(self, consumer):
        """
        Unregister a consumer
        :param consumer: The consumer to register.
        :type consumer: Consumer.
        """
        if consumer in self._consumers:
            self._consumers.remove(consumer)

    def enter_transparent_mode(self):
        response = self._communicator.do_command(command=CoreAPI.set_slave_bus_mode(),
                                                 fields={'mode': CoreAPI.SlaveBusMode.TRANSPARENT})
        self._transparent_mode = response['mode'] == CoreAPI.SlaveBusMode.TRANSPARENT

    def exit_transparent_mode(self):
        response = self._communicator.do_command(command=CoreAPI.set_slave_bus_mode(),
                                                 fields={'mode': CoreAPI.SlaveBusMode.LIVE})
        self._transparent_mode = response['mode'] == CoreAPI.SlaveBusMode.TRANSPARENT

    def __enter__(self):
        self.enter_transparent_mode()

    def __exit__(self, exc_type, exc_val, exc_tb):
        _ = exc_type, exc_val, exc_tb
        self.exit_transparent_mode()

    def do_command(self, address, command, fields, timeout=2):
        # type: (str, SlaveCommandSpec, Dict[str, Any], Optional[int]) -> Optional[Dict[str, Any]]
        """
        Send an slave command over the Communicator and block until an answer is received.
        If the Core does not respond within the timeout period, a CommunicationTimedOutException is raised
        """
        if not self._transparent_mode:
            raise RuntimeError('Transparent mode not active.')

        command.set_address(address)

        consumer = Consumer(command)
        self.register_consumer(consumer)

        master_timeout = False
        payload = command.create_request_payload(fields)
        if self._verbose:
            logger.info('Writing to slave transport:   Address: {0} - Data: {1}'.format(address, printable(payload)))
        try:
            self._communicator.do_command(command=CoreAPI.slave_tx_transport_message(len(payload)),
                                          fields={'payload': list(payload)},  # TODO: Remove list() once CoreCommunicator uses bytearrays
                                          timeout=timeout)
        except CommunicationTimedOutException as ex:
            logger.error('Internal timeout during slave transport: {0}'.format(ex))
            master_timeout = True

        try:
            if master_timeout:
                # When there's a communication timeout with the master, catch this exception and timeout the consumer
                # so it uses a flow expected by the caller
                return consumer.get(0)
            if timeout is not None and not consumer.send_only():
                return consumer.get(timeout)
        except CommunicationTimedOutException:
            self.unregister_consumer(consumer)
            raise
        return None

    def _process_transport_message(self, package):
        payload = bytearray(package['payload'])  # TODO: Remove bytearray() once the CoreCommunicator uses bytearrays
        if self._verbose:
            logger.info('Reading from slave transport: Data: {0}'.format(printable(payload)))

        self._read_buffer += payload
        if SlaveCommandSpec.RESPONSE_PREFIX not in self._read_buffer:
            return

        index = self._read_buffer.index(SlaveCommandSpec.RESPONSE_PREFIX)
        if index > 0:
            self._read_buffer = self._read_buffer[index:]

        consumed_bytes = 0
        for consumer in self._consumers[:]:
            consumed_bytes = consumer.suggest_payload(self._read_buffer)
            if consumed_bytes > 0:
                self.unregister_consumer(consumer)
                break
        self._read_buffer = self._read_buffer[max(len(SlaveCommandSpec.RESPONSE_PREFIX), consumed_bytes):]


class Consumer(object):
    """
    A consumer is registered to the read thread before a command is issued.  If an output
    matches the consumer, the output will unblock the get() caller.
    """

    def __init__(self, command):  # type: (SlaveCommandSpec) -> None
        self.command = command
        self._queue = Queue()  # type: Queue

    def suggest_payload(self, payload):  # type: (bytearray) -> int
        """ Consume payload if needed """
        if len(payload) < self.command.response_length:
            return 0
        calculated_hash = self.command.extract_hash_from_payload(payload)
        expected_hash = self.command.expected_response_hash
        if calculated_hash != expected_hash:
            return 0
        self._queue.put(self.command.consume_response_payload(payload[:self.command.response_length]))
        return self.command.response_length

    def send_only(self):  # type: () -> bool
        return len(self.command.response_fields) == 0

    def get(self, timeout):  # type: (int) -> Any
        """ Wait until the slave module replies or the timeout expires. """
        try:
            value = self._queue.get(timeout=timeout)
            if value is None:
                # No valid data could be received
                raise CommunicationTimedOutException('Empty or invalid slave data received')
            return value
        except Empty:
            raise CommunicationTimedOutException('No slave data received in {0}s'.format(timeout))
