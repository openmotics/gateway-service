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
Module to work update an uCAN
"""

from __future__ import absolute_import
import logging
import os
import struct
import time
from intelhex import IntelHex
from master.core.ucan_api import UCANAPI
from master.core.ucan_command import UCANPalletCommandSpec, SID
from master.core.ucan_communicator import UCANCommunicator
from master.core.fields import UInt32Field
from serial_utils import CommunicationTimedOutException
from ioc import Inject, INJECTED

if False:  # MYPY
    from typing import Optional
    from logging import Logger

# Different name to reduce confusion between multiple used loggers
global_logger = logging.getLogger(__name__)


class UCANUpdater(object):
    """
    This is a class holding tools to execute uCAN updates
    """

    APPLICATION_START = 0x4
    BOOTLOADER_START = 0xD000
    WRITE_FLASH_BLOCK_TIMEOUT = 10
    BOOTLOADER_APPLICATION_SWITCH_TIMEOUT = 15

    # There's a buffer of 8 segments on the uCAN. This means 7 data segments with a 1-byte header, so 49 bytes.
    # In this data stream is also the address (4 bytes) and the CRC (4 bytes) leaving 41 usefull bytes.
    MAX_FLASH_BYTES = 41

    # Bootloader timeouts
    BOOTLOADER_TIMEOUT_UPDATE = 60
    BOOTLOADER_TIMEOUT_RUNTIME = 0  # Currently needed to switch to application mode

    # Tries
    PING_TRIES = 4
    CONTROL_ACTION_TRIES = 10
    WRITE_FLASH_BLOCK_TRIES = 20

    @staticmethod
    @Inject
    def update(cc_address, ucan_address, hex_filename, version, logger, ucan_communicator=INJECTED):
        # type: (str, str, str, Optional[str], Logger, UCANCommunicator) -> Optional[str]
        """ Flashes the content from an Intel HEX file to the specified uCAN """

        logger.info('Updating uCAN {0} at CC {1} to {2}'.format(
            ucan_address, cc_address,
            'v{0}'.format(version) if version is not None else 'unknown version')
        )
        start_time = time.time()

        if not os.path.exists(hex_filename):
            raise RuntimeError('The given path does not point to an existing file')
        intel_hex = IntelHex(hex_filename)

        try:
            in_bootloader = ucan_communicator.is_ucan_in_bootloader(cc_address=cc_address,
                                                                    ucan_address=ucan_address,
                                                                    tries=UCANUpdater.PING_TRIES)
        except Exception:
            raise RuntimeError('uCAN did not respond')

        current_version = None  # type: Optional[str]
        if in_bootloader:
            logger.info('Bootloader already active, skipping version check')
        else:
            try:
                response = ucan_communicator.do_command(cc_address=cc_address,
                                                        command=UCANAPI.get_version(),
                                                        identity=ucan_address,
                                                        fields={},
                                                        tries=UCANUpdater.CONTROL_ACTION_TRIES)
                if response is None:
                    raise RuntimeError()
                current_version = response['firmware_version']
                logger.info('Current uCAN version: v{0}'.format(current_version))
            except Exception:
                logger.warning('Could not load uCAN version')

            logger.info('Bootloader not active, switching to bootloader')
            ucan_communicator.do_command(cc_address=cc_address,
                                         command=UCANAPI.set_bootloader_timeout(SID.NORMAL_COMMAND),
                                         identity=ucan_address,
                                         fields={'timeout': UCANUpdater.BOOTLOADER_TIMEOUT_UPDATE},
                                         tries=UCANUpdater.CONTROL_ACTION_TRIES)
            response = ucan_communicator.do_command(cc_address=cc_address,
                                                    command=UCANAPI.reset(SID.NORMAL_COMMAND),
                                                    identity=ucan_address,
                                                    fields={},
                                                    timeout=UCANUpdater.BOOTLOADER_APPLICATION_SWITCH_TIMEOUT,
                                                    tries=UCANUpdater.CONTROL_ACTION_TRIES)
            if response is None:
                raise RuntimeError('Error resettings uCAN before flashing')
            if response.get('application_mode', 1) != 0:
                raise RuntimeError('uCAN didn\'t enter bootloader after reset')
            in_bootloader = ucan_communicator.is_ucan_in_bootloader(cc_address=cc_address,
                                                                    ucan_address=ucan_address,
                                                                    tries=UCANUpdater.PING_TRIES)
            if not in_bootloader:
                raise RuntimeError('Could not enter bootloader')
            logger.info('Bootloader active')

        logger.info('Loading bootloader version...')
        try:
            response = ucan_communicator.do_command(cc_address=cc_address,
                                                    command=UCANAPI.get_bootloader_version(),
                                                    identity=ucan_address,
                                                    fields={},
                                                    tries=UCANUpdater.CONTROL_ACTION_TRIES)
            if response is None:
                raise RuntimeError()
            if response['major'] == ord('v'):
                bootloader_version = '<= v1.3'  # Legacy version
            else:
                bootloader_version = 'v{0}.{1}'.format(response['major'], response['minor'])
            logger.info('Bootloader version: {0}'.format(bootloader_version))
        except Exception:
            logger.warning('Could not load bootloader version')

        logger.info('Erasing flash...')
        ucan_communicator.do_command(cc_address=cc_address,
                                     command=UCANAPI.erase_flash(),
                                     identity=ucan_address,
                                     fields={},
                                     tries=UCANUpdater.CONTROL_ACTION_TRIES)
        logger.info('Erasing flash... Done')

        logger.info('Flashing contents of {0}'.format(os.path.basename(hex_filename)))
        logger.info('Flashing...')
        uint32_helper = UInt32Field('')
        empty_payload = bytearray([255] * UCANUpdater.MAX_FLASH_BYTES)
        address_blocks = list(range(UCANUpdater.APPLICATION_START, UCANUpdater.BOOTLOADER_START, UCANUpdater.MAX_FLASH_BYTES))
        total_amount = float(len(address_blocks))
        for i in range(4):
            intel_hex[UCANUpdater.BOOTLOADER_START - 8 + i] = intel_hex[i]  # Copy reset vector
            intel_hex[UCANUpdater.BOOTLOADER_START - 4 + i] = 0x0  # Reserve some space for the CRC
        crc = 0
        total_payload = bytearray()
        logged_percentage = -1
        for index, start_address in enumerate(address_blocks):
            end_address = min(UCANUpdater.BOOTLOADER_START, start_address + UCANUpdater.MAX_FLASH_BYTES) - 1

            payload = bytearray(intel_hex.tobinarray(start=start_address,
                                                     end=end_address))
            if start_address < address_blocks[-1]:
                crc = UCANPalletCommandSpec.calculate_crc(data=payload,
                                                          remainder=crc)
            else:
                payload = payload[:-4]
                crc = UCANPalletCommandSpec.calculate_crc(data=payload,
                                                          remainder=crc)
                payload += uint32_helper.encode(crc)

            little_start_address = struct.unpack('<I', struct.pack('>I', start_address))[0]

            if payload != empty_payload:
                # Since the uCAN flash area is erased, skip empty blocks
                try:
                    result = ucan_communicator.do_command(cc_address=cc_address,
                                                          command=UCANAPI.write_flash(len(payload)),
                                                          identity=ucan_address,
                                                          fields={'start_address': little_start_address,
                                                                  'data': payload},
                                                          timeout=UCANUpdater.WRITE_FLASH_BLOCK_TIMEOUT,
                                                          tries=UCANUpdater.WRITE_FLASH_BLOCK_TRIES)
                    if result is None or not result['success']:
                        raise RuntimeError('Failed to flash {0} bytes to address 0x{1:04X}'.format(len(payload), start_address))
                except CommunicationTimedOutException as ex:
                    logger.warning('Flashing... Address 0x{0:04X} failed: {1}'.format(start_address, ex))
                    raise

            total_payload += payload

            percentage = int(index / total_amount * 100)
            if percentage > logged_percentage:
                logger.info('Flashing... {0}%'.format(percentage))
                logged_percentage = percentage

        logger.info('Flashing... Done')
        crc = UCANPalletCommandSpec.calculate_crc(data=total_payload)
        if crc != 0:
            raise RuntimeError('Unexpected error in CRC calculation (0x{0:08X})'.format(crc))

        # Prepare reset to application mode
        logger.info('Reduce bootloader timeout to {0}s'.format(UCANUpdater.BOOTLOADER_TIMEOUT_RUNTIME))
        ucan_communicator.do_command(cc_address=cc_address,
                                     command=UCANAPI.set_bootloader_timeout(SID.BOOTLOADER_COMMAND),
                                     identity=ucan_address,
                                     fields={'timeout': UCANUpdater.BOOTLOADER_TIMEOUT_RUNTIME},
                                     tries=UCANUpdater.CONTROL_ACTION_TRIES)
        logger.info('Set safety counter allowing the application to immediately start on reset')
        ucan_communicator.do_command(cc_address=cc_address,
                                     command=UCANAPI.set_bootloader_safety_counter(),
                                     identity=ucan_address,
                                     fields={'safety_counter': 5},
                                     tries=UCANUpdater.CONTROL_ACTION_TRIES)

        # Switch to application mode
        logger.info('Reset to application mode')
        response = ucan_communicator.do_command(cc_address=cc_address,
                                                command=UCANAPI.reset(SID.BOOTLOADER_COMMAND),
                                                identity=ucan_address,
                                                fields={},
                                                timeout=UCANUpdater.BOOTLOADER_APPLICATION_SWITCH_TIMEOUT,
                                                tries=UCANUpdater.CONTROL_ACTION_TRIES)
        if response is None:
            raise RuntimeError('Error resettings uCAN after flashing')
        if response.get('application_mode', 0) != 1:
            raise RuntimeError('uCAN didn\'t enter application mode after reset')

        current_version = None
        if ucan_address != '255.255.255':
            try:
                response = ucan_communicator.do_command(cc_address=cc_address,
                                                        command=UCANAPI.get_version(),
                                                        identity=ucan_address,
                                                        fields={},
                                                        tries=UCANUpdater.CONTROL_ACTION_TRIES)
                if response is None:
                    raise RuntimeError()
                current_version = response['firmware_version']
                logger.info('New uCAN version: v{0}'.format(current_version))
            except Exception:
                raise RuntimeError('Could not load new uCAN version')
            if current_version != version:
                raise RuntimeError('Post-update firmware version {0} does not match expected {1}'.format(
                    current_version if current_version is not None else 'unknown',
                    version
                ))
        else:
            logger.info('Skip loading new version as address will have been changed by the application')

        logger.info('Update completed. Took {0:.1f}s'.format(time.time() - start_time))
        return current_version
