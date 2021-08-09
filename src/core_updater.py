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
Module to work update a Core
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
from logs import Logs
from master.core.core_updater import CoreUpdater

logger = logging.getLogger('openmotics')



if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage:')
        print('{0} firmware_filename'.format(sys.argv[0]))
        sys.exit(1)
    firmware_filename = sys.argv[1]

    config = ConfigParser()
    config.read(constants.get_config_file())
    core_cli_serial_port = config.get('OpenMotics', 'cli_serial')
    Injectable.value(cli_serial=Serial(core_cli_serial_port, 115200))
    Injectable.value(master_communicator=None)
    Injectable.value(maintenance_communicator=None)

    Logs.setup_logger()
    CoreUpdater.update(hex_filename=firmware_filename)
