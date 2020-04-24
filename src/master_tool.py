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


@Inject
def core_master_sync(master_communicator=INJECTED):
    print('Sync...')
    try:
        master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})
        print('Done sync')
    except CommunicationTimedOutException:
        print('Failed sync')
        sys.exit(1)


@Inject
def core_master_reset(master_communicator=INJECTED):
    print('Resetting...')
    try:
        reset_ba = {'type': 254, 'action': 0, 'device_nr': 0, 'extra_parameter': 0}
        master_communicator.do_command(CoreAPI.basic_action(), reset_ba, timeout=None)
        print('Done resetting')
    except CommunicationTimedOutException:
        print('Failed resetting')
        sys.exit(1)


@Inject
def classic_master_sync(master_communicator=INJECTED):
    print('Sync...')
    try:
        master_communicator.do_command(master_api.status())
        print('Done sync')
        sys.exit(0)
    except CommunicationTimedOutException:
        print('Failed sync')
        sys.exit(1)


@Inject
def classic_master_version(master_communicator=INJECTED):
    status = master_communicator.do_command(master_api.status())
    print('{0}.{1}.{2} H{3}'.format(status['f1'], status['f2'], status['f3'], status['h']))


@Inject
def classic_master_wipe(master_communicator=INJECTED):
    (num_banks, bank_size, write_size) = (256, 256, 10)
    print('Wiping the master...')
    for bank in range(0, num_banks):
        print('-  Wiping bank {0}'.format(bank))
        for addr in range(0, bank_size, write_size):
            master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': bank, 'address': addr, 'data': '\xff' * write_size}
            )

    master_communicator.do_command(master_api.activate_eeprom(), {'eep': 0})
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


@Inject
def classic_master_reset(master_communicator=INJECTED):
    print('Resetting...')
    try:
        master_communicator.do_command(master_api.reset())
        print('Done resetting')
        sys.exit(0)
    except CommunicationTimedOutException:
        print('Failed resetting')
        sys.exit(1)


def classic_hardreset():
    # type: () -> None
    print('Performing hard reset...')
    gpio_dir = open('/sys/class/gpio/gpio44/direction', 'w')
    gpio_dir.write('out')
    gpio_dir.close()

    def power(master_on):
        """ Set the power on the master. """
        gpio_file = open('/sys/class/gpio/gpio44/value', 'w')
        gpio_file.write('1' if master_on else '0')
        gpio_file.close()

    power(False)
    time.sleep(5)
    power(True)
    print('Done performing hard reset')


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

    config = ConfigParser()
    config.read(constants.get_config_file())

    port = config.get('OpenMotics', 'controller_serial')

    if args.port:
        print(port)
        return

    if not any([args.sync, args.version, args.reset, args.wipe, args.update]):
        parser.print_help()

    platform = Platform.get_platform()

    if args.hardreset:
        if platform == Platform.Type.CORE_PLUS:
            raise NotImplementedError()
        else:
            classic_hardreset()
        return

    Injectable.value(controller_serial=Serial(port, 115200))

    if platform == Platform.Type.CORE_PLUS:
        from master.core import core_communicator
        _ = core_communicator
    else:
        from master.classic import master_communicator
        _ = master_communicator

    @Inject
    def start(master_communicator=INJECTED):
        master_communicator.start()
    start()

    try:

        if args.sync:
            if platform == Platform.Type.CORE_PLUS:
                core_master_sync()
            else:
                classic_master_sync()
        elif args.version:
            if platform == Platform.Type.CORE_PLUS:
                raise NotImplementedError()
            else:
                classic_master_version()
        elif args.reset:
            if platform == Platform.Type.CORE_PLUS:
                core_master_reset()
            else:
                classic_master_reset()
        elif args.wipe:
            if platform == Platform.Type.CORE_PLUS:
                raise NotImplementedError()
            else:
                classic_master_wipe()
        elif args.update:
            if platform == Platform.Type.CORE_PLUS:
                core_master_update(args.master_firmware_core)
            else:
                classic_master_update(args.master_firmware_classic)

    finally:

        @Inject
        def stop(master_communicator=INJECTED):
            master_communicator.stop()
            time.sleep(4)
        stop()


if __name__ == '__main__':
    main()
