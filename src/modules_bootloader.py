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
Tool to bootload the slave modules (output, dimmer, input, temperature, ...)
"""
from __future__ import absolute_import
from platform_utils import System, Platform
System.import_libs()

import argparse
import time
import os
import sys
import logging
from ioc import INJECTED, Inject
from gateway.initialize import setup_platform

logger = logging.getLogger("openmotics")


def setup_logger():
    """ Setup the OpenMotics logger. """

    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


def main():
    supported_modules = ['O', 'R', 'D', 'I', 'T', 'C']

    parser = argparse.ArgumentParser(description='Tool to bootload the slave modules.')

    parser.add_argument('-t', '--type', dest='type', choices=supported_modules + [m.lower() for m in supported_modules], required=True,
                        help='The type of module to bootload (choices: {0})'.format(', '.join(supported_modules)))
    parser.add_argument('-f', '--file', dest='file', required=True,
                        help='The filename of the hex file to bootload')
    parser.add_argument('-v', '--version', dest='version', required=False,
                        help='The version of the firmware to flash')
    parser.add_argument('--verbose', dest='verbose', action='store_true',
                        help='Show the serial output')

    args = parser.parse_args()
    module_type = args.type.upper()
    filename = args.file
    version = args.version

    setup_platform(message_client_name=None)  # No MessageClient needed

    if Platform.get_platform() == Platform.Type.CORE_PLUS:
        from master.core.slave_updater import SlaveUpdater

        @Inject
        def get_communicator(master_communicator=INJECTED):
            return master_communicator

        core_communicator = get_communicator()
        core_communicator.start()
        try:
            update_success = SlaveUpdater.update_all(module_type=module_type,
                                                     hex_filename=filename,
                                                     version=version)
        finally:
            core_communicator.stop()
            time.sleep(5)
    else:
        from master.classic.slave_updater import bootload_modules

        try:
            if os.path.getsize(args.file) <= 0:
                print('Could not read hex or file is empty: {0}'.format(args.file))
                return False
        except OSError as ex:
            print('Could not open hex: {0}'.format(ex))
            return False

        update_success = bootload_modules(module_type=module_type,
                                          filename=filename,
                                          logger=logger.info)

    return update_success


if __name__ == '__main__':
    setup_logger()
    success = main()
    if not success:
        sys.exit(1)
