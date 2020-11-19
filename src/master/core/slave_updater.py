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
from master.core.memory_models import (
    GlobalConfiguration,
    InputModuleConfiguration, OutputModuleConfiguration, SensorModuleConfiguration,
    CanControlModuleConfiguration, UCanModuleConfiguration
)
from master.core.slave_communicator import SlaveCommunicator, CommunicationTimedOutException
from master.core.slave_api import SlaveAPI
from master.core.ucan_communicator import UCANCommunicator
from master.core.ucan_updater import UCANUpdater

logger = logging.getLogger('openmotics')

if False:  # MYPY
    from typing import Tuple, Optional, List, Dict, Any, Union


class SlaveUpdater(object):
    """
    This is a class holding tools to execute slave updates
    """

    BLOCKS_SMALL_SLAVE = 410
    BLOCKS_LARGE_SLAVE = 922
    BOOTLOADER_TIMEOUT = 10
    WRITE_FLASH_BLOCK_TIMEOUT = 10
    SWITCH_MODE_TIMEOUT = 10
    BLOCK_SIZE = 64

    @staticmethod
    def update_all(module_type, hex_filename, gen3_firmware, version):  # type: (str, str, bool, Optional[str]) -> bool
        def _default_if_255(value, default):
            return value if value != 255 else default

        general_configuration = GlobalConfiguration()
        executed_update = False
        success = True

        # Classic master slave modules: ['O', 'R', 'D', 'I', 'T', 'C']
        update_map = {'I': (InputModuleConfiguration, _default_if_255(general_configuration.number_of_input_modules, 0)),
                      'O': (OutputModuleConfiguration, _default_if_255(general_configuration.number_of_output_modules, 0)),
                      'D': (OutputModuleConfiguration, _default_if_255(general_configuration.number_of_output_modules, 0)),
                      'T': (SensorModuleConfiguration, _default_if_255(general_configuration.number_of_sensor_modules, 0)),
                      'C': (CanControlModuleConfiguration, _default_if_255(general_configuration.number_of_can_control_modules, 0))}
        if module_type in update_map:
            module_configuration_class, number_of_modules = update_map[module_type]
            for module_id in range(number_of_modules):
                module_configuration = module_configuration_class(module_id)  # type: Union[InputModuleConfiguration, OutputModuleConfiguration, SensorModuleConfiguration, CanControlModuleConfiguration]
                if module_configuration.device_type == module_type:
                    executed_update = True
                    success &= SlaveUpdater.update(address=module_configuration.address,
                                                   hex_filename=hex_filename,
                                                   gen3_firmware=gen3_firmware,
                                                   version=version)
                else:
                    logger.info('Skip updating unsupported module {0}: {1} != {2}'.format(
                        module_configuration.address, module_configuration.device_type, module_type
                    ))

        # MicroCAN (uCAN)
        if module_type == 'UC':
            number_of_ucs = _default_if_255(general_configuration.number_of_ucan_modules, 0)
            if number_of_ucs:
                ucan_communicator = UCANCommunicator()
                for module_id in range(number_of_ucs):
                    ucan_configuration = UCanModuleConfiguration(module_id)
                    executed_update = True
                    success &= UCANUpdater.update(cc_address=ucan_configuration.module.address,
                                                  ucan_address=ucan_configuration.address,
                                                  ucan_communicator=ucan_communicator,
                                                  hex_filename=hex_filename,
                                                  version=version)

        if not executed_update:
            logger.info('No modules of type {0} were updated'.format(module_type))
            return True
        return success

    @staticmethod
    @Inject
    def update(address, hex_filename, gen3_firmware, version, slave_communicator=INJECTED):
        # type: (str, str, bool, Optional[str], SlaveCommunicator) -> bool
        """ Flashes the content from an Intel HEX file to a slave module """
        try:
            with slave_communicator:
                logger.info('Updating slave')

                if not os.path.exists(hex_filename):
                    raise RuntimeError('The given path does not point to an existing file')
                firmware = IntelHex(hex_filename)  # Using the IntelHex library read and validate contents

                logger.info('{0} - Loading current firmware version'.format(address))
                current_version = SlaveUpdater._get_version(slave_communicator, address, tries=30)
                if current_version is None:
                    logger.info('{0} - Could not request current firmware version'.format(address))
                    logger.info('{0} - Module does not support bootloading. Skipping'.format(address))
                    return True  # This is considered "success" as it's nothing that can "fixed"
                firmware_version, hardware_version = current_version
                logger.info('{0} - Current version: {1} ({2})'.format(address, firmware_version, hardware_version))

                if version == firmware_version:
                    logger.info('{0} - Already up-to-date. Skipping'.format(address))
                    return True

                gen3_module = int(firmware_version.split('.')[0]) >= 6
                if gen3_firmware and not gen3_module:
                    logger.info('{0} - Skip flashing Gen3 firmware on Gen2 module'.format(address))
                    return True
                if gen3_module and not gen3_firmware:
                    logger.info('{0} - Skip flashing Gen2 firmware on Gen3 module'.format(address))
                    return True

                logger.info('{0} - Entering bootloader'.format(address))
                try:
                    response = slave_communicator.do_command(address=address,
                                                             command=SlaveAPI.goto_bootloader(),
                                                             fields={'timeout': SlaveUpdater.BOOTLOADER_TIMEOUT},
                                                             timeout=SlaveUpdater.SWITCH_MODE_TIMEOUT)
                    SlaveUpdater._validate_response(response)
                    # The return code can't be used to verify whether the bootloader is actually active, since it is
                    # answered by the active code. E.g. if the application was active, it's the application that will
                    # answer this call with the return_code APPLICATION_ACTIVE
                    logger.info('{0} - Bootloader active'.format(address))
                except CommunicationTimedOutException:
                    logger.error('{0} - Could not enter bootloader. Aborting'.format(address))
                    return False

                if version is not None:
                    response = slave_communicator.do_command(address=address,
                                                             command=SlaveAPI.set_firmware_version(),
                                                             fields={'version': version})
                    SlaveUpdater._validate_response(response)

                blocks = SlaveUpdater.BLOCKS_SMALL_SLAVE
                if len(firmware) // SlaveUpdater.BLOCK_SIZE + 1 > blocks:
                    blocks = SlaveUpdater.BLOCKS_LARGE_SLAVE

                crc = SlaveUpdater._get_crc(firmware, blocks)
                response = slave_communicator.do_command(address=address,
                                                         command=SlaveAPI.set_firmware_crc(),
                                                         fields={'crc': crc})
                SlaveUpdater._validate_response(response)

                logger.info('{0} - Flashing contents of {1}'.format(address, os.path.basename(hex_filename)))
                logger.info('{0} - Flashing...'.format(address))
                for block in range(blocks):
                    start = block * SlaveUpdater.BLOCK_SIZE
                    if block < (blocks - 1):
                        payload = bytearray(firmware.tobinarray(start=start, end=start + SlaveUpdater.BLOCK_SIZE - 1))
                    else:
                        payload = (
                                bytearray(firmware.tobinarray(start=start, end=start + SlaveUpdater.BLOCK_SIZE - 1 - 8)) +
                                bytearray(firmware.tobinarray(start=0, end=7))  # Store jump address to the end of the flash space
                        )

                    try:
                        response = slave_communicator.do_command(address=address,
                                                                 command=SlaveAPI.write_firmware_block(),
                                                                 fields={'address': block, 'payload': payload},
                                                                 timeout=SlaveUpdater.WRITE_FLASH_BLOCK_TIMEOUT)
                        SlaveUpdater._validate_response(response)
                        if block % int(blocks / 10) == 0 and block != 0:
                            logger.info('{0} - Flashing... {1}%'.format(address, int(block * 100 / blocks)))
                    except CommunicationTimedOutException:
                        logger.info('{0} - Flashing... block {1} failed'.format(address, block))
                        raise

                logger.info('{0} - Flashing... Done'.format(address))

                logger.info('{0} - Running integrity check'.format(address))
                response = slave_communicator.do_command(address=address,
                                                         command=SlaveAPI.integrity_check(),
                                                         fields={})
                SlaveUpdater._validate_response(response)
                logger.info('{0} - Integrity OK'.format(address))

                logger.info('{0} - Entering application'.format(address))
                try:
                    response = slave_communicator.do_command(address=address,
                                                             command=SlaveAPI.goto_application(),
                                                             fields={},
                                                             timeout=SlaveUpdater.SWITCH_MODE_TIMEOUT)
                    return_code = SlaveUpdater._validate_response(response)
                    if return_code != SlaveAPI.ReturnCode.APPLICATION_ACTIVE:
                        logger.error('{0} - Could not enter application: {1}. Aborting'.format(address, return_code))
                        return False
                    logger.info('{0} - Application active'.format(address))
                except CommunicationTimedOutException:
                    pass  # TODO: This should respond
                    # logger.error('{0} - Could not enter application. Aborting'.format(address))
                    # return False

                logger.info('{0} - Loading new firmware version'.format(address))
                new_version = SlaveUpdater._get_version(slave_communicator, address, tries=60)
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
    def _get_version(slave_communicator, address, tries=1):  # type: (SlaveCommunicator, str, int) -> Optional[Tuple[str, str]]
        tries_counter = tries
        while True:
            try:
                response = slave_communicator.do_command(address=address,
                                                         command=SlaveAPI.get_firmware_version(),
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
        return_code = SlaveAPI.ReturnCode.code_to_enum(response['return_code'])
        if return_code in SlaveAPI.ReturnCode.ERRORS:
            raise RuntimeError('Got unexpected response: {0}'.format(return_code))
        return return_code
