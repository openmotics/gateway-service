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
Tool to bootload the energy modules from the command line.
"""
from __future__ import absolute_import
from platform_utils import System
System.import_libs()

import sys
import argparse
import logging
from ioc import INJECTED, Inject
from logs import Logs
from serial_utils import CommunicationTimedOutException
from gateway.enums import EnergyEnums
from gateway.initialize import setup_minimal_energy_platform

if False:  # MYPY
    from typing import Tuple
    from gateway.energy_module_controller import EnergyModuleController
    from serial_utils import RS485

logger = logging.getLogger('openmotics')


def main():
    """ The main function. """
    logger.info('Bootloader for Energy/Power Modules and P1 Concentrator')
    logger.info('Command: {0}'.format(' '.join(sys.argv)))

    parser = argparse.ArgumentParser(description='Tool to bootload a module.')
    parser.add_argument('--address', dest='address', type=int,
                        help='the address of the module to bootload')
    parser.add_argument('--all', dest='all', action='store_true',
                        help='bootload all modules')
    parser.add_argument('--file', dest='file',
                        help='the filename of the hex file to bootload')
    parser.add_argument('--p1c', dest='p1c', action='store_true',
                        help='bootload for the P1 concentrator modules')
    parser.add_argument('--verbose', dest='verbose', action='store_true',
                        help='show the serial output')
    parser.add_argument('--scan', dest='scan', action='store_true',
                        help='Scan the energy bus for modules')
    parser.add_argument('--version', dest='firmware_version', required=False,
                        help='version of the provided hex file')

    args = parser.parse_args()

    if not args.file and not args.scan:
        parser.print_help()
        return

    setup_minimal_energy_platform()

    @Inject
    def _get_from_ioc(energy_module_controller=INJECTED, energy_serial=INJECTED):
        # type: (EnergyModuleController, RS485) -> Tuple[EnergyModuleController, RS485]
        return energy_module_controller, energy_serial

    controller, serial = _get_from_ioc()

    if serial is None:
        logger.info('Energy bus is disabled. Skipping...')
        return
    if controller is None:
        logger.error('Controller could not be loaded. Aborting...')
        return

    serial.start()

    if args.scan:
        logger.info('Scanning addresses 0-255...')
        for module_type, address, version in controller.scan_bus():
            logger.info('{0}{1} - Version: {2}'.format(module_type, address, version))
        logger.info('Scan completed')
        return

    version = EnergyEnums.Version.ENERGY_MODULE
    if args.p1c:
        version = EnergyEnums.Version.P1_CONCENTRATOR

    if args.address or args.all:
        if args.all:
            failures = controller.update_modules(module_version=version,
                                                 firmware_filename=args.file,
                                                 firmware_version=args.firmware_version)
            for module_address, exception in failures.items():
                if exception is None:
                    continue
                elif exception is CommunicationTimedOutException:
                    logger.warning('E{0} - Module was unavailable and is skipped...'.format(module_address))
                else:
                    logger.exception('E{0} - Module had an unexpected error during bootloading and was skipped: {1}'.format(module_address, exception))
        else:
            module_address = args.address
            modules = [module for module in controller.load_modules()
                       if module.address == module_address and module.version == version]
            if len(modules) != 1:
                logger.info('ERROR: Cannot find a module with address {0}'.format(module_address))
                sys.exit(0)
            try:
                controller.update_module(module_version=version,
                                         module_address=module_address,
                                         firmware_filename=args.file,
                                         firmware_version=args.firmware_version)
            except CommunicationTimedOutException:
                logger.warning('E{0} - Module unavailable. Skipping...'.format(module_address))
            except Exception:
                logger.exception('E{0} - Unexpected exception during bootload. Skipping...'.format(module_address))

    else:
        parser.print_help()


if __name__ == '__main__':
    Logs.setup_logger()
    main()
