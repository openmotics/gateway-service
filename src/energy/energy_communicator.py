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

from gateway.daemon_thread import BaseThread
from gateway.hal.master_controller import CommunicationFailure
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from gateway.models import EnergyModule, EnergyCT, Module
from gateway.dto import ModuleDTO
from gateway.enums import EnergyEnums
from ioc import INJECTED, Inject
from energy.energy_api import EnergyAPI, BROADCAST_ADDRESS, NORMAL_MODE, ADDRESS_MODE
from energy.energy_command import EnergyCommand
from serial_utils import CommunicationStatus, CommunicationTimedOutException, \
    Printable

if False:  # MYPY:
    from typing import Any, Dict, List, Literal, Optional, Tuple, Union
    from serial_utils import RS485
    DataType = Union[float, int, str]

    HEALTH = Literal['success', 'unstable', 'failure']

logger = logging.getLogger(__name__)


class EnergyCommunicator(object):
    """ Uses a serial port to communicate with the power modules. """

    @Inject
    def __init__(self, energy_serial=INJECTED, pubsub=INJECTED, address_mode_timeout=300):
        # type: (RS485, PubSub, int) -> None
        self.__verbose = logger.level >= logging.DEBUG
        self.__serial = energy_serial
        self.__serial_lock = RLock()
        self.__cid = 1

        self.__address_mode = False
        self.__address_mode_stop = False
        self.__address_thread = None  # type: Optional[Thread]
        self.__address_mode_timeout = address_mode_timeout
        self.__pubsub = pubsub

        self.__last_success = 0  # type: float

        self.__communication_stats_calls = {'calls_succeeded': [],
                                            'calls_timedout': []}  # type: Dict[str, List]

        self.__communication_stats_bytes = {'bytes_written': 0,
                                            'bytes_read': 0}  # type: Dict[str, int]

        self.__debug_buffer = {'read': {},
                               'write': {}}  # type: Dict[str,Dict[float,str]]
        self.__debug_buffer_duration = 300

    def get_communication_statistics(self):
        # type: () -> Dict[str, Any]
        ret = {}  # type: Dict[str, Any]
        ret.update(self.__communication_stats_calls)
        ret.update(self.__communication_stats_bytes)
        return ret

    def reset_communication_statistics(self):
        # type: () -> None
        self.__communication_stats_calls = {'calls_succeeded': [],
                                            'calls_timedout': []}
        self.__communication_stats_bytes = {'bytes_written': 0,
                                            'bytes_read': 0}

    def get_communicator_health(self):
        # type: () -> HEALTH
        stats = self.get_communication_statistics()
        calls_timedout = [call for call in stats['calls_timedout']]
        calls_succeeded = [call for call in stats['calls_succeeded']]
        all_calls = sorted(calls_timedout + calls_succeeded)

        if len(calls_timedout) == 0:
            # If there are no timeouts at all
            return CommunicationStatus.SUCCESS

        if len(all_calls) <= 10:
            # Not enough calls made to have a decent view on what's going on
            logger.warning('Observed energy communication failures, but not enough calls')
            return CommunicationStatus.UNSTABLE

        calls_last_x_minutes = [t for t in all_calls if t > time.time() - 180]
        if len(calls_last_x_minutes) <= 5:
            # Not enough calls in the last 3 minutes to have a decent view on what's going on
            logger.warning('Observed energy communication failures, but not recent enough')
            return CommunicationStatus.UNSTABLE

        if len(all_calls) >= 30 and not any(t in calls_timedout for t in all_calls[-30:]):
            # The last 30 calls are successfull, consider "recoverd"
            return CommunicationStatus.SUCCESS
        if not any(t in calls_timedout for t in all_calls[-10:]):
            # The last 10 calls are successfull, consider "recovering"
            logger.warning('Observed energy communication failures, but recovering')
            return CommunicationStatus.UNSTABLE

        ratio = len([t for t in calls_last_x_minutes if t in calls_timedout]) / float(len(calls_last_x_minutes))
        if ratio < 0.25:
            # Less than 25% of the calls fail, let's assume everything is just "fine"
            logger.warning('Observed energy communication failures, but there\'s only a failure ratio of {:.2f}%'.format(ratio * 100))
            return CommunicationStatus.UNSTABLE

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

    def __debug(self, action, data):
        # type: (str, Optional[bytearray]) -> None
        if data is not None:
            logger.debug("%.3f %s power: %s", time.time(), action, Printable(data))

    def __write_to_serial(self, data):
        # type: (bytearray) -> None
        """ Write data to the serial port.

        :param data: the data to write
        """
        self.__debug('writing to', data)
        self.__serial.write(data)
        self.__communication_stats_bytes['bytes_written'] += len(data)
        threshold = time.time() - self.__debug_buffer_duration
        self.__debug_buffer['write'][time.time()] = str(Printable(data))
        for t in self.__debug_buffer['write'].keys():
            if t < threshold:
                del self.__debug_buffer['write'][t]

    def do_command(self, address, cmd, *data):
        # type: (int, EnergyCommand, DataType) -> Tuple[Any, ...]
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
            # type: (int, EnergyCommand, DataType) -> Tuple[Any, ...]
            """ Send the command once. """
            try:
                cid = self.__get_cid()
                send_data = _cmd.create_input(_address, cid, *_data)
                self.__write_to_serial(send_data)

                if _address == BROADCAST_ADDRESS:
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
                do_once(address, EnergyAPI.bootloader_jump_application())
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
            self.__address_thread = BaseThread(name='poweraddressmode', target=self.__do_address_mode)
            self.__address_thread.daemon = True
            self.__address_thread.start()

    def __do_address_mode(self):
        # type: () -> None
        """ This code is running in a thread when in address mode. """
        expire = time.time() + self.__address_mode_timeout
        address_mode = EnergyAPI.set_addressmode(EnergyEnums.Version.ENERGY_MODULE)
        address_mode_p1c = EnergyAPI.set_addressmode(EnergyEnums.Version.P1_CONCENTRATOR)
        want_an_address_8 = EnergyAPI.want_an_address(EnergyEnums.Version.POWER_MODULE)
        want_an_address_12 = EnergyAPI.want_an_address(EnergyEnums.Version.ENERGY_MODULE)
        want_an_address_p1c = EnergyAPI.want_an_address(EnergyEnums.Version.P1_CONCENTRATOR)
        set_address = EnergyAPI.set_address(EnergyEnums.Version.ENERGY_MODULE)
        set_address_p1c = EnergyAPI.set_address(EnergyEnums.Version.P1_CONCENTRATOR)

        # AGT start
        data = address_mode.create_input(BROADCAST_ADDRESS, self.__get_cid(), ADDRESS_MODE)
        self.__write_to_serial(data)
        data = address_mode_p1c.create_input(BROADCAST_ADDRESS, self.__get_cid(),ADDRESS_MODE)
        self.__write_to_serial(data)

        # Wait for WAA and answer.
        while not self.__address_mode_stop and time.time() < expire:
            try:
                header, data = self.__read_from_serial()

                if set_address.check_header_partial(header) or set_address_p1c.check_header_partial(header):
                    continue

                version = None
                if want_an_address_8.check_header_partial(header):
                    version = EnergyEnums.Version.POWER_MODULE
                elif want_an_address_12.check_header_partial(header):
                    version = EnergyEnums.Version.ENERGY_MODULE
                elif want_an_address_p1c.check_header_partial(header):
                    version = EnergyEnums.Version.P1_CONCENTRATOR

                if version is None:
                    logger.warning("Received unexpected message in address mode")
                else:
                    (old_address, cid) = (header[:2][1], header[2:3])

                    # Make sure the module is registered in the ORM
                    new_address, old_module = EnergyCommunicator._get_address_and_module(old_address)
                    if old_module is None:
                        module = Module(source=ModuleDTO.Source.GATEWAY,
                                        address=str(new_address),
                                        hardware_type=ModuleDTO.HardwareType.PHYSICAL)
                        module.save()
                        energy_module = EnergyModule(number=new_address,
                                                     version=version,
                                                     module=module)
                        energy_module.save()
                        for port_id in range(EnergyEnums.NUMBER_OF_PORTS[version]):
                            ct = EnergyCT(number=port_id,
                                          sensor_type=2,  # Default of 12.5A
                                          times='',  # No times by default (all night)
                                          energy_module=energy_module)
                            ct.save()

                    # Send new address to module
                    if version == EnergyEnums.Version.P1_CONCENTRATOR:
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
        data = address_mode.create_input(BROADCAST_ADDRESS, self.__get_cid(), NORMAL_MODE)
        self.__write_to_serial(data)
        data = address_mode_p1c.create_input(BROADCAST_ADDRESS, self.__get_cid(), NORMAL_MODE)
        self.__write_to_serial(data)

        self.__address_mode = False

    @staticmethod
    def _get_address_and_module(old_address):
        modules = Module.select().where(Module.source == ModuleDTO.Source.GATEWAY,
                                        Module.hardware_type == ModuleDTO.HardwareType.PHYSICAL)
        new_address = 2
        old_module = None  # type: Optional[Module]
        if len(modules) > 0:
            matching_modules = [module for module in modules if module.address == str(old_address)]
            old_module = None if len(matching_modules) == 0 else matching_modules[0]
            if old_module is None:
                existing_addresses = [int(module.address) for module in modules]
                while new_address in existing_addresses and new_address < 255:
                    new_address += 1
                if new_address == 255:
                    raise RuntimeError('No free EnergyModule address found')
            else:
                new_address = int(old_module.address)

        return new_address, old_module

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
        """ Returns whether the EnergyCommunicator is in address mode. """
        return self.__address_mode

    def __read_from_serial(self):
        # type: () -> Tuple[bytearray, bytearray]
        """ Read a EnergyCommand from the serial port. """
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
            if EnergyCommand.get_crc(header, data) != crc:
                raise Exception('CRC doesn\'t match')
        except Empty:
            raise CommunicationTimedOutException('Communication timed out')
        except Exception:
            self.__debug('reading from', command)
            raise
        finally:
            self.__debug('reading from', command)

        threshold = time.time() - self.__debug_buffer_duration
        self.__debug_buffer['read'][time.time()] = str(Printable(command))
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
