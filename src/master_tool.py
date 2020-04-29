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
Tool to control the master from the command line.

@author: fryckbos
"""
from __future__ import absolute_import
from platform_utils import System, Platform
System.import_libs()

import argparse
import logging
import shutil
import subprocess
import sys
import time
from six.moves.configparser import ConfigParser
from ioc import INJECTED, Inject, Injectable
from serial import Serial
import constants
import master.classic.master_api as master_api
from master.core.core_api import CoreAPI
from serial_utils import CommunicationTimedOutException

logger = logging.getLogger('openmotics')


def setup_logger():
    """ Setup the OpenMotics logger. """

    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


@Inject
def master_sync(master_controller=INJECTED):
    print('Sync...')
    try:
        master_controller.get_status()
        print('Done sync')
    except CommunicationTimedOutException:
        print('Failed sync')
        sys.exit(1)


@Inject
def master_version(master_controller=INJECTED):
    status = master_controller.get_status()
    print('{} H{}'.format(status['version'], status['hw_version']))


@Inject
def master_reset(master_controller=INJECTED):
    print('Resetting...')
    try:
        master_controller.reset()
        print('Done resetting')
    except CommunicationTimedOutException:
        print('Failed resetting')
        sys.exit(1)


@Inject
def master_cold_reset(master_controller=INJECTED):
    print('Performing hard reset...')
    master_controller.cold_reset()
    print('Done performing hard reset')


@Inject
def master_factory_reset(master_controller=INJECTED):
    print('Wiping the master...')
    master_controller.factory_reset()
    print('Done wiping the master')


def classic_master_update(firmware):
    if firmware:
        try:
            print('Updating master')
            subprocess.check_call(['/opt/openmotics/bin/updateController.sh', 'H4', 'PIC18F67J11', firmware, '/opt/openmotics/firmware.hex'])
            shutil.copy(firmware, '/opt/openmotics/firmware.hex')
            print('Done update')
        except subprocess.CalledProcessError:
            print('Failed to update master')
            sys.exit(1)
    else:
        print('error: --master-firmware-classic is required to update')
        sys.exit(1)


def core_master_update(firmware):
    if firmware:
        try:
            print('Updating master')
            # TODO should probably move to bin
            subprocess.check_call(['python2', '/opt/openmotics/python/core_updater.py', firmware])
            shutil.copy(firmware, '/opt/openmotics/firmware.hex')
            print('Done update')
        except subprocess.CalledProcessError:
            print('Failed to update master')
            sys.exit(1)
    else:
        print('error: --master-firmware-core is required to update')
        sys.exit(1)


def main():
    """ The main function. """
    parser = argparse.ArgumentParser(description='Tool to control the master.')
    parser.add_argument('--port', dest='port', action='store_true',
                        help='get the serial port device')
    parser.add_argument('--sync', dest='sync', action='store_true',
                        help='sync the serial port')
    parser.add_argument('--reset', dest='reset', action='store_true',
                        help='reset the master')
    parser.add_argument('--hard-reset', dest='hardreset', action='store_true',
                        help='perform a hardware reset on the master')
    parser.add_argument('--version', dest='version', action='store_true',
                        help='get the version of the master')
    parser.add_argument('--wipe', dest='wipe', action='store_true',
                        help='wip the master eeprom')
    parser.add_argument('--update', dest='update', action='store_true',
                        help='update the master firmware')
    parser.add_argument('--master-firmware-classic',
                        help='path to the hexfile with the classic firmware')
    parser.add_argument('--master-firmware-core',
                        help='path to the hexfile with the core+ firmware')

    args = parser.parse_args()

    setup_logger()

    config = ConfigParser()
    config.read(constants.get_config_file())

    port = config.get('OpenMotics', 'controller_serial')

    if args.port:
        print(port)
        return

    if not any([args.sync, args.version, args.reset, args.hardreset, args.wipe, args.update]):
        parser.print_help()

    platform = Platform.get_platform()

    Injectable.value(controller_serial=Serial(port, 115200))

    if platform == Platform.Type.CORE_PLUS:
        from master.core.memory_file import MemoryFile, MemoryTypes
        Injectable.value(memory_files={MemoryTypes.EEPROM: MemoryFile(MemoryTypes.EEPROM),
                                       MemoryTypes.FRAM: MemoryFile(MemoryTypes.FRAM)})
        from gateway.hal import master_controller_core
        _ = master_controller_core
    else:
        Injectable.value(configuration_controller=None)
        Injectable.value(eeprom_db=constants.get_eeprom_extension_database_file())
        from master.classic import eeprom_extension
        from gateway.hal import master_controller_classic
        _ = master_controller_classic

    if args.update:
        if platform == Platform.Type.CORE_PLUS:
            core_master_update(args.master_firmware_core)
        else:
            classic_master_update(args.master_firmware_classic)
        return
    elif args.hardreset:
        master_cold_reset()
        return

    @Inject
    def start(master_communicator=INJECTED):
        # Explicitly only start the communicator and not the controller,
        # to avoid the brackground synchronization, etc.
        master_communicator.start()
    start()

    try:

        if args.sync:
            master_sync()
        elif args.version:
            master_version()
        elif args.reset:
            master_reset()
        elif args.wipe:
            master_factory_reset()

    finally:

        @Inject
        def stop(master_communicator=INJECTED):
            master_communicator.stop()
            time.sleep(4)
        stop()


if __name__ == '__main__':
    main()
