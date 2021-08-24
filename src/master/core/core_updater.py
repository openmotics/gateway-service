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

if False:  # MYPY
    from typing import Optional
    from serial import Serial
    from logging import Logger

logger = logging.getLogger(__name__)


class CoreUpdater(object):
    """
    This is a class holding tools to execute Core updates
    """

    BOOTLOADER_SERIAL_READ_TIMEOUT = 3
    ENTER_BOOTLOADER_DELAY = 1.5
    ENTER_APPLICATION_DELAY = 5.0

    @staticmethod
    @Inject
    def update(hex_filename, version, raise_exception=False, master_communicator=INJECTED, maintenance_communicator=INJECTED, cli_serial=INJECTED):
        # type: (str, str, bool, CoreCommunicator, MaintenanceCommunicator, Serial) -> bool
        """ Flashes the content from an Intel HEX file to the Core """
        logger_ = Logs.get_update_logger('master_coreplus')
        try:
            # TODO: Check version and skip update if the version is already active

            logger_.info('Updating Core')

            master_communicator = master_communicator
            maintenance_communicator = maintenance_communicator

            if master_communicator is not None and not master_communicator.is_running():
                master_communicator.start()

            current_version = None  # type: Optional[str]
            try:
                current_version = master_communicator.do_command(CoreAPI.get_firmware_version(), {})['version']
                logger_.info('Current firmware version: {0}'.format(current_version))
            except Exception as ex:
                logger_.warning('Could not load current firmware version: {0}'.format(ex))

            if current_version is not None and version == current_version:
                logger_.info('Firmware up-to-date, skipping')
                return True

            logger_.info('Updating firmware from {0} to {1}'.format(current_version if current_version is not None else 'unknown',
                                                                    version if version is not None else 'unknown'))

            if master_communicator is not None and maintenance_communicator is not None:
                maintenance_communicator.stop()
                master_communicator.stop()

            if not os.path.exists(hex_filename):
                raise RuntimeError('The given path does not point to an existing file')
            _ = IntelHex(hex_filename)  # Using the IntelHex library to validate content validity
            with open(hex_filename, 'r') as hex_file:
                hex_lines = hex_file.readlines()

            logger_.info('Verify bootloader communications')
            bootloader_version = CoreUpdater._in_bootloader(cli_serial, logger_)
            if bootloader_version is not None:
                logger_.info('Bootloader {0} active'.format(bootloader_version))
            else:
                logger_.info('Bootloader not active, switching to bootloader')
                cli_serial.write(b'reset\r\n')
                time.sleep(CoreUpdater.ENTER_BOOTLOADER_DELAY)
                bootloader_version = CoreUpdater._in_bootloader(cli_serial, logger_)
                if bootloader_version is None:
                    raise RuntimeError('Could not enter bootloader')
                logger_.info('Bootloader {0} active'.format(bootloader_version))

            logger_.info('Flashing contents of {0}'.format(os.path.basename(hex_filename)))
            logger_.info('Flashing...')
            amount_lines = len(hex_lines)
            for index, line in enumerate(hex_lines):
                cli_serial.write(bytearray(ord(c) for c in line))
                response = CoreUpdater._read_line(cli_serial, logger_)
                if response.startswith('nok'):
                    raise RuntimeError('Unexpected NOK while flashing: {0}'.format(response))
                if not response.startswith('ok'):
                    raise RuntimeError('Unexpected answer while flashing: {0}'.format(response))
                if index % (amount_lines // 10) == 0 and index != 0:
                    logger_.info('Flashing... {0}%'.format(index * 10 // (amount_lines // 10)))
            logger_.info('Flashing... Done')

            logger_.info('Verify Core communication')
            time.sleep(CoreUpdater.ENTER_APPLICATION_DELAY)
            if CoreUpdater._in_bootloader(cli_serial, logger_):
                raise RuntimeError('Still in bootloader')

            if master_communicator is not None and maintenance_communicator is not None:
                maintenance_communicator.start()
                master_communicator.start()

            current_version = None
            try:
                current_version = master_communicator.do_command(CoreAPI.get_firmware_version(), {})['version']
                logger_.info('Post-update firmware version: {0}'.format(current_version))
            except Exception as ex:
                logger_.warning('Could not load post-update firmware version: {0}'.format(ex))
            if version is not None and current_version != version:
                raise RuntimeError('Post-update firmware version {0} does not match expected {1}'.format(
                    current_version if current_version is not None else 'unknown',
                    version
                ))

            logger_.info('Update completed')
            return True
        except Exception as ex:
            logger_.error('Error flashing: {0}'.format(ex))
            if raise_exception:
                raise
            return False

    @staticmethod
    def _in_bootloader(serial, logger_):  # type: (Serial, Logger) -> Optional[str]
        serial.flushInput()
        serial.write(b'hi\n')
        response = CoreUpdater._read_line(serial, logger_)
        serial.flushInput()
        if not response.startswith('hi;ver='):
            return None
        return response.split('=')[-1]

    @staticmethod
    def _read_line(serial, logger_, discard_lines=0):  # type: (Serial, Logger, int) -> str
        timeout = time.time() + CoreUpdater.BOOTLOADER_SERIAL_READ_TIMEOUT
        line = ''
        while time.time() < timeout:
            if serial.inWaiting():
                data = bytearray(serial.read(1))
                line += chr(data[0])
                if data == bytearray(b'\n'):
                    if line[0] == '#':
                        logger_.debug('* Debug: {0}'.format(line.strip()))
                        line = ''
                    elif discard_lines == 0:
                        return line.strip()
                    else:
                        discard_lines -= 1
                        line = ''
        raise RuntimeError('Timeout while communicating with Core bootloader')
