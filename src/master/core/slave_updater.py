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
Module to update a slave module
"""

from __future__ import absolute_import
import logging
import os
import time
from ioc import INJECTED, Inject
from intelhex import IntelHex
from master.core.slave_communicator import SlaveCommunicator, CommunicationTimedOutException
from master.core.slave_api import SlaveAPI
from master.core.ucan_updater import UCANUpdater
from logs import Logs

# Different name to reduce confusion between multiple used loggers
global_logger = logging.getLogger(__name__)

if False:  # MYPY
    from typing import Tuple, Optional, List, Dict, Any
    from logging import Logger


class SlaveUpdater(object):
    """
    This is a class holding tools to execute slave updates
    """

    BLOCK_SIZE = 64
    BLOCKS_SMALL_SLAVE = 410
    BLOCKS_LARGE_SLAVE = 922
    BOOTLOADER_TIMEOUT = 10
    WRITE_FLASH_BLOCK_TIMEOUT = 10
    SWITCH_MODE_TIMEOUT = 15

    @staticmethod
    def update_ucan(ucan_address, cc_address, hex_filename, version):  # type: (str, str, str, Optional[str]) -> Optional[str]
        individual_logger = Logs.get_update_logger('ucan_{0}'.format(ucan_address))
        return UCANUpdater.update(cc_address=cc_address,
                                  ucan_address=ucan_address,
                                  hex_filename=hex_filename,
                                  version=version,
                                  logger=individual_logger)

    @staticmethod
    @Inject
    def update(address, hex_filename, gen3_firmware, version, logger, slave_communicator=INJECTED):
        # type: (str, str, bool, Optional[str], Logger, SlaveCommunicator) -> Optional[str]
        """ Flashes the content from an Intel HEX file to a slave module """
        with slave_communicator:
            logger.info('Updating slave')

            if not os.path.exists(hex_filename):
                raise RuntimeError('The given path does not point to an existing file')
            firmware = IntelHex(hex_filename)  # Using the IntelHex library read and validate contents

            logger.info('Loading current firmware version')
            current_version = SlaveUpdater._get_version(slave_communicator=slave_communicator,
                                                        address=address,
                                                        logger=logger,
                                                        tries=5)
            if current_version is None:
                logger.info('Could not request current firmware version')
                logger.info('Module does not support bootloading. Skipping')
                return None  # This is considered "success" as it's nothing that can "fixed"
            firmware_version, hardware_version = current_version
            logger.info('Current version: {0} ({1})'.format(firmware_version, hardware_version))

            if version == firmware_version:
                logger.info('Already up-to-date. Skipping')
                return version

            gen3_module = int(firmware_version.split('.')[0]) >= 6
            if gen3_firmware and not gen3_module:
                logger.info('Skip flashing Gen3 firmware on Gen2 module')
                return firmware_version
            if gen3_module and not gen3_firmware:
                logger.info('Skip flashing Gen2 firmware on Gen3 module')
                return firmware_version

            logger.info('Entering bootloader')
            try:
                response = slave_communicator.do_command(address=address,
                                                         command=SlaveAPI.goto_bootloader(),
                                                         fields={'timeout': SlaveUpdater.BOOTLOADER_TIMEOUT},
                                                         timeout=SlaveUpdater.SWITCH_MODE_TIMEOUT)
                SlaveUpdater._validate_response(response=response)
                # The return code can't be used to verify whether the bootloader is actually active, since it is
                # answered by the active code. E.g. if the application was active, it's the application that will
                # answer this call with the return_code APPLICATION_ACTIVE
                logger.info('Bootloader should be active')
                time.sleep(2)  # Wait for the bootloader to settle
            except CommunicationTimedOutException:
                logger.error('Could not enter bootloader. Aborting')
                return firmware_version

            if version is not None:
                response = slave_communicator.do_command(address=address,
                                                         command=SlaveAPI.set_firmware_version(),
                                                         fields={'version': version})
                SlaveUpdater._validate_response(response=response)

            data_blocks = len(firmware) // SlaveUpdater.BLOCK_SIZE + 1
            blocks = SlaveUpdater.BLOCKS_SMALL_SLAVE
            if data_blocks > blocks or gen3_module:
                blocks = SlaveUpdater.BLOCKS_LARGE_SLAVE
            logger.info('{0} slave ({1}/{2} blocks)'.format(
                'Large' if blocks == SlaveUpdater.BLOCKS_LARGE_SLAVE else 'Small',
                data_blocks, blocks
            ))

            crc = SlaveUpdater._get_crc(firmware=firmware,
                                        blocks=blocks)
            response = slave_communicator.do_command(address=address,
                                                     command=SlaveAPI.set_firmware_crc(),
                                                     fields={'crc': crc})
            SlaveUpdater._validate_response(response=response)

            logger.info('Flashing contents of {0}'.format(os.path.basename(hex_filename)))
            logger.info('Flashing...')
            for block in range(blocks):
                start = block * SlaveUpdater.BLOCK_SIZE
                if block < (blocks - 1):
                    payload = bytearray(firmware.tobinarray(start=start, end=start + SlaveUpdater.BLOCK_SIZE - 1))
                else:
                    payload = (
                            bytearray(firmware.tobinarray(start=start, end=start + SlaveUpdater.BLOCK_SIZE - 1 - 8)) +
                            bytearray(firmware.tobinarray(start=0, end=7))  # Store jump address to the end of the flash space
                    )

                tries = 0
                while True:
                    tries += 1
                    try:
                        response = slave_communicator.do_command(address=address,
                                                                 command=SlaveAPI.write_firmware_block(),
                                                                 fields={'address': block, 'payload': payload},
                                                                 timeout=SlaveUpdater.WRITE_FLASH_BLOCK_TIMEOUT)
                        SlaveUpdater._validate_response(response=response)
                        if block % int(blocks / 10) == 0 and block != 0:
                            logger.info('Flashing... {0}%'.format(int(block * 100 / blocks)))
                        break
                    except CommunicationTimedOutException as ex:
                        logger.warning('Flashing... Block {0} failed: {1}'.format(block, ex))
                        if tries >= 3:
                            raise

            logger.info('Flashing... Done')

            logger.info('Running integrity check')
            response = slave_communicator.do_command(address=address,
                                                     command=SlaveAPI.integrity_check(),
                                                     fields={})
            SlaveUpdater._validate_response(response=response)
            logger.info('Integrity OK')

            logger.info('Entering application')
            try:
                response = slave_communicator.do_command(address=address,
                                                         command=SlaveAPI.goto_application(),
                                                         fields={},
                                                         timeout=SlaveUpdater.SWITCH_MODE_TIMEOUT)
                SlaveUpdater._validate_response(response=response)
                logger.info('Application should be active')
                time.sleep(2)  # Wait for the application to settle
            except CommunicationTimedOutException:
                logger.error('Switching to application timed out')

            if address != '255.255.255.255':
                logger.info('Loading new firmware version')
                new_version = SlaveUpdater._get_version(slave_communicator=slave_communicator,
                                                        address=address,
                                                        logger=logger,
                                                        tries=5)
                if new_version is None:
                    logger.error('Could not request new firmware version')
                    return firmware_version
                firmware_version, hardware_version = new_version
                logger.info('New version: {0} ({1})'.format(firmware_version, hardware_version))
            else:
                logger.info('Skip loading new version as address will have been changed by the application')

            logger.info('Update completed')
            return firmware_version

    @staticmethod
    def _get_version(slave_communicator, address, logger, tries=1):
        # type: (SlaveCommunicator, str, Logger, int) -> Optional[Tuple[str, str]]
        tries_counter = tries
        while True:
            try:
                response = slave_communicator.do_command(address=address,
                                                         command=SlaveAPI.get_firmware_version(),
                                                         fields={})
                if response is None:
                    raise CommunicationTimedOutException()
                if tries_counter != tries:
                    logger.warning('Needed {0} tries to load version'.format(tries - tries_counter + 1))
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
        return_code = SlaveAPI.ReturnCode.code_to_enum(response['return_code'])
        if return_code in SlaveAPI.ReturnCode.ERRORS:
            raise RuntimeError('Got unexpected response: {0}'.format(return_code))
        return return_code
