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
Module to update an RS485 slave
"""

from __future__ import absolute_import
from platform_utils import System
System.import_libs()

import sys
import logging
import constants
from six.moves.configparser import ConfigParser
from serial import Serial
from ioc import Injectable
from master.core.rs485_updater import RS485Updater
from master.core.core_communicator import CoreCommunicator

logger = logging.getLogger("openmotics")


def setup_logger():
    """ Setup the OpenMotics logger. """

    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage:')
        print('{0} address version firmware_filename'.format(sys.argv[0]))
        sys.exit(1)
    address = sys.argv[1]
    version = sys.argv[2]
    firmware_filename = sys.argv[3]

    setup_logger()

    config = ConfigParser()
    config.read(constants.get_config_file())
    controller_serial_port = config.get('OpenMotics', 'controller_serial')
    Injectable.value(controller_serial=Serial(controller_serial_port, 115200))
    core_communicator = CoreCommunicator()
    core_communicator.start()
    Injectable.value(master_communicator=core_communicator)

    RS485Updater.update(address=address, version=version, hex_filename=firmware_filename)
    core_communicator.stop()
