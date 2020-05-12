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
The main module for the OpenMotics
"""
from __future__ import absolute_import

from platform_utils import System
System.import_libs()

import logging
import os
import time

import constants
from ioc import INJECTED, Inject
from master import setup_platform

logger = logging.getLogger("openmotics")


def setup_logger():
    """ Setup the OpenMotics logger. """

    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


@Inject
def factory_reset(master_controller=INJECTED):
    import glob
    import shutil

    logger.info('Rebooting master...')
    master_controller.cold_reset()
    time.sleep(5)

    logger.info('Wiping master eeprom...')
    master_controller.start()
    master_controller.factory_reset()
    master_controller.stop()

    logger.info('Removing databases...')
    # Delete databases.
    for f in constants.get_all_database_files():
        if os.path.exists(f):
            os.remove(f)

    # Delete plugins
    logger.info('Removing plugins...')
    plugin_dir = constants.get_plugin_dir()
    plugins = [name for name in os.listdir(plugin_dir)
               if os.path.isdir(os.path.join(plugin_dir, name))]
    for plugin in plugins:
        shutil.rmtree(plugin_dir + plugin)

    config_files = constants.get_plugin_configfiles()
    for config_file in glob.glob(config_files):
        os.remove(config_file)


if __name__ == '__main__':
    setup_logger()
    setup_platform()

    lock_file = constants.get_init_lockfile()
    if os.path.isfile(lock_file):
        with open(lock_file) as fd:
            content = fd.read()

        if content == 'factory_reset':
            logger.info('Running factory reset...')

            factory_reset()

            logger.info('Running factory reset, done')
        else:
            logger.warning('unknown initialization {}'.format(content))
        os.unlink(lock_file)

    logger.info('Ready')
