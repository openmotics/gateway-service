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
from master.core.maintenance import MaintenanceCommunicator

if False:  # MYPY
    from typing import Optional
    from serial.serialposix import Serial

logger = logging.getLogger('openmotics')


class CoreUpdater(object):
    """
    This is a class holding tools to execute Core updates
    """

    BOOTLOADER_SERIAL_READ_TIMEOUT = 3
    RESET_DELAY = 2

    @staticmethod
    @Inject
    def update(hex_filename, master_communicator=INJECTED, maintenance_communicator=INJECTED, cli_serial=INJECTED):
        # type: (str, CoreCommunicator, MaintenanceCommunicator, Serial) -> bool
        """ Flashes the content from an Intel HEX file to the Core """
        try:
            # TODO: Check version and skip update if the version is already active

            logger.info('Updating Core')

            master_communicator = master_communicator
            maintenance_communicator = maintenance_communicator

            if master_communicator is not None and maintenance_communicator is not None:
                maintenance_communicator.stop()
                # master_communicator.stop()  # TODO: Hold the communicator

            if not os.path.exists(hex_filename):
                raise RuntimeError('The given path does not point to an existing file')
            _ = IntelHex(hex_filename)  # Using the IntelHex library to validate content validity
            with open(hex_filename, 'r') as hex_file:
                hex_lines = hex_file.readlines()

            logger.info('Verify bootloader communications')
            bootloader_version = CoreUpdater._in_bootloader(cli_serial)
            if bootloader_version is not None:
                logger.info('Bootloader {0} active'.format(bootloader_version))
            else:
                logger.info('Bootloader not active, switching to bootloader')
                cli_serial.write('reset\r\n')
                time.sleep(CoreUpdater.RESET_DELAY)
                bootloader_version = CoreUpdater._in_bootloader(cli_serial)
                if bootloader_version is None:
                    raise RuntimeError('Could not enter bootloader')
                logger.info('Bootloader {0} active'.format(bootloader_version))

            logger.info('Flashing contents of {0}'.format(os.path.basename(hex_filename)))
            logger.info('Flashing...')
            amount_lines = len(hex_lines)
            for index, line in enumerate(hex_lines):
                cli_serial.write(line)
                response = CoreUpdater._read_line(cli_serial)
                if response.startswith('nok'):
                    raise RuntimeError('Unexpected NOK while flashing: {0}'.format(response))
                if not response.startswith('ok'):
                    raise RuntimeError('Unexpected answer while flashing: {0}'.format(response))
                if index % int(amount_lines / 10) == 0 and index != 0:
                    logger.debug('Flashing... {0}%'.format(int(index * 100 / amount_lines)))
            logger.info('Flashing... Done')

            logger.info('Verify Core communication')
            time.sleep(CoreUpdater.RESET_DELAY)
            if CoreUpdater._in_bootloader(cli_serial):
                raise RuntimeError('Still in bootloader')
            cli_serial.write('firmware version\r\n')
            firmware_version = CoreUpdater._read_line(cli_serial, discard_lines=2)
            logger.info('Application version {0} active'.format(firmware_version))
            cli_serial.flushInput()

            if master_communicator is not None and maintenance_communicator is not None:
                maintenance_communicator.start()
                # master_communicator.start()  # TODO: Make sure it can start again

            # TODO: Also verify CoreCommunicator / API

            logger.info('Update completed')
            return True
        except Exception as ex:
            logger.error('Error flashing: {0}'.format(ex))
            return False

    @staticmethod
    def _in_bootloader(serial):  # type: (Serial) -> Optional[str]
        serial.flushInput()
        serial.write('hi\n')
        response = CoreUpdater._read_line(serial)
        serial.flushInput()
        if not response.startswith('hi;ver='):
            return None
        return response.split('=')[-1]

    @staticmethod
    def _read_line(serial, verbose=True, discard_lines=0):  # type: (Serial, bool, int) -> str
        timeout = time.time() + CoreUpdater.BOOTLOADER_SERIAL_READ_TIMEOUT
        line = ''
        while time.time() < timeout:
            if serial.inWaiting():
                char = serial.read(1)
                line += char
                if char == '\n':
                    if line[0] == '#' and verbose:
                        logger.debug('* Debug: {0}'.format(line.strip()))
                        line = ''
                    elif discard_lines == 0:
                        return line.strip()
                    else:
                        discard_lines -= 1
                        line = ''
        raise RuntimeError('Timeout while communicating with Core bootloader')
