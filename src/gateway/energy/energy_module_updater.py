# Copyright (C) 2021 OpenMotics BV
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
Energy module update logic
"""
from __future__ import absolute_import

import os.path

import intelhex
import logging
import time
from ioc import INJECTED, Inject
from gateway.energy.energy_api import EnergyAPI
from gateway.enums import EnergyEnums
from logs import Logs

if False:  # MYPY
    from typing import Tuple, Optional, List
    from gateway.energy.energy_communicator import EnergyCommunicator

# Different name to reduce confusion between multiple used loggers
global_logger = logging.getLogger(__name__)


class EnergyModuleUpdater(object):

    @Inject
    def __init__(self, energy_communicator=INJECTED):
        # type: (EnergyCommunicator) -> None
        self._energy_communicator = energy_communicator

    def get_module_firmware_version(self, module_address, module_version):  # type: (int, int) -> Tuple[str, Optional[str]]
        raw_version = self._energy_communicator.do_command(module_address, EnergyAPI.get_version(module_version))
        if module_version == EnergyEnums.Version.P1_CONCENTRATOR:
            return '{0}.{1}.{2}'.format(raw_version[1], raw_version[2], raw_version[3]), str(raw_version[0])
        else:
            cleaned_version = raw_version[0].split('\x00', 1)[0]
            parsed_version = cleaned_version.split('_')
            if len(parsed_version) != 4:
                return cleaned_version, None
            return '{0}.{1}.{2}'.format(parsed_version[1], parsed_version[2], parsed_version[3]), str(parsed_version[0])

    def bootload_module(self, module_version, module_address, hex_filename, firmware_version):
        if not os.path.exists(hex_filename):
            raise RuntimeError('File {0} does not exists'.format(hex_filename))

        if module_version == EnergyEnums.Version.ENERGY_MODULE:
            return self._bootload_energy_module(module_address=module_address,
                                                hex_filename=hex_filename,
                                                version=firmware_version)
        if module_version == EnergyEnums.Version.P1_CONCENTRATOR:
            return self._bootload_p1_concentrator(module_address=module_address,
                                                  hex_filename=hex_filename,
                                                  version=firmware_version)
        raise RuntimeError('Unknown or unsupported energy module version: {0}'.format(module_version))

    def _bootload_energy_module(self, module_address, hex_filename, version):
        # type: (int, str, str) -> str
        individual_logger = Logs.get_update_logger('energy_{0}'.format(module_address))
        in_booloader = False
        try:
            firmware_version, hardware_version = self.get_module_firmware_version(module_address, EnergyEnums.Version.ENERGY_MODULE)
            if hardware_version == 'OMFBC':
                individual_logger.info('Already in bootloader: {0}'.format(firmware_version))
                in_booloader = True
            else:
                individual_logger.info('Version: {0}'.format(firmware_version))
        except Exception:
            individual_logger.info('Could not load current version')

        calibration_data = None  # Optional[List[int]]
        if not in_booloader:
            try:
                individual_logger.info('Reading calibration data')
                calibration_data = list(self._energy_communicator.do_command(module_address, EnergyAPI.read_eeprom(12, 100), *[256, 100]))
                individual_logger.info('Calibration data: {0}'.format(','.join([str(d) for d in calibration_data])))
            except Exception as ex:
                individual_logger.info('Could not read calibration data: {0}'.format(ex))

        if not in_booloader:
            individual_logger.info('Going to bootloader')
            self._energy_communicator.do_command(module_address, EnergyAPI.bootloader_goto(EnergyEnums.Version.ENERGY_MODULE), 10)
            firmware_version, hardware_version = self.get_module_firmware_version(module_address, EnergyEnums.Version.ENERGY_MODULE)
            if hardware_version != 'OMFBC':
                raise RuntimeError('Failed to enter bootloader')
            individual_logger.info('Bootloader version: {0}'.format(firmware_version))

        try:
            individual_logger.info('Erasing code...')
            for page in range(6, 64):
                self._energy_communicator.do_command(module_address, EnergyAPI.bootloader_erase_code(), page)

            reader = HexReader(hex_filename)
            individual_logger.info('Writing code...')
            for address in range(0x1D006000, 0x1D03FFFB, 128):
                data = reader.get_bytes_version_12(address)
                self._energy_communicator.do_command(module_address, EnergyAPI.bootloader_write_code(EnergyEnums.Version.ENERGY_MODULE), *data)
        finally:
            individual_logger.info('Jumping to application')
            self._energy_communicator.do_command(module_address, EnergyAPI.bootloader_jump_application())

        tries = 0
        while True:
            try:
                tries += 1
                individual_logger.info('Waiting for application...')
                firmware_version, hardware_version = self.get_module_firmware_version(module_address, EnergyEnums.Version.ENERGY_MODULE)
                if hardware_version == 'OMFPC':
                    individual_logger.info('Version: {0}'.format(firmware_version))
                    break
                if tries >= 6:
                    raise RuntimeError('Failed to enter application')
            except Exception:
                if tries >= 3:
                    raise
            time.sleep(1)

        if calibration_data is not None:
            time.sleep(1)
            individual_logger.info('Restoring calibration data')
            self._energy_communicator.do_command(module_address, EnergyAPI.write_eeprom(12, 100), *([256] + calibration_data))

        individual_logger.info('Done')
        return firmware_version

    def _bootload_p1_concentrator(self, module_address, hex_filename, version):
        _ = hex_filename  # Not yet in use
        individual_logger = Logs.get_update_logger('p1_concentrator_{0}'.format(module_address))
        firmware_version, hardware_version = self.get_module_firmware_version(module_address, EnergyEnums.Version.P1_CONCENTRATOR)
        individual_logger.info('Version: {0} ({1})'.format(firmware_version, hardware_version))
        if firmware_version == version:
            individual_logger.info('Already up-to-date. Skipping')
            return
        individual_logger.info('Start bootloading')

        individual_logger.info('Going to bootloader')
        self._energy_communicator.do_command(module_address, EnergyAPI.bootloader_goto(EnergyEnums.Version.P1_CONCENTRATOR), 10)

        # No clue yet. Most likely this will use the same approach as regular master slave modules

        individual_logger.info('Done')


class HexReader(object):
    """ Reads the hex from file and returns it in the OpenMotics format. """

    def __init__(self, hex_file):
        """ Constructor with the name of the hex file. """
        self._hex = intelhex.IntelHex(hex_file)
        self._crc = 0

    def get_bytes_version_8(self, address):
        """ Get the 192 bytes from the hex file, with 3 address bytes prepended. """
        data_bytes = [address % 256,
                      (address % 65536) / 256,
                      address / 65536]

        iaddress = address * 2
        for i in range(64):
            data0 = self._hex[iaddress + (4 * i) + 0]
            data1 = self._hex[iaddress + (4 * i) + 1]
            data2 = self._hex[iaddress + (4 * i) + 2]

            if address == 0 and i == 0:  # Set the start address to the bootloader: 0x400
                data1 = 4

            data_bytes.append(data0)
            data_bytes.append(data1)
            data_bytes.append(data2)

            if not (address == 43904 and i >= 62):  # Don't include the CRC bytes in the CRC
                self._crc += data0 + data1 + data2

        if address == 43904:  # Add the CRC at the end of the program
            data_bytes[-1] = self._crc % 256
            data_bytes[-2] = (self._crc % (256 * 256)) / 256
            data_bytes[-3] = (self._crc % (256 * 256 * 256)) / (256 * 256)
            data_bytes[-4] = (self._crc % (256 * 256 * 256 * 256)) / (256 * 256 * 256)

        return data_bytes

    @staticmethod
    def int_to_array_12(integer):
        """ Convert an integer to an array for the 12 port energy module. """
        return [integer % 256, (integer % 65536) / 256, (integer / 65536) % 256, (integer / 65536) / 256]

    def get_bytes_version_12(self, address):
        """ Get the 128 bytes from the hex file, with 4 address bytes prepended. """
        data_bytes = self.int_to_array_12(address)

        for i in range(32):
            data0 = self._hex[address + (4 * i) + 0]
            data1 = self._hex[address + (4 * i) + 1]
            data2 = self._hex[address + (4 * i) + 2]
            data3 = self._hex[address + (4 * i) + 3]

            data_bytes.append(data0)
            data_bytes.append(data1)
            data_bytes.append(data2)
            data_bytes.append(data3)

            if not (address == 486801280 and i == 31):
                self._crc += data0 + data1 + data2 + data3

        if address == 486801280:
            data_bytes = data_bytes[:-4]
            data_bytes += self.int_to_array_12(self.get_crc())

        return data_bytes

    def get_crc(self):
        """ Get the crc for the block that have been read from the HexReader. """
        return self._crc
