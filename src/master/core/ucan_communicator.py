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
Module to communicate with the uCANs.
"""

from __future__ import absolute_import
import logging
import time
from six.moves.queue import Queue, Empty
from ioc import Injectable, Inject, INJECTED, Singleton
from master.core.core_api import CoreAPI
from master.core.core_communicator import CoreCommunicator, BackgroundConsumer
from master.core.exceptions import BootloadingException
from master.core.ucan_command import SID, UCANCommandSpec
from master.core.ucan_api import UCANAPI
from serial_utils import CommunicationTimedOutException, Printable

if False:  # MYPY
    from typing import Optional, Dict, Any, Union, Callable, List

logger = logging.getLogger(__name__)


@Injectable.named('ucan_communicator')
@Singleton
class UCANCommunicator(object):
    """
    Uses a CoreCommunicator to communicate with uCANs
    """

    # TODO: Hold communications when master is rebooting

    @Inject
    def __init__(self, master_communicator=INJECTED, verbose=False):  # type: (CoreCommunicator, bool) -> None
        """
        :param master_communicator: CoreCommunicator
        :param verbose: Log all communication
        """
        self._verbose = verbose
        self._communicator = master_communicator
        self._consumers = {}  # type: Dict[str, List[Union[Consumer, PalletConsumer]]]
        self._cc_pallet_mode = {}  # type: Dict[str, bool]

        self._background_consumer = BackgroundConsumer(CoreAPI.ucan_rx_transport_message(), 1, self._process_transport_message)
        self._communicator.register_consumer(self._background_consumer)

    def ping(self, cc_address, ucan_address, bootloader=False, ping_data=1, tries=3, warn=True):
        """
        Pings an uCAN in a certain mode
        """
        self.do_command(cc_address=cc_address,
                        command=UCANAPI.ping(SID.BOOTLOADER_COMMAND if bootloader else SID.NORMAL_COMMAND),
                        identity=ucan_address,
                        fields={'data': ping_data},
                        tries=tries,
                        warn=warn)

    def is_ucan_in_bootloader(self, cc_address, ucan_address):  # type: (str, str) -> bool
        """
        Figures out whether a uCAN is in bootloader or application mode. This can be a rather slow call since it might rely on a communication timeout
        :param cc_address: The address of the CAN Control
        :param ucan_address:  The address of the uCAN
        :return: Boolean, indicating whether the uCAN is in bootloader or not
        """
        try:
            self.ping(cc_address=cc_address,
                      ucan_address=ucan_address,
                      bootloader=False,
                      tries=2,
                      warn=False)
            return False
        except CommunicationTimedOutException:
            self.ping(cc_address=cc_address,
                      ucan_address=ucan_address,
                      bootloader=True,
                      tries=2,
                      warn=False)
            return True

    def register_consumer(self, consumer):  # type: (Union[Consumer, PalletConsumer]) -> None
        """ Register a consumer """
        self._consumers.setdefault(consumer.cc_address, []).append(consumer)

    def unregister_consumer(self, consumer):  # type: (Union[Consumer, PalletConsumer]) -> None
        """ Unregister a consumer """
        consumers = self._consumers.get(consumer.cc_address, [])
        if consumer in consumers:
            consumers.remove(consumer)

    def do_command(self, cc_address, command, identity, fields, timeout=2, tx_timeout=2, tries=3, warn=True):
        # type: (str, UCANCommandSpec, str, Dict[str, Any], Optional[int], Optional[int], int, bool) -> Optional[Dict[str, Any]]
        """
        Tries to send a uCAN command over the Communicator and block until an answer is received.
        Since communication to the uCANs seems to be unreliable every now and then, there is a build-in retry
        mechanism for now.
        """
        tries_counter = tries
        while True:
            try:
                response = self._do_command(cc_address=cc_address,
                                            command=command,
                                            identity=identity,
                                            fields=fields,
                                            timeout=timeout,
                                            tx_timeout=tx_timeout)
                if tries_counter != tries and warn:
                    logger.warning('Needed {0} tries to execute {1}'.format(tries - tries_counter + 1, command))
                return response
            except CommunicationTimedOutException:
                tries_counter -= 1
                if tries_counter == 0:
                    if warn:
                        logger.warning('Could not execute {0} in {1} tries'.format(command, tries))
                    raise
                time.sleep(tries - tries_counter)  # Gradually longer waits

    def _do_command(self, cc_address, command, identity, fields, timeout=2, tx_timeout=2):
        # type: (str, UCANCommandSpec, str, Dict[str, Any], Optional[int], Optional[int]) -> Optional[Dict[str, Any]]
        """
        Send a uCAN command over the Communicator and block until an answer is received.
        If the Core does not respond within the timeout period, a CommunicationTimedOutException is raised
        """
        if self._cc_pallet_mode.get(cc_address, False) is True:
            raise BootloadingException('CC {0} is currently bootloading'.format(cc_address))

        command.set_identity(identity)

        if command.sid == SID.BOOTLOADER_PALLET:
            consumer = PalletConsumer(cc_address, command, self._release_pallet_mode)  # type: Union[PalletConsumer, Consumer]
            self._cc_pallet_mode[cc_address] = True
        else:
            consumer = Consumer(cc_address, command)
        self.register_consumer(consumer)

        master_timeout = False
        for payload in command.create_request_payloads(identity, fields):
            if self._verbose:
                logger.info('Writing to uCAN transport:   CC %s - SID %s - Data: %s', cc_address, command.sid, Printable(payload))
            try:
                self._communicator.do_command(command=CoreAPI.ucan_tx_transport_message(),
                                              fields={'cc_address': cc_address,
                                                      'nr_can_bytes': len(payload),
                                                      'sid': command.sid,
                                                      'payload': payload + bytearray([0] * (8 - len(payload)))},
                                              timeout=tx_timeout if tx_timeout is not None else timeout)
            except CommunicationTimedOutException as ex:
                logger.error('Internal timeout during uCAN transport to CC {0}: {1}'.format(cc_address, ex))
                master_timeout = True
                break

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

    def _release_pallet_mode(self, cc_address):  # type: (str) -> None
        self._cc_pallet_mode[cc_address] = False

    def _process_transport_message(self, package):  # type: (Dict[str, Any]) -> None
        payload_length = package['nr_can_bytes']  # type: int
        payload = package['payload'][:payload_length]  # type: bytearray
        sid = package['sid']  # type: int
        cc_address = package['cc_address']  # type: str
        logger.debug('Reading from uCAN transport: CC %s - SID %s - Data: %s', cc_address, sid, Printable(payload))

        consumers = self._consumers.get(cc_address, [])
        for consumer in consumers[:]:
            if consumer.suggest_payload(payload):
                self.unregister_consumer(consumer)


class Consumer(object):
    """
    A consumer is registered to the read thread before a command is issued.  If an output
    matches the consumer, the output will unblock the get() caller.
    """

    def __init__(self, cc_address, command):  # type: (str, UCANCommandSpec) -> None
        self.cc_address = cc_address
        self.command = command
        self._queue = Queue()  # type: Queue[Dict[str, Any]]
        self._payload_set = {}  # type: Dict[int, bytearray]

    def suggest_payload(self, payload):  # type: (bytearray) -> bool
        """ Consume payload if needed """
        payload_hash = self.command.extract_hash(payload)
        if payload_hash in self.command.headers:
            self._payload_set[payload_hash] = payload
        if len(self._payload_set) == len(self.command.headers):
            response = self.command.consume_response_payload(self._payload_set)
            if response is None:
                return False
            self._queue.put(response)
            return True
        return False

    def send_only(self):  # type: () -> bool
        return len(self.command.response_instructions) == 0

    def get(self, timeout):  # type: (Union[int, float]) -> Dict[str, Any]
        """
        Wait until the uCAN (or CC) replies or the timeout expires.

        :param timeout: timeout in seconds
        :returns: dict containing the output fields of the command
        """
        try:
            value = self._queue.get(timeout=timeout)
            if value is None:
                # No valid data could be received
                raise CommunicationTimedOutException('Empty or invalid uCAN data received')
            return value
        except Empty:
            raise CommunicationTimedOutException('No uCAN data received in {0}s'.format(timeout))


class PalletConsumer(Consumer):
    """
    A pallet consumer is registered to the read thread before a command is issued.  If an output
    matches the consumer, the output will unblock the get() caller.
    """

    def __init__(self, cc_address, command, finished_callback):  # type: (str, UCANCommandSpec, Callable[[str], None]) -> None
        super(PalletConsumer, self).__init__(cc_address=cc_address,
                                             command=command)
        self._amount_of_segments = None
        self._finished_callback = finished_callback

    def suggest_payload(self, payload):
        """ Consume payload if needed """
        header = payload[0]
        first_segment = bool(header >> 7 & 1)
        segments_remaining = header & 127
        if first_segment:
            self._amount_of_segments = segments_remaining + 1
        segment_data = payload[1:]
        self._payload_set[segments_remaining] = segment_data
        if self._amount_of_segments is not None and sorted(self._payload_set.keys()) == list(range(self._amount_of_segments)):
            pallet = bytearray()
            for segment in sorted(list(self._payload_set.keys()), reverse=True):
                pallet += self._payload_set[segment]
            self._queue.put(self.command.consume_response_payload(pallet))
            return True
        return False

    def get(self, timeout):
        try:
            return super(PalletConsumer, self).get(timeout=timeout)
        finally:
            self._finished_callback(self.cc_address)

    def send_only(self):
        return False
