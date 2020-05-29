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
Module to update an RS485 slave module
"""

from __future__ import absolute_import
import logging
import os
import time
from intelhex import IntelHex
from ioc import Inject, INJECTED
from master.core.rs485_communicator import RS485Communicator, CommunicationTimedOutException
from master.core.rs485_api import RS485API

logger = logging.getLogger('openmotics')

if False:  # MYPY
    from typing import Tuple, Optional, List, Dict, Any


class RS485Updater(object):
    """
    This is a class holding tools to execute RS485 slave updates
    """

    BLOCKS_SMALL_SLAVE = 410
    BLOCKS_LARGE_SLAVE = 922
    BOOTLOADER_TIMEOUT = 10
    WRITE_FLASH_BLOCK_TIMEOUT = 10
    SWITCH_MODE_TIMEOUT = 10
    BLOCK_SIZE = 64

    @staticmethod
    @Inject
    def update(address, hex_filename, version, rs485_communicator=INJECTED):  # type: (str, str, str, RS485Communicator) -> bool
        """ Flashes the content from an Intel HEX file to a slave module """
        try:
            with rs485_communicator:
                logger.info('Updating RS485 slave')

                if not os.path.exists(hex_filename):
                    raise RuntimeError('The given path does not point to an existing file')
                firmware = IntelHex(hex_filename)  # Using the IntelHex library read and validate contents

                logger.info('{0} - Loading current firmware version'.format(address))
                current_version = RS485Updater._get_version(rs485_communicator, address, tries=30)
                if current_version is None:
                    logger.info('{0} - Could not request current firmware version'.format(address))
                    logger.info('{0} - Module does not support bootloading. Skipping'.format(address))
                    return True  # This is considered "success" as it's nothing that can "fixed"
                firmware_version, hardware_version = current_version
                logger.info('{0} - Current version: {1} ({2})'.format(address, firmware_version, hardware_version))

                if version == firmware_version:
                    logger.info('{0} - Already up-to-date. Skipping'.format(address))
                    return True

                logger.info('{0} - Entering bootloader'.format(address))
                try:
                    response = rs485_communicator.do_command(address=address,
                                                             command=RS485API.goto_bootloader(),
                                                             fields={'timeout': RS485Updater.BOOTLOADER_TIMEOUT},
                                                             timeout=RS485Updater.SWITCH_MODE_TIMEOUT)
                    RS485Updater._validate_response(response)
                    # The return code can't be used to verify whether the bootloader is actually active, since it is
                    # answered by the active code. E.g. if the application was active, it's the application that will
                    # answer this call with the return_code APPLICATION_ACTIVE
                    logger.info('{0} - Bootloader active'.format(address))
                except CommunicationTimedOutException:
                    logger.error('{0} - Could not enter bootloader. Aborting'.format(address))
                    return False

                response = rs485_communicator.do_command(address=address,
                                                         command=RS485API.set_firmware_version(),
                                                         fields={'version': version})
                RS485Updater._validate_response(response)

                blocks = RS485Updater.BLOCKS_SMALL_SLAVE
                if len(firmware) // RS485Updater.BLOCK_SIZE + 1 > blocks:
                    blocks = RS485Updater.BLOCKS_LARGE_SLAVE

                crc = RS485Updater._get_crc(firmware, blocks)
                response = rs485_communicator.do_command(address=address,
                                                         command=RS485API.set_firmware_crc(),
                                                         fields={'crc': crc})
                RS485Updater._validate_response(response)

                logger.info('{0} - Flashing contents of {1}'.format(address, os.path.basename(hex_filename)))
                logger.info('{0} - Flashing...'.format(address))
                for block in range(blocks):
                    start = block * RS485Updater.BLOCK_SIZE
                    if block < (blocks - 1):
                        payload = bytearray(firmware.tobinarray(start=start, end=start + RS485Updater.BLOCK_SIZE - 1))
                    else:
                        payload = (
                            bytearray(firmware.tobinarray(start=start, end=start + RS485Updater.BLOCK_SIZE - 1 - 8)) +
                            bytearray(firmware.tobinarray(start=0, end=7))
                        )

                    try:
                        response = rs485_communicator.do_command(address=address,
                                                                 command=RS485API.write_firmware_block(),
                                                                 fields={'address': block, 'payload': payload},
                                                                 timeout=RS485Updater.WRITE_FLASH_BLOCK_TIMEOUT)
                        RS485Updater._validate_response(response)
                        if block % int(blocks / 10) == 0 and block != 0:
                            logger.info('{0} - Flashing... {1}%'.format(address, int(block * 100 / blocks)))
                    except CommunicationTimedOutException:
                        logger.info('{0} - Flashing... block {1} failed'.format(address, block))
                        raise

                logger.info('{0} - Flashing... Done'.format(address))

                logger.info('{0} - Running integrity check'.format(address))
                response = rs485_communicator.do_command(address=address,
                                                         command=RS485API.integrity_check(),
                                                         fields={})
                RS485Updater._validate_response(response)
                logger.info('{0} - Integrity OK'.format(address))

                logger.info('{0} - Entering application'.format(address))
                try:
                    response = rs485_communicator.do_command(address=address,
                                                             command=RS485API.goto_application(),
                                                             fields={},
                                                             timeout=RS485Updater.SWITCH_MODE_TIMEOUT)
                    return_code = RS485Updater._validate_response(response)
                    if return_code != RS485API.ReturnCode.APPLICATION_ACTIVE:
                        logger.error('{0} - Could not enter application: {1}. Aborting'.format(address, return_code))
                        return False
                    logger.info('{0} - Application active'.format(address))
                except CommunicationTimedOutException:
                    pass  # TODO: This should respond
                    # logger.error('{0} - Could not enter application. Aborting'.format(address))
                    # return False

                logger.info('{0} - Loading new firmware version'.format(address))
                new_version = RS485Updater._get_version(rs485_communicator, address, tries=60)
                if new_version is None:
                    logger.error('{0} - Could not request new firmware version'.format(address))
                    return False
                firmware_version, hardware_version = new_version
                logger.info('{0} - New version: {1} ({2})'.format(address, firmware_version, hardware_version))

                logger.info('{0} - Update completed'.format(address))
                return True
        except Exception as ex:
            logger.exception('{0} - Error flashing: {1}'.format(address, ex))
            return False

    @staticmethod
    def _get_version(rs485_communicator, address, tries=1):  # type: (RS485Communicator, str, int) -> Optional[Tuple[str, str]]
        tries_counter = tries
        while True:
            try:
                response = rs485_communicator.do_command(address=address,
                                                         command=RS485API.get_firmware_version(),
                                                         fields={})
                if response is None:
                    raise CommunicationTimedOutException()
                if tries_counter != tries:
                    logger.warning('{0} - Needed {1} tries to load version'.format(address, tries - tries_counter + 1))
                return response['version'], response['hardware_version']
            except CommunicationTimedOutException:
                tries_counter -= 1
                if tries_counter == 0:
                    return None
                time.sleep(2)

    @staticmethod
    def _get_crc(firmware, blocks):  # type: (IntelHex, int) -> List[int]
        bytes_sum = 0
        for block in range(64 * blocks - 8):
            bytes_sum += firmware[block]

        return [
            (bytes_sum & (0xFF << 24)) >> 24,
            (bytes_sum & (0xFF << 16)) >> 16,
            (bytes_sum & (0xFF << 8)) >> 8,
            (bytes_sum & (0xFF << 0)) >> 0
        ]

    @staticmethod
    def _validate_response(response):  # type: (Optional[Dict[str, Any]]) -> Optional[str]
        if response is None:
            return None
        return_code = RS485API.ReturnCode.code_to_enum(response['return_code'])
        if return_code in RS485API.ReturnCode.ERRORS:
            raise RuntimeError('Got unexpected response: {0}'.format(return_code))
        return return_code
