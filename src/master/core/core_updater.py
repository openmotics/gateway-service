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
Module to work update a Core
"""

from __future__ import absolute_import
import logging
import os
import time
from intelhex import IntelHex
from ioc import Inject, INJECTED, Singleton, Injectable
from threading import Event as ThreadingEvent
from master.core.events import Event as MasterCoreEvent
from master.core.core_communicator import CoreCommunicator, BackgroundConsumer, CommunicationBlocker
from master.core.core_api import CoreAPI
from master.maintenance_communicator import MaintenanceCommunicator
from logs import Logs
from platform_utils import Hardware

if False:  # MYPY
    from typing import Optional, List
    from serial import Serial
    from logging import Logger

# Different name to reduce confusion between multiple used loggers
global_logger = logging.getLogger(__name__)


@Injectable.named('core_updater')
@Singleton
class CoreUpdater(object):
    """
    This is a class holding tools to execute Core updates
    """

    BOOTLOADER_SERIAL_READ_TIMEOUT = 5
    POST_BOOTLOAD_DELAY = 2.0
    APPLICATION_STARTUP_TIMEOUT = 30.0
    POWER_CYCLE_DELAY = 2.0

    ENTER_BOOTLOADER_TRIES = 5
    BLOCK_WRITE_TRIES = 5

    @Inject
    def __init__(self, master_communicator=INJECTED, maintenance_communicator=INJECTED, cli_serial=INJECTED):
        # type: (CoreCommunicator, MaintenanceCommunicator, Serial) -> None
        self._master_communicator = master_communicator
        self._maintenance_communicator = maintenance_communicator
        self._cli_serial = cli_serial

        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
        )
        self._master_started = ThreadingEvent()
        self._master_started.set()

    def _handle_event(self, data):
        core_event = MasterCoreEvent(data)
        if core_event.type == MasterCoreEvent.Types.SYSTEM:
            if core_event.data.get('type') == MasterCoreEvent.SystemEventTypes.STARTUP_COMPLETED:
                self._master_started.set()

    def update(self, hex_filename, version, ):
        # type: (str, str) -> None
        """ Flashes the content from an Intel HEX file to the Core """
        component_logger = Logs.get_update_logger('master_coreplus')
        component_logger.info('Updating Core')
        start_time = time.time()

        communication_tracing = []
        try:
            if self._master_communicator is not None and not self._master_communicator.is_running():
                self._master_communicator.start()

            current_version = None  # type: Optional[str]
            try:
                current_version = self._master_communicator.do_command(command=CoreAPI.get_firmware_version(),
                                                                       fields={},
                                                                       bypass_blockers=[CommunicationBlocker.UPDATE])['version']
                component_logger.info('Current firmware version: {0}'.format(current_version))
            except Exception as ex:
                component_logger.warning('Could not load current firmware version: {0}'.format(ex))

            component_logger.info('Updating firmware from {0} to {1}'.format(current_version if current_version is not None else 'unknown',
                                                                             version if version is not None else 'unknown'))

            if self._master_communicator is not None and self._maintenance_communicator is not None:
                self._maintenance_communicator.stop()
                self._master_communicator.stop()

            if not os.path.exists(hex_filename):
                raise RuntimeError('The given path does not point to an existing file')
            _ = IntelHex(hex_filename)  # Using the IntelHex library to validate content validity
            with open(hex_filename, 'r') as hex_file:
                hex_lines = hex_file.readlines()

            component_logger.info('Switching to bootloader')
            tries = CoreUpdater.ENTER_BOOTLOADER_TRIES
            while True:
                try:
                    self._cli_serial.flushInput()
                    Hardware.cycle_gpio(Hardware.CoreGPIO.MASTER_POWER, [False, CoreUpdater.POWER_CYCLE_DELAY, True])
                    bootloader_version = self._wait_for_response(tracing=communication_tracing)
                    if bootloader_version is None:
                        raise RuntimeError('Could not enter bootloader')
                    component_logger.info('Bootloader {0} active'.format(bootloader_version))
                    break
                except Exception:
                    tries -= 1
                    if tries == 0:
                        raise
                    component_logger.warning('Could not enter bootloader, trying again')

            component_logger.info('Flashing contents of {0}'.format(os.path.basename(hex_filename)))
            component_logger.info('Flashing...')
            amount_lines = len(hex_lines)
            for index, line in enumerate(hex_lines):
                tries = CoreUpdater.BLOCK_WRITE_TRIES
                while True:
                    try:
                        self._write_line(line=line, tracing=communication_tracing)
                        response = self._wait_for_response(tracing=communication_tracing)
                        if response.startswith('nok'):
                            raise RuntimeError('Unexpected NOK while flashing: {0}'.format(response))
                        if not response.startswith('ok'):
                            raise RuntimeError('Unexpected answer while flashing: {0}'.format(response))
                        break
                    except RuntimeError as ex:
                        tries -= 1
                        component_logger.warning('Flashing... Line {0}/{1} failed: {2}'.format(index, amount_lines, ex))
                        self._wait_for_response(tracing=communication_tracing)
                        if tries == 0:
                            raise
                if index % (amount_lines // 10) == 0 and index != 0:
                    component_logger.info('Flashing... {0}%'.format(index * 10 // (amount_lines // 10)))
            component_logger.info('Flashing... Done')

            component_logger.info('Post-flash power cycle')
            time.sleep(CoreUpdater.POST_BOOTLOAD_DELAY)
            Hardware.set_gpio(Hardware.CoreGPIO.MASTER_POWER, False)

            time.sleep(CoreUpdater.POWER_CYCLE_DELAY / 2)
            if self._master_communicator is not None and self._maintenance_communicator is not None:
                self._maintenance_communicator.start()
                self._master_communicator.start()
            time.sleep(CoreUpdater.POWER_CYCLE_DELAY / 2)

            component_logger.info('Waiting for startup')
            self._master_started.clear()
            Hardware.set_gpio(Hardware.CoreGPIO.MASTER_POWER, True)
            if not self._master_started.wait(CoreUpdater.APPLICATION_STARTUP_TIMEOUT):
                raise RuntimeError('Core was not started after {0}s'.format(CoreUpdater.APPLICATION_STARTUP_TIMEOUT))
            component_logger.info('Startup complete')

            current_version = None
            try:
                current_version = self._master_communicator.do_command(command=CoreAPI.get_firmware_version(),
                                                                       fields={},
                                                                       bypass_blockers=[CommunicationBlocker.UPDATE])['version']
                component_logger.info('Post-update firmware version: {0}'.format(current_version))
            except Exception as ex:
                component_logger.warning('Could not load post-update firmware version: {0}'.format(ex))
            if version is not None and current_version != version:
                raise RuntimeError('Post-update firmware version {0} does not match expected {1}'.format(
                    current_version if current_version is not None else 'unknown',
                    version
                ))

            component_logger.info('Update completed. Took {0:.1f}s'.format(time.time() - start_time))
        except Exception:
            if communication_tracing:
                component_logger.info('Dumping communication trace:')
                for line in communication_tracing:  # [-10:]:
                    component_logger.info(line)
            raise

    def _wait_for_response(self, tracing):  # type: (List[str]) -> Optional[str]
        line = self._read_line(tracing=tracing)
        if 'DS30HexLoader' in line:
            self._write_line('hi\n', tracing=tracing)
            line = self._read_line(tracing=tracing)
            if not line.startswith('hi;ver='):
                raise RuntimeError('Unexpected response on hi: {0}'.format(line))
            return line.split('=')[-1]
        return line

    def _write_line(self, line, tracing):  # type: (str, List[str]) -> None
        tracing.append('> {0}'.format(line.strip()))
        self._cli_serial.write(bytearray(ord(i) for i in line))
        self._cli_serial.flushOutput()

    def _read_line(self, tracing):  # type: (List[str]) -> str
        timeout = time.time() + CoreUpdater.BOOTLOADER_SERIAL_READ_TIMEOUT
        line = ''
        while time.time() < timeout:
            bytes_waiting = self._cli_serial.inWaiting()
            if bytes_waiting:
                line += bytearray(self._cli_serial.read(bytes_waiting)).decode()
                if line[-1] == '\n':
                    tracing.append('< {0}'.format(line.strip()))
                    if line[0] != '#':
                        return line.strip()
                    line = ''
        raise RuntimeError('Timeout while communicating with Core bootloader')
