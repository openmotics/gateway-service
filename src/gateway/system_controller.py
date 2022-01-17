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
System BLL
"""
from __future__ import absolute_import

import glob
import io
import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import tarfile
from threading import Timer

from six.moves.configparser import ConfigParser

import constants
from bus.om_bus_events import OMBusEvents
from gateway.base_controller import BaseController
from ioc import INJECTED, Inject, Injectable, Singleton
from platform_utils import System

if False:  # MYPY
    from typing import Dict, Any, List, Optional, Iterable
    from gateway.watchdog import Watchdog
    from gateway.module_controller import ModuleController
    from bus.om_bus_client import MessageClient

logger = logging.getLogger(__name__)


@Injectable.named('system_controller')
@Singleton
class SystemController(BaseController):

    @Inject
    def __init__(self, master_controller=INJECTED, module_controller=INJECTED, message_client=INJECTED):
        super(SystemController, self).__init__(master_controller)
        self._module_controller = module_controller  # type: ModuleController
        self._message_client = message_client  # type: MessageClient

    # Time related

    def set_timezone(self, timezone):
        _ = self  # Not static for consistency
        timezone_file_path = '/usr/share/zoneinfo/' + timezone
        if not os.path.isfile(timezone_file_path):
            raise RuntimeError('Could not find timezone \'' + timezone + '\'')
        if os.path.exists(constants.get_timezone_file()):
            os.remove(constants.get_timezone_file())
        os.symlink(timezone_file_path, constants.get_timezone_file())
        # Make sure python refreshes the timezone information
        time.tzset()
        if self._message_client is not None:
            self._message_client.send_event(OMBusEvents.TIME_CHANGED, {})

    def get_timezone(self):
        try:
            path = os.readlink(constants.get_timezone_file())
            if not path.startswith('/usr/share/zoneinfo/'):
                # Reset timezone to default setting
                logger.error('Unexpected timezone path {0}, reset to UTC'.format(path))
                self.set_timezone('UTC')
                return 'UTC'
            if path.startswith('/usr/share/zoneinfo/posix'):
                # As seen on the buildroot os, the timezone info is all located in the posix folder within zoneinfo.
                return path[26:]
            return path[20:]
        except Exception:
            logger.exception('Could not parse current timezone, reset to UTC')
            return 'UTC'

    def get_python_timezone(self):
        _ = self
        return time.tzname[0]

    # Backup and restore functions

    def get_full_backup(self):
        """
        Get a backup (tar) of the master eeprom, the sqlite databases and the plugins

        :returns: Tar containing multiple files: master.eep, config.db, scheduled.db, power.db,
        eeprom_extensions.db, metrics.db and plugins as a string of bytes.
        """
        _ = self  # Not static for consistency

        def backup_sqlite_db(input_db_path, backup_db_path):
            """ Backup an sqlite db provided the path to the db to backup and the backup db. """
            # Connect to database
            connection = sqlite3.connect(input_db_path)
            cursor = connection.cursor()

            # Lock database before making a backup
            cursor.execute('begin immediate')

            # Make new backup file
            shutil.copyfile(input_db_path, backup_db_path)

            # Unlock database
            connection.rollback()

        tmp_dir = tempfile.mkdtemp()
        tmp_sqlite_dir = '{0}/sqlite'.format(tmp_dir)
        os.mkdir(tmp_sqlite_dir)

        try:
            with open('{0}/master.eep'.format(tmp_sqlite_dir), 'w') as eeprom_file:
                eeprom_file.write(self._module_controller.get_master_backup())

            for filename, source in {'config.db': constants.get_config_database_file(),
                                     'power.db': constants.get_power_database_file(),
                                     'eeprom_extensions.db': constants.get_eeprom_extension_database_file(),
                                     'metrics.db': constants.get_metrics_database_file(),
                                     'gateway.db': constants.get_gateway_database_file()}.items():
                if os.path.exists(source):
                    target = '{0}/{1}'.format(tmp_sqlite_dir, filename)
                    backup_sqlite_db(source, target)

            # Backup plugins
            tmp_plugin_dir = '{0}/{1}'.format(tmp_dir, 'plugins')
            tmp_plugin_content_dir = '{0}/{1}'.format(tmp_plugin_dir, 'content')
            tmp_plugin_config_dir = '{0}/{1}'.format(tmp_plugin_dir, 'config')
            os.mkdir(tmp_plugin_dir)
            os.mkdir(tmp_plugin_content_dir)
            os.mkdir(tmp_plugin_config_dir)

            plugin_dir = constants.get_plugin_dir()
            plugins = [name for name in os.listdir(plugin_dir) if os.path.isdir(os.path.join(plugin_dir, name))]
            for plugin in plugins:
                shutil.copytree(plugin_dir + plugin, '{0}/{1}/'.format(tmp_plugin_content_dir, plugin))

            config_files = constants.get_plugin_configfiles()
            for config_file in glob.glob(config_files):
                shutil.copy(config_file, '{0}/'.format(tmp_plugin_config_dir))

            # Backup hex files
            tmp_hex_dir = '{0}/{1}'.format(tmp_dir, 'hex')
            os.mkdir(tmp_hex_dir)
            hex_files = constants.get_hex_files()
            for hex_file in glob.glob(hex_files):
                shutil.copy(hex_file, '{0}/'.format(tmp_hex_dir))

            # Backup general config stuff
            tmp_config_dir = '{0}/{1}'.format(tmp_dir, 'config')
            os.mkdir(tmp_config_dir)
            config_dir = constants.get_config_dir()
            for file_name in ['openmotics.conf', 'https.key', 'https.crt']:
                shutil.copy(os.path.join(config_dir, file_name), '{0}/'.format(tmp_config_dir))

            retcode = subprocess.call('cd {0}; tar cf backup.tar *'.format(tmp_dir), shell=True)
            if retcode != 0:
                raise Exception('The backup tar could not be created.')

            with open('{0}/backup.tar'.format(tmp_dir), 'r') as backup_file:
                return backup_file.read()

        finally:
            shutil.rmtree(tmp_dir)

    def restore_full_backup(self, data):
        """
        Restore a full backup containing the master eeprom and the sqlite databases.

        :param data: The backup to restore.
        :type data: Tar containing multiple files: master.eep, config.db, scheduled.db, power.db,
        eeprom_extensions.db, metrics.db and plugins as a string of bytes.
        :returns: dict with 'output' key.
        """
        import glob
        import shutil
        import tempfile
        import subprocess

        tmp_dir = tempfile.mkdtemp()
        tmp_sqlite_dir = '{0}/sqlite'.format(tmp_dir)
        try:
            with open('{0}/backup.tar'.format(tmp_dir), 'wb') as backup_file:
                backup_file.write(data)

            retcode = subprocess.call('cd {0}; tar xf backup.tar'.format(tmp_dir), shell=True)
            if retcode != 0:
                raise Exception('The backup tar could not be extracted.')

            # Check if the sqlite db's are in a folder or not for backwards compatibility
            src_dir = tmp_sqlite_dir if os.path.isdir(tmp_sqlite_dir) else tmp_dir

            with open('{0}/master.eep'.format(src_dir), 'r') as eeprom_file:
                eeprom_content = eeprom_file.read()
                self._module_controller.master_restore(data=eeprom_content)

            for filename, target in {'config.db': constants.get_config_database_file(),
                                     'users.db': constants.get_config_database_file(),
                                     'power.db': constants.get_power_database_file(),
                                     'eeprom_extensions.db': constants.get_eeprom_extension_database_file(),
                                     'metrics.db': constants.get_metrics_database_file(),
                                     'gateway.db': constants.get_gateway_database_file()}.items():
                source = '{0}/{1}'.format(src_dir, filename)
                if os.path.exists(source):
                    shutil.copyfile(source, target)

            # Restore the plugins if there are any
            backup_plugin_dir = '{0}/plugins'.format(tmp_dir)
            backup_plugin_content_dir = '{0}/content'.format(backup_plugin_dir)
            backup_plugin_config_files = '{0}/config/pi_*'.format(backup_plugin_dir)

            if os.path.isdir(backup_plugin_dir):
                plugin_dir = constants.get_plugin_dir()
                plugins = [name for name in os.listdir(backup_plugin_content_dir) if os.path.isdir(os.path.join(backup_plugin_content_dir, name))]
                for plugin in plugins:
                    dest_dir = '{0}{1}'.format(plugin_dir, plugin)
                    if os.path.isdir(dest_dir):
                        shutil.rmtree(dest_dir)
                    shutil.copytree('{0}/{1}/'.format(backup_plugin_content_dir, plugin), '{0}{1}'.format(plugin_dir, plugin))

                config_files = constants.get_plugin_config_dir()
                for config_file in glob.glob(backup_plugin_config_files):
                    shutil.copy(config_file, '{0}/'.format(config_files))

            return {'output': 'Restore complete'}

        finally:
            shutil.rmtree(tmp_dir)
            # Restart the Cherrypy server after 1 second. Lets the current request terminate.
            Timer(1, lambda: os._exit(0)).start()

    def factory_reset(self, can=True):
        # type: (bool) -> Dict[str,Any]
        try:
            argv = ['python2', 'openmotics_cli.py', 'operator', 'factory-reset']
            if can:
                argv.append('--can')
            subprocess.check_output(argv)
        except subprocess.CalledProcessError as exc:
            return {'success': False, 'factory_reset': exc.output.strip()}

        self.restart_services(service_names=['openmotics'])
        if can:
            return {'factory_reset_full': 'pending'}
        return {'factory_reset': 'pending'}

    def restart_services(self, service_names=None):
        # type: (Optional[Iterable[str]]) -> Dict[str,Any]
        def _restart(_service_names):
            # type: (Iterable[str]) -> None
            logger.info('Restarting services...')
            for service_name in _service_names:
                System.restart_service(service_name)

        if service_names is None:
            service_names = System.SERVICES

        Timer(2, _restart, args=[service_names]).start()
        return {'restart_services': 'pending'}

    def get_logs(self):
        fh = io.BytesIO()
        with tarfile.open(fileobj=fh, mode='w:gz') as archive:
            archive.add('/var/log/supervisor', recursive=True)
        return fh.getvalue()

    @Inject
    def set_self_recovery(self, active, watchdog=INJECTED):  # type: (bool, Watchdog) -> None
        if active:
            watchdog.start()
        else:
            watchdog.stop()

    def is_esafe_touchscreen_calibrated(self):
        _ = self
        return os.path.exists(constants.get_esafe_touchscreen_calibration_file())

    def calibrate_esafe_touchscreen(self):
        _ = self
        try:
            argv = ['TSLIB_CONSOLEDEVICE=none', 'ts_calibrate']
            subprocess.check_output(argv)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError('Could not calibrate touchscreen: {}'.format(exc))
