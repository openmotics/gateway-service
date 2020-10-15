# Copyright (C) 2016 OpenMotics BV
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
Module to communicate with the power modules.
"""
from __future__ import absolute_import

import logging
import time
from threading import RLock, Thread

from six.moves.queue import Empty

from gateway.hal.master_controller import CommunicationFailure
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject
from power import power_api
from power.power_command import PowerCommand
from power.time_keeper import TimeKeeper
from serial_utils import CommunicationStatus, CommunicationTimedOutException, \
    printable

if False:  # MYPY:
    from typing import Any, Dict, List, Literal, Optional, Tuple, Union
    from serial_utils import RS485
    from power.power_store import PowerStore
    DataType = Union[float, int, str]

    HEALTH = Literal['success', 'unstable', 'failure']

logger = logging.getLogger("openmotics")


class PowerCommunicator(object):
    """ Uses a serial port to communicate with the power modules. """

    @Inject
    def __init__(self, power_serial=INJECTED, power_store=INJECTED, pubsub=INJECTED, verbose=False, time_keeper_period=60,
                 address_mode_timeout=300):
        # type: (RS485, PowerStore, PubSub, bool, int, int) -> None
        """ Default constructor.

        :param power_serial: Serial port to communicate with
        :type power_serial: Instance of :class`RS485`
        :param verbose: Print all serial communication to stdout.
        """
        self.__serial = power_serial
        self.__serial_lock = RLock()
        self.__cid = 1

        self.__address_mode = False
        self.__address_mode_stop = False
        self.__address_thread = None  # type: Optional[Thread]
        self.__address_mode_timeout = address_mode_timeout
        self.__power_store = power_store
        self.__pubsub = pubsub

        self.__last_success = 0  # type: float

        if time_keeper_period != 0:
            self.__time_keeper = TimeKeeper(self, power_store, time_keeper_period)  # type: Optional[TimeKeeper]
        else:
            self.__time_keeper = None

        self.__communication_stats_calls = {'calls_succeeded': [],
                                            'calls_timedout': []}  # type: Dict[str, List]

        self.__communication_stats_bytes = {'bytes_written': 0,
                                            'bytes_read': 0}  # type: Dict[str, int]

        self.__debug_buffer = {'read': {},
                               'write': {}}  # type: Dict[str,Dict[float,str]]
        self.__debug_buffer_duration = 300

        self.__verbose = verbose

    def start(self):
        # type: () -> None
        """ Start the power communicator. """
        if self.__time_keeper is not None:
            self.__time_keeper.start()

    def stop(self):
        # type: () -> None
        if self.__time_keeper is not None:
            self.__time_keeper.stop()

    def get_communication_statistics(self):
        # type: () -> Dict[str, Any]
        ret = {}  # type: Dict[str, Any]
        ret.update(self.__communication_stats_calls)
        ret.update(self.__communication_stats_bytes)
        return ret

    def get_communicator_health(self):
        # type: () -> HEALTH
        stats = self.get_communication_statistics()
        calls_timedout = [call for call in stats['calls_timedout']]
        calls_succeeded = [call for call in stats['calls_succeeded']]

        if len(calls_timedout) == 0:
            # If there are no timeouts at all
            return CommunicationStatus.SUCCESS

        all_calls = sorted(calls_timedout + calls_succeeded)
        calls_last_x_minutes = [t for t in all_calls if t > time.time() - 180]
        ratio = len([t for t in calls_last_x_minutes if t in calls_timedout]) / float(len(calls_last_x_minutes))

        if len(all_calls) <= 10:
            # Not enough calls made to have a decent view on what's going on
            logger.warning('Observed energy communication failures, but not enough calls')
            return CommunicationStatus.UNSTABLE
        elif not any(t in calls_timedout for t in all_calls[-10:]):
            logger.warning('Observed energy communication failures, but recent calls recovered')
            # The last X calls are successfull
            return CommunicationStatus.UNSTABLE
        elif len(calls_last_x_minutes) <= 5:
            logger.warning('Observed energy communication failures, but not recent enough')
            # Not enough recent calls
            return CommunicationStatus.UNSTABLE
        elif ratio < 0.25:
            # Less than 25% of the calls fail, let's assume everything is just "fine"
            logger.warning('Observed energy communication failures, but there\'s only a failure ratio of {:.2f}%'.format(ratio * 100))
            return CommunicationStatus.UNSTABLE
        else:
            return CommunicationStatus.FAILURE

    def get_debug_buffer(self):
        # type: () -> Dict[str, Dict[Any, Any]]
        return self.__debug_buffer

    def get_seconds_since_last_success(self):
        # type: () -> float
        """ Get the number of seconds since the last successful communication. """
        if self.__last_success == 0:
            return 0  # No communication - return 0 sec since last success
        else:
            return time.time() - self.__last_success

    def __get_cid(self):
        # type: () -> int
        """ Get a communication id """
        (ret, self.__cid) = (self.__cid, (self.__cid % 255) + 1)
        return ret

    @staticmethod
    def __log(action, data):
        # type: (Optional[str]) -> None
        if data is not None:
            logger.info("%.3f %s power: %s" % (time.time(), action, printable(data)))

    def __write_to_serial(self, data):
        # type: (bytearray) -> None
        """ Write data to the serial port.

        :param data: the data to write
        """
        if self.__verbose:
            PowerCommunicator.__log('writing to', data)
        self.__serial.write(data)
        self.__communication_stats_bytes['bytes_written'] += len(data)
        threshold = time.time() - self.__debug_buffer_duration
        self.__debug_buffer['write'][time.time()] = printable(data)
        for t in self.__debug_buffer['write'].keys():
            if t < threshold:
                del self.__debug_buffer['write'][t]

    def do_command(self, address, cmd, *data):
        # type: (int, PowerCommand, DataType) -> Tuple[Any, ...]
        """ Send a command over the serial port and block until an answer is received.
        If the power module does not respond within the timeout period, a
        CommunicationTimedOutException is raised.

        :param address: Address of the power module
        :type address: 2 bytes string
        :param cmd: the command to execute
        :param data: data for the command
        :raises: :class`CommunicationTimedOutException` if power module did not respond in time
        :raises: :class`InAddressModeException` if communicator is in address mode
        :returns: dict containing the output fields of the command
        """
        if self.__address_mode:
            raise InAddressModeException()

        def do_once(_address, _cmd, *_data):
            # type: (int, PowerCommand, DataType) -> Tuple[Any, ...]
            """ Send the command once. """
            try:
                cid = self.__get_cid()
                send_data = _cmd.create_input(_address, cid, *_data)
                self.__write_to_serial(send_data)

                if _address == power_api.BROADCAST_ADDRESS:
                    self.__communication_stats_calls['calls_succeeded'].append(time.time())
                    self.__communication_stats_calls['calls_succeeded'] = self.__communication_stats_calls['calls_succeeded'][-50:]
                    return ()  # No reply on broadcast messages !
                else:
                    tries = 0
                    while True:
                        # In this loop we might receive data that didn't match the expected header. This might happen
                        # if we for some reason had a timeout on the previous call, and we now read the response
                        # to that call. In this case, we just re-try (up to 3 times), as the correct data might be
                        # next in line.
                        header, response_data = self.__read_from_serial()
                        if not _cmd.check_header(header, _address, cid):
                            if _cmd.is_nack(header, _address, cid) and response_data == bytearray([2]):
                                raise UnkownCommandException('Unknown command')
                            tries += 1
                            logger.warning("Header did not match command ({0})".format(tries))
                            if tries == 3:
                                raise Exception("Header did not match command ({0})".format(tries))
                        else:
                            break

                    self.__last_success = time.time()
                    return_data = _cmd.read_output(response_data)
                    self.__communication_stats_calls['calls_succeeded'].append(time.time())
                    self.__communication_stats_calls['calls_succeeded'] = self.__communication_stats_calls['calls_succeeded'][-50:]
                    return return_data
            except CommunicationTimedOutException:
                self.__communication_stats_calls['calls_timedout'].append(time.time())
                self.__communication_stats_calls['calls_timedout'] = self.__communication_stats_calls['calls_timedout'][-50:]
                raise

        with self.__serial_lock:
            try:
                return do_once(address, cmd, *data)
            except UnkownCommandException:
                # This happens when the module is stuck in the bootloader.
                logger.error("Got UnkownCommandException")
                do_once(address, power_api.bootloader_jump_application())
                time.sleep(1)
                return self.do_command(address, cmd, *data)
            except CommunicationTimedOutException:
                # Communication timed out, try again.
                return do_once(address, cmd, *data)
            except Exception as ex:
                logger.exception("Unexpected error: {0}".format(ex))
                time.sleep(0.25)
                return do_once(address, cmd, *data)

    def start_address_mode(self):
        # type: () -> None
        """ Start address mode.

        :raises: :class`InAddressModeException` if communicator is in maintenance mode.
        """
        if self.__address_mode:
            raise InAddressModeException()

        self.__address_mode = True
        self.__address_mode_stop = False

        with self.__serial_lock:
            self.__address_thread = Thread(target=self.__do_address_mode,
                                           name="PowerCommunicator address mode thread")
            self.__address_thread.daemon = True
            self.__address_thread.start()

    def __do_address_mode(self):
        # type: () -> None
        """ This code is running in a thread when in address mode. """
        if self.__power_store is None:
            self.__address_mode = False
            self.__address_thread = None
            return

        expire = time.time() + self.__address_mode_timeout
        address_mode = power_api.set_addressmode(power_api.ENERGY_MODULE)
        address_mode_p1c = power_api.set_addressmode(power_api.P1_CONCENTRATOR)
        want_an_address_8 = power_api.want_an_address(power_api.POWER_MODULE)
        want_an_address_12 = power_api.want_an_address(power_api.ENERGY_MODULE)
        want_an_address_p1c = power_api.want_an_address(power_api.P1_CONCENTRATOR)
        set_address = power_api.set_address(power_api.ENERGY_MODULE)
        set_address_p1c = power_api.set_address(power_api.P1_CONCENTRATOR)

        # AGT start
        data = address_mode.create_input(power_api.BROADCAST_ADDRESS,
                                         self.__get_cid(),
                                         power_api.ADDRESS_MODE)
        self.__write_to_serial(data)
        data = address_mode_p1c.create_input(power_api.BROADCAST_ADDRESS,
                                             self.__get_cid(),
                                             power_api.ADDRESS_MODE)
        self.__write_to_serial(data)

        # Wait for WAA and answer.
        while not self.__address_mode_stop and time.time() < expire:
            try:
                header, data = self.__read_from_serial()

                if set_address.check_header_partial(header) or set_address_p1c.check_header_partial(header):
                    continue

                version = None
                if want_an_address_8.check_header_partial(header):
                    version = power_api.POWER_MODULE
                elif want_an_address_12.check_header_partial(header):
                    version = power_api.ENERGY_MODULE
                elif want_an_address_p1c.check_header_partial(header):
                    version = power_api.P1_CONCENTRATOR

                if version is None:
                    logger.warning("Received unexpected message in address mode")
                else:
                    (old_address, cid) = (header[:2][1], header[2:3])
                    # Ask power_controller for new address, and register it.
                    new_address = self.__power_store.get_free_address()

                    if self.__power_store.module_exists(old_address):
                        self.__power_store.readdress_power_module(old_address, new_address)
                    else:
                        self.__power_store.register_power_module(new_address, version)

                    # Send new address to module
                    if version == power_api.P1_CONCENTRATOR:
                        address_data = set_address_p1c.create_input(old_address, ord(cid), new_address)
                    else:
                        # Both power- and energy module share the same API
                        address_data = set_address.create_input(old_address, ord(cid), new_address)
                    self.__write_to_serial(address_data)

            except CommunicationTimedOutException:
                pass  # Didn't receive a command, no problem.
            except Exception as exception:
                logger.exception("Got exception in address mode: %s", exception)

        # AGT stop
        data = address_mode.create_input(power_api.BROADCAST_ADDRESS,
                                         self.__get_cid(),
                                         power_api.NORMAL_MODE)
        self.__write_to_serial(data)
        data = address_mode_p1c.create_input(power_api.BROADCAST_ADDRESS,
                                             self.__get_cid(),
                                             power_api.NORMAL_MODE)
        self.__write_to_serial(data)

        self.__address_mode = False

    def stop_address_mode(self):
        # type: () -> None
        """ Stop address mode. """
        if not self.__address_mode:
            raise Exception("Not in address mode !")

        self.__address_mode_stop = True
        if self.__address_thread:
            self.__address_thread.join()
        self.__address_thread = None
        master_event = MasterEvent(MasterEvent.Types.POWER_ADDRESS_EXIT, {})
        self.__pubsub.publish_master_event(PubSub.MasterTopics.POWER, master_event)

    def in_address_mode(self):
        # type: () -> bool
        """ Returns whether the PowerCommunicator is in address mode. """
        return self.__address_mode

    def __read_from_serial(self):
        # type: () -> Tuple[bytearray, bytearray]
        """ Read a PowerCommand from the serial port. """
        phase = 0
        index = 0

        header = bytearray()
        length = 0
        data = bytearray()
        crc = 0

        command = bytearray()

        try:
            while phase < 8:
                byte = self.__serial.read_queue.get(True, 0.25)
                command += byte
                self.__communication_stats_bytes['bytes_read'] += 1

                if phase == 0:  # Skip non 'R' bytes
                    if byte == bytearray(b'R'):
                        phase = 1
                    else:
                        phase = 0
                elif phase == 1:  # Expect 'T'
                    if byte == bytearray(b'T'):
                        phase = 2
                    else:
                        raise Exception("Unexpected character")
                elif phase == 2:  # Expect 'R'
                    if byte == bytearray(b'R'):
                        phase = 3
                        index = 0
                    else:
                        raise Exception("Unexpected character")
                elif phase == 3:  # Read the header fields
                    header += byte
                    index += 1
                    if index == 8:
                        length = ord(byte)
                        if length > 0:
                            phase = 4
                            index = 0
                        else:
                            phase = 5
                elif phase == 4:  # Read the data
                    data += byte
                    index += 1
                    if index == length:
                        phase = 5
                elif phase == 5:  # Read the CRC code
                    crc = ord(byte)
                    phase = 6
                elif phase == 6:  # Expect '\r'
                    if byte == bytearray(b'\r'):
                        phase = 7
                    else:
                        raise Exception("Unexpected character")
                elif phase == 7:  # Expect '\n'
                    if byte == bytearray(b'\n'):
                        phase = 8
                    else:
                        raise Exception("Unexpected character")
            if PowerCommand.get_crc(header, data) != crc:
                raise Exception('CRC doesn\'t match')
        except Empty:
            raise CommunicationTimedOutException('Communication timed out')
        except Exception:
            if not self.__verbose:
                PowerCommunicator.__log('reading from', command)
            raise
        finally:
            if self.__verbose:
                PowerCommunicator.__log('reading from', command)

        threshold = time.time() - self.__debug_buffer_duration
        self.__debug_buffer['read'][time.time()] = printable(command)
        for t in self.__debug_buffer['read'].keys():
            if t < threshold:
                del self.__debug_buffer['read'][t]

        return header, data


class InAddressModeException(CommunicationFailure):
    """ Raised when the power communication is in address mode. """
    pass


class UnkownCommandException(CommunicationFailure):
    """ Raised when the power module responds with a NACK indicating an unkown command. """
    pass
