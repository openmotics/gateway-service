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
from ioc import Inject, INJECTED
from master.core.core_communicator import CoreCommunicator
from master.core.core_api import CoreAPI
from master.maintenance_communicator import MaintenanceCommunicator
from logs import Logs
from platform_utils import Hardware

if False:  # MYPY
    from typing import Optional
    from serial import Serial
    from logging import Logger

# Different name to reduce confusion between multiple used loggers
global_logger = logging.getLogger(__name__)


class CoreUpdater(object):
    """
    This is a class holding tools to execute Core updates
    """

    BOOTLOADER_SERIAL_READ_TIMEOUT = 3
    POST_BOOTLOAD_DELAY = 2.0
    APPLICATION_STARTUP_DELAY = 5.0
    POWER_CYCLE_DELAY = 2.0

    @staticmethod
    @Inject
    def update(hex_filename, version, raise_exception=False, master_communicator=INJECTED, maintenance_communicator=INJECTED, cli_serial=INJECTED):
        # type: (str, str, bool, CoreCommunicator, MaintenanceCommunicator, Serial) -> bool
        """ Flashes the content from an Intel HEX file to the Core """
        component_logger = Logs.get_update_logger('master_coreplus')
        try:
            # TODO: Check version and skip update if the version is already active

            component_logger.info('Updating Core')

            master_communicator = master_communicator
            maintenance_communicator = maintenance_communicator

            if master_communicator is not None and not master_communicator.is_running():
                master_communicator.start()

            current_version = None  # type: Optional[str]
            try:
                current_version = master_communicator.do_command(CoreAPI.get_firmware_version(), {})['version']
                component_logger.info('Current firmware version: {0}'.format(current_version))
            except Exception as ex:
                component_logger.warning('Could not load current firmware version: {0}'.format(ex))

            if current_version is not None and version == current_version:
                component_logger.info('Firmware up-to-date, skipping')
                return True

            component_logger.info('Updating firmware from {0} to {1}'.format(current_version if current_version is not None else 'unknown',
                                                                             version if version is not None else 'unknown'))

            if master_communicator is not None and maintenance_communicator is not None:
                maintenance_communicator.stop()
                master_communicator.stop()

            if not os.path.exists(hex_filename):
                raise RuntimeError('The given path does not point to an existing file')
            _ = IntelHex(hex_filename)  # Using the IntelHex library to validate content validity
            with open(hex_filename, 'r') as hex_file:
                hex_lines = hex_file.readlines()

            component_logger.info('Verify bootloader communications')
            bootloader_version = CoreUpdater._in_bootloader(serial=cli_serial,
                                                            logger=component_logger)
            if bootloader_version is not None:
                component_logger.info('Bootloader {0} active'.format(bootloader_version))
            else:
                component_logger.info('Bootloader not active, switching to bootloader')
                Hardware.cycle_gpio(Hardware.GPIO.CORE_POWER, [False, CoreUpdater.POWER_CYCLE_DELAY, True])
                CoreUpdater._wait_for(serial=cli_serial,
                                      entry='DS30HexLoader',
                                      logger=component_logger)
                bootloader_version = CoreUpdater._in_bootloader(serial=cli_serial,
                                                                logger=component_logger)
                if bootloader_version is None:
                    raise RuntimeError('Could not enter bootloader')
                component_logger.info('Bootloader {0} active'.format(bootloader_version))

            component_logger.info('Flashing contents of {0}'.format(os.path.basename(hex_filename)))
            component_logger.info('Flashing...')
            amount_lines = len(hex_lines)
            for index, line in enumerate(hex_lines):
                cli_serial.write(bytearray(ord(c) for c in line))
                response = CoreUpdater._read_line(serial=cli_serial,
                                                  logger=component_logger)
                if response.startswith('nok'):
                    raise RuntimeError('Unexpected NOK while flashing: {0}'.format(response))
                if not response.startswith('ok'):
                    raise RuntimeError('Unexpected answer while flashing: {0}'.format(response))
                if index % (amount_lines // 10) == 0 and index != 0:
                    component_logger.info('Flashing... {0}%'.format(index * 10 // (amount_lines // 10)))
            component_logger.info('Flashing... Done')

            component_logger.info('Post-flash power cycle')
            time.sleep(CoreUpdater.POST_BOOTLOAD_DELAY)
            Hardware.cycle_gpio(Hardware.GPIO.CORE_POWER, [False, CoreUpdater.POWER_CYCLE_DELAY, True])
            time.sleep(CoreUpdater.APPLICATION_STARTUP_DELAY)  # TODO: Replace with monitoring the CLI for "startup completed" message

            component_logger.info('Verify Core communication')
            if master_communicator is not None and maintenance_communicator is not None:
                maintenance_communicator.start()
                master_communicator.start()

            current_version = None
            try:
                current_version = master_communicator.do_command(CoreAPI.get_firmware_version(), {})['version']
                component_logger.info('Post-update firmware version: {0}'.format(current_version))
            except Exception as ex:
                component_logger.warning('Could not load post-update firmware version: {0}'.format(ex))
            if version is not None and current_version != version:
                raise RuntimeError('Post-update firmware version {0} does not match expected {1}'.format(
                    current_version if current_version is not None else 'unknown',
                    version
                ))

            component_logger.info('Update completed')
            return True
        except Exception as ex:
            component_logger.error('Error flashing: {0}'.format(ex))
            if raise_exception:
                raise
            return False

    @staticmethod
    def _wait_for(serial, entry, logger):  # type: (Serial, str, Logger) -> None
        output = ''
        while entry not in output:
            output = CoreUpdater._read_line(serial=serial,
                                            logger=logger)

    @staticmethod
    def _in_bootloader(serial, logger):  # type: (Serial, Logger) -> Optional[str]
        serial.flushInput()
        serial.write(b'hi\n')
        response = CoreUpdater._read_line(serial=serial,
                                          logger=logger)
        serial.flushInput()
        if not response.startswith('hi;ver='):
            return None
        return response.split('=')[-1]

    @staticmethod
    def _read_line(serial, logger, discard_lines=0):  # type: (Serial, Logger, int) -> str
        timeout = time.time() + CoreUpdater.BOOTLOADER_SERIAL_READ_TIMEOUT
        line = ''
        while time.time() < timeout:
            if serial.inWaiting():
                data = bytearray(serial.read(1))
                line += chr(data[0])
                if data == bytearray(b'\n'):
                    if line[0] == '#':
                        logger.debug('* Debug: {0}'.format(line.strip()))
                        line = ''
                    elif discard_lines == 0:
                        return line.strip()
                    else:
                        discard_lines -= 1
                        line = ''
        raise RuntimeError('Timeout while communicating with Core bootloader')
