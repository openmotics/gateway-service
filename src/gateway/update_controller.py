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
Update Controller
"""
from __future__ import absolute_import
import re
import time
import tempfile
import glob
import os
import logging
import constants
import requests
import gateway
import hashlib
import shutil
import subprocess
from urlparse import urlparse, urlunparse
from ioc import INJECTED, Inject, Injectable
from logs import Logs
from gateway.daemon_thread import DaemonThread
from gateway.models import Config
from platform_utils import Platform, System
from gateway.enums import EnergyEnums

if False:  # MYPY
    from typing import Any, List, Union, Optional, TextIO, Dict
    from gateway.module_controller import ModuleController
    from gateway.hal.master_controller import MasterController
    from gateway.energy_module_controller import EnergyModuleController
    from logging import Logger

# Different name to reduce confusion between multiple used loggers
global_logger = logging.getLogger(__name__)

# TODO: Migrate gateway-os update to gateway-service


@Injectable.named('update_controller')
class UpdateController(object):

    UPDATE_DELAY = 120

    PREFIX = constants.OPENMOTICS_PREFIX  # e.g. /x
    VERSIONS_FOLDER = os.path.join(PREFIX, 'versions')  # e.g. /x/versions
    VERSIONS_BASE_TEMPLATE = os.path.join(VERSIONS_FOLDER, '{0}', '{1}')  # e.g. /x/versions/{0}/{1}
    VERSIONS_CURRENT_TEMPLATE = VERSIONS_BASE_TEMPLATE.format('{0}', 'current')  # e.g. /x/versions/{0}/current
    VERSIONS_PREVIOUS_TEMPLATE = VERSIONS_BASE_TEMPLATE.format('{0}', 'previous')  # e.g. /x/versions/{0}/previous

    SERVICE_BASE_TEMPLATE = VERSIONS_BASE_TEMPLATE.format('service', '{0}')  # e.g. /x/versions/service/{0}
    SERVICE_CURRENT = VERSIONS_CURRENT_TEMPLATE.format('service')  # e.g. /x/versions/service/current
    SERVICE_PREVIOUS = VERSIONS_PREVIOUS_TEMPLATE.format('service')  # e.g. /x/versions/service/previous
    PLUGINS_DIRECTORY_TEMPLATE = os.path.join(SERVICE_BASE_TEMPLATE, 'python', 'plugins')  # e.g. /x/versions/service/{0}/python/plugins

    FRONTEND_BASE_TEMPLATE = VERSIONS_BASE_TEMPLATE.format('frontend', '{0}')  # e.g. /x/versions/frontend/{0}
    FRONTEND_CURRENT = VERSIONS_CURRENT_TEMPLATE.format('frontend')  # e.g. /x/versions/frontend/current
    FRONTEND_PREVIOUS = VERSIONS_PREVIOUS_TEMPLATE.format('frontend')  # e.g. /x/versions/frontend/previous

    FIRMWARE_FILENAME_TEMPLATE = VERSIONS_BASE_TEMPLATE.format('firmwares', '{0}')  # e.g. /x/versions/firmwares/{0}
    FIRMWARE_NAME_TEMPLATE = 'OMF{0}_{{0}}.hex'
    FIRMWARE_CODE_MAP = {'temperature': ('TE', ['T']),
                         'input': ('IT', ['I']), 'input_gen3': ('IT', ['I']),
                         'output': ('OT', ['O', 'R']), 'output_gen3': ('RY', ['O']),
                         'dimmer': ('DL', ['D']), 'dimmer_gen3': ('ZL', ['D']),
                         'can': ('CL', ['C']), 'can_gen3': ('CL', ['C']),
                         'ucan': ('MN', ['UC']),
                         'master_classic': ('GY', ['M']),
                         'master_coreplus': ('BN', ['M']),
                         'energy': ('EY', ['E']),
                         'p1_concentrator': ('PR', ['P'])}
    MODULE_TYPE_MAP = {'temperature': {2: 'temperature'},
                       'input': {2: 'input', 3: 'input_gen3'},
                       'output': {2: 'output', 3: 'output_gen3'},
                       'shutter': {2: 'output'},
                       'dim_control': {2: 'dimmer', 3: 'dimmer_gen3'},
                       'can_control': {2: 'can', 3: 'can_gen3'},
                       'ucan': {3: 'ucan'},
                       'master_classic': {2: 'master_classic'},
                       'master_core': {3: 'master_coreplus'},
                       'energy': {2: 'energy', 3: 'energy'},
                       'p1_concentrator': {3: 'p1_concentrator'}}

    # Below order of services are important, this is the order in which the updates will be performed
    SUPPORTED_FIRMWARES = {Platform.Type.CORE: ['gateway_service', 'gateway_frontend',
                                                'master_coreplus',
                                                'input_gen3', 'output_gen3', 'dimmer_gen3', 'can_gen3', 'ucan',
                                                'energy', 'p1_concentrator'],
                           Platform.Type.CORE_PLUS: ['gateway_service', 'gateway_frontend',
                                                     'master_coreplus',
                                                     'input_gen3', 'output_gen3', 'dimmer_gen3', 'can_gen3', 'ucan',
                                                     'energy', 'p1_concentrator'],
                           Platform.Type.CLASSIC: ['gateway_service', 'gateway_frontend',
                                                   'master_classic',
                                                   'input', 'output', 'dimmer', 'can',
                                                   'energy', 'p1_concentrator'],
                           Platform.Type.ESAFE: ['gateway_service']}

    @Inject
    def __init__(self, gateway_uuid=INJECTED, module_controller=INJECTED, master_controller=INJECTED, energy_module_controller=INJECTED, cloud_url=INJECTED):
        # type: (str, ModuleController, MasterController, EnergyModuleController, str) -> None
        self._update_thread = None  # Optional[DaemonThread]
        self._gateway_uuid = gateway_uuid
        self._module_controller = module_controller
        self._master_controller = master_controller
        self._energy_module_controller = energy_module_controller
        self._cloud_url = cloud_url

        if not os.path.exists(UpdateController.VERSIONS_FOLDER):
            global_logger.info('Creating {0}'.format(UpdateController.VERSIONS_FOLDER))
            os.makedirs(UpdateController.VERSIONS_FOLDER)
        for kind in ['service', 'frontend', 'firmwares']:
            path = os.path.join(UpdateController.VERSIONS_FOLDER, kind)
            if not os.path.exists(path):
                global_logger.info('Creating {0}'.format(path))
                os.makedirs(path)

        self._update_threshold = time.time() + UpdateController.UPDATE_DELAY

    def start(self):
        self._update_thread = DaemonThread(name='update_controller',
                                           target=self._execute_pending_updates,
                                           interval=60,
                                           delay=300)
        self._update_thread.start()

    def stop(self):
        if self._update_thread is not None:
            self._update_thread.stop()

    def request_update(self, new_version, metadata=None):
        """
        Example metadata:
        > {'version': '1.2.3',
        >  'firmwares': [{'type': 'master_coreplus',
        >                 'version': '3.12.3'
        >                 'dependencies': ['gateway_service >= 3.1.1'],
        >                 'sha256': 'abcdef',
        >                 'urls': ['https://foo.bar/master-coreplus_3.12.3.hex',
        >                          'https://foo.bar/master-coreplus_3.12.3.hex'],
        >                 'url': 'https://foo.bar/master-coreplus_3.12.3.hex'}]}
        Where the order of download is based on `firmware.get('urls', [firmware['url']])`
        """
        global_logger.info('Request for update to {0}'.format(new_version))
        platform = Platform.get_platform()
        if metadata is None:
            response = requests.get(url=self._get_update_metadata_url(version=new_version),
                                    timeout=2)
            if response.status_code != 200:
                raise ValueError('Failed to get update metadata for {0}'.format(new_version))
            metadata = response.json()
        for firmware in metadata.get('firmwares', []):
            version = firmware['version']
            firmware_type = firmware['type']
            if firmware_type not in UpdateController.SUPPORTED_FIRMWARES.get(platform, []):
                global_logger.info('Skip firmware {0} as it is unsupported on platform {1}'.format(firmware_type, platform))
                continue
            Config.set_entry('firmware_{0}'.format(firmware_type), {'target_version': version, 'failure': False})
            global_logger.info('Request for update firmware {0} to {1}'.format(firmware_type, version))

    def _execute_pending_updates(self):
        if self._update_threshold > time.time():
            return  # Wait a bit, making sure the service is completely up-and-running before starting updates

        firmware_types = UpdateController.SUPPORTED_FIRMWARES.get(Platform.get_platform(), [])
        for firmware_type in firmware_types:
            config_key = 'firmware_{0}'.format(firmware_type)
            config_data = Config.get_entry(key=config_key,
                                           fallback=None)  # type: Optional[Dict[str, Any]]
            if config_data is None:
                continue
            if config_data['failure']:
                continue  # Update failed, no retry for now
            target_version = config_data['target_version']  # type: str

            component_logger = Logs.get_update_logger(name=firmware_type)
            try:
                if firmware_type == 'gateway_service':
                    component_logger.info('Updating gateway_service to {0}'.format(target_version))
                    # Validate whether an update is needed
                    if target_version == gateway.__version__:
                        component_logger.info('Firmware for gateway_service already up-to-date')
                        Config.remove_entry(key=config_key)
                        continue  # Already up-to-date
                    # Check whether `current` isn't already pointing to the target version (would indicate some version mismatch)
                    target_version_folder = UpdateController.SERVICE_BASE_TEMPLATE.format(target_version)
                    if os.path.exists(UpdateController.SERVICE_CURRENT) and target_version_folder == os.readlink(UpdateController.SERVICE_CURRENT):
                        raise RuntimeError('Symlinked current version seems not what the code states it should be')
                    # Read failure report
                    failure_filename = UpdateController.SERVICE_BASE_TEMPLATE.format('{0}.failure'.format(target_version))
                    if os.path.exists(failure_filename):
                        with open(failure_filename, 'w') as failure:
                            raise RuntimeError('Update failure reported: {0}'.format(failure.read()))
                    # Download archive if needed
                    filename = UpdateController.SERVICE_BASE_TEMPLATE.format('gateway_{0}.tgz'.format(target_version))
                    if not os.path.exists(filename):
                        self._download_firmware(firmware_type=firmware_type,
                                                version=target_version,
                                                logger=component_logger,
                                                target_filename=filename)
                    # Start actual update
                    component_logger.info('Detaching gateway_service update process')
                    UpdateController._execute(command=['python',
                                                       os.path.join(UpdateController.PREFIX, 'python', 'openmotics_update.py'),
                                                       '--update-gateway-service',
                                                       target_version],
                                              logger=component_logger)
                    time.sleep(300)  # Wait 5 minutes, the service should be stopped by above detached process anyway

                elif firmware_type == 'gateway_frontend':
                    self.update_gateway_frontend(new_version=target_version,
                                                 logger=component_logger)
                    Config.remove_entry(key=config_key)

                else:  # Hex firmwares
                    self._update_module_firmware(firmware_type=firmware_type,
                                                 target_version=target_version)
                    Config.remove_entry(key=config_key)
            except Exception as ex:
                component_logger.error('Could not update {0} to {1}: {2}'.format(firmware_type, target_version, ex))
                config_data['failure'] = True
                Config.set_entry(key=config_key,
                                 value=config_data)

    def update_module_firmware(self, module_type, target_version):
        # type: (str, str) -> None
        if module_type not in UpdateController.MODULE_TYPE_MAP:
            raise RuntimeError('Cannot update unknown module type {0}'.format(module_type))
        # Load firmware type
        parsed_version = tuple(int(part) for part in target_version.split('.'))
        if module_type in ['master_classic', 'master_core']:
            generation = 3 if parsed_version < (2, 0, 0) else 2  # Core = 1.x.x, classic = 3.x.x
        else:
            generation = 3 if parsed_version >= (6, 0, 0) else 2  # Gen3 = 6.x.x, gen2 = 3.x.x
        if generation not in UpdateController.MODULE_TYPE_MAP[module_type]:
            raise RuntimeError('Calculated generation {0} is not suppored on {1}'.format(generation, module_type))
        firmware_type = UpdateController.MODULE_TYPE_MAP[module_type][generation]
        platform = Platform.get_platform()
        if firmware_type not in UpdateController.SUPPORTED_FIRMWARES.get(platform, []):
            raise RuntimeError('Firmware {0} cannot be updated on platform {1}'.format(firmware_type, platform))
        # Execute update
        self._update_module_firmware(firmware_type=firmware_type,
                                     target_version=target_version)

    def _update_module_firmware(self, firmware_type, target_version):
        # type: (str, str) -> None
        component_logger = Logs.get_update_logger(name=firmware_type)

        if firmware_type not in UpdateController.FIRMWARE_CODE_MAP:
            raise RuntimeError('Dynamic update for {0} not yet supported'.format(firmware_type))

        platform = Platform.get_platform()
        filename_code = UpdateController.FIRMWARE_CODE_MAP[firmware_type][0]

        if firmware_type in ['master_classic', 'master_coreplus']:
            try:
                current_version = '.'.join(str(e) for e in self._master_controller.get_firmware_version())  # type: Optional[str]
            except Exception:
                current_version = None
            if current_version == target_version:
                component_logger.info('Master already up-to-date')
                return

            filename_base = UpdateController.FIRMWARE_NAME_TEMPLATE.format(filename_code)
            target_filename = UpdateController.FIRMWARE_FILENAME_TEMPLATE.format(filename_base.format(target_version))
            self._download_firmware(firmware_type=firmware_type,
                                    version=target_version,
                                    logger=component_logger,
                                    target_filename=target_filename)
            self._master_controller.update_master(hex_filename=target_filename,
                                                  version=target_version)
            UpdateController._archive_firmwares(target_filename=target_filename,
                                                filename_base=filename_base)
            return

        if platform in Platform.ClassicTypes and firmware_type == 'ucan':
            return  # A uCAN cannot be updated on the Classic platform for now

        filename_base = UpdateController.FIRMWARE_NAME_TEMPLATE.format(filename_code)
        target_filename = UpdateController.FIRMWARE_FILENAME_TEMPLATE.format(filename_base.format(target_version))
        self._download_firmware(firmware_type=firmware_type,
                                version=target_version,
                                logger=component_logger,
                                target_filename=target_filename)

        if firmware_type in ['energy', 'p1_concentrator']:
            module_version = {'energy': EnergyEnums.Version.ENERGY_MODULE,
                              'p1_concentrator': EnergyEnums.Version.P1_CONCENTRATOR}[firmware_type]
            failures = self._energy_module_controller.update_modules(module_version=module_version,
                                                                     firmware_filename=target_filename,
                                                                     firmware_version=target_version)
            for module_address, exception in failures.items():
                if exception is not None:
                    component_logger.error('Updating energy module {0} failed: {1}'.format(module_address, exception))
            UpdateController._archive_firmwares(target_filename=target_filename,
                                                filename_base=filename_base)
            return

        module_codes = UpdateController.FIRMWARE_CODE_MAP[firmware_type][1]
        for module_code in module_codes:
            self._master_controller.update_slave_modules(firmware_type=firmware_type,
                                                         module_type=module_code,
                                                         hex_filename=target_filename,
                                                         version=target_version)
        UpdateController._archive_firmwares(target_filename=target_filename,
                                            filename_base=filename_base)

    def update_gateway_frontend(self, new_version, logger):
        logger.info('Updating gateway_frontend to {0}'.format(new_version))

        # Migrate legacy folder structure, if needed
        if not os.path.exists(UpdateController.FRONTEND_CURRENT):
            current_version = 'legacy'
            try:
                with open(os.path.join(UpdateController.PREFIX, 'static', 'index.html'), 'r') as index:
                    match = re.search(r"v([0-9]+?\.[0-9]+?\.[0-9]+)", index.read())
                    if match is not None:
                        current_version = match.groups()[0]
            except Exception as ex:
                logger.warning('Could not parse current frontend version while migrating legacy structure: {0}'.format(ex))
            old_version_folder = UpdateController.FRONTEND_BASE_TEMPLATE.format(current_version)
            os.makedirs(old_version_folder)
            os.symlink(old_version_folder, UpdateController.FRONTEND_CURRENT)

            old_location = os.path.join(UpdateController.PREFIX, 'static')
            new_location = os.path.join(UpdateController.FRONTEND_CURRENT, 'static')
            shutil.move(old_location, new_location)
            os.symlink(new_location, old_location)

        old_version = os.readlink(UpdateController.FRONTEND_CURRENT).split(os.path.sep)[-1]
        if old_version == new_version:
            # Already up-to-date
            logger.info('Firmware for gateway_frontend already up-to-date')
            return

        new_version_folder = UpdateController.FRONTEND_BASE_TEMPLATE.format(new_version)
        if not os.path.exists(new_version_folder):
            os.mkdir(new_version_folder)

            # Download firmware
            filename = UpdateController.FRONTEND_BASE_TEMPLATE.format('frontend_{0}.tgz'.format(new_version))
            self._download_firmware(firmware_type='gateway_frontend',
                                    version=new_version,
                                    logger=logger,
                                    target_filename=filename)

            # Extract new version
            logger.info('Extracting archive')
            os.makedirs(os.path.join(new_version_folder, 'static'))
            UpdateController._extract_tgz(filename=filename,
                                          output_dir=os.path.join(new_version_folder, 'static'),
                                          logger=logger)

        # Symlink to new version
        logger.info('Symlink to new version')
        os.unlink(UpdateController.FRONTEND_CURRENT)
        os.symlink(new_version_folder, UpdateController.FRONTEND_CURRENT)

        logger.info('Update completed')

    @staticmethod
    def update_gateway_service(new_version):
        """ Executed from within a separate process """
        component_logger = Logs.get_update_logger('gateway_service')
        try:
            component_logger.info('Stopping services')
            System.run_service_action('stop', 'openmotics')
            System.run_service_action('stop', 'vpn_service')

            # Migrate legacy folder structure, if needed
            if not os.path.exists(UpdateController.SERVICE_CURRENT):
                old_version_folder = UpdateController.SERVICE_BASE_TEMPLATE.format(gateway.__version__)
                os.makedirs(old_version_folder)
                os.symlink(old_version_folder, UpdateController.SERVICE_CURRENT)

                for folder in ['python', 'etc', 'python-deps']:
                    old_location = os.path.join(UpdateController.PREFIX, folder)
                    new_location = os.path.join(UpdateController.SERVICE_CURRENT, folder)
                    shutil.move(old_location, new_location)
                    os.symlink(new_location, old_location)

            old_version = os.readlink(UpdateController.SERVICE_CURRENT).split(os.path.sep)[-1]
            old_version_folder = UpdateController.SERVICE_BASE_TEMPLATE.format(old_version)
            new_version_folder = UpdateController.SERVICE_BASE_TEMPLATE.format(new_version)

            if not os.path.exists(new_version_folder):
                os.mkdir(new_version_folder)

                # Extract new version
                component_logger.info('Extracting archive')
                os.makedirs(os.path.join(new_version_folder, 'python'))
                UpdateController._extract_tgz(filename=UpdateController.SERVICE_BASE_TEMPLATE.format('gateway_{0}.tgz'.format(new_version)),
                                              output_dir=os.path.join(new_version_folder, 'python'),
                                              logger=component_logger)

                # Copy `etc`
                component_logger.info('Copy `etc` folder')
                shutil.copytree(os.path.join(old_version_folder, 'etc'), os.path.join(new_version_folder, 'etc'))

                # Restore plugins
                component_logger.info('Copy plugins')
                plugins = glob.glob('{0}{1}*{1}'.format(UpdateController.PLUGINS_DIRECTORY_TEMPLATE.format(old_version), os.path.sep))
                for plugin in plugins:
                    UpdateController._execute(command=['cp', '-R',
                                                       os.path.join(UpdateController.PLUGINS_DIRECTORY_TEMPLATE.format(old_version), plugin),
                                                       os.path.join(UpdateController.PLUGINS_DIRECTORY_TEMPLATE.format(new_version), '')],
                                              logger=component_logger)

                # Install pip dependencies
                component_logger.info('Installing pip dependencies')
                os.makedirs(os.path.join(new_version_folder, 'python-deps'))
                operating_system = System.get_operating_system()['ID']
                if operating_system != System.OS.BUILDROOT:
                    temp_dir = tempfile.mkdtemp(dir=UpdateController.PREFIX)
                    UpdateController._execute(
                        command='env TMPDIR={0} PYTHONUSERBASE={1}/python-deps python {1}/python/libs/pip.whl/pip install --no-index --user {1}/python/libs/{2}/*.whl'.format(
                            temp_dir, new_version_folder, operating_system
                        ),
                        logger=component_logger,
                        shell=True
                    )
                    os.rmdir(temp_dir)

            # Keep track of the old version, so it can be manually restored if something goes wrong
            component_logger.info('Tracking previous version')
            if os.path.exists(UpdateController.SERVICE_PREVIOUS):
                os.unlink(UpdateController.SERVICE_PREVIOUS)
            os.symlink(old_version_folder, UpdateController.SERVICE_PREVIOUS)

            # Symlink to new version
            component_logger.info('Symlink to new version')
            os.unlink(UpdateController.SERVICE_CURRENT)
            os.symlink(new_version_folder, UpdateController.SERVICE_CURRENT)

            # Startup
            component_logger.info('Starting services')
            System.run_service_action('start', 'openmotics')
            System.run_service_action('start', 'vpn_service')

            # Health-check
            component_logger.info('Checking health')
            update_successful = UpdateController._check_gateway_service_health(logger=component_logger)

            if not update_successful:
                component_logger.info('Update failed, restoring')
                # Stop services again
                System.run_service_action('stop', 'openmotics')
                System.run_service_action('stop', 'vpn_service')
                # Symlink rollback to old version
                os.unlink(UpdateController.SERVICE_CURRENT)
                os.symlink(old_version_folder, UpdateController.SERVICE_CURRENT)
                # Start services again
                System.run_service_action('start', 'openmotics')
                System.run_service_action('start', 'vpn_service')
                # Raise with actual reason
                raise RuntimeError('Failed to start {0}'.format(new_version))

            os.unlink(UpdateController.SERVICE_PREVIOUS)
            component_logger.info('Update completed')
        except Exception as ex:
            with open(UpdateController.SERVICE_BASE_TEMPLATE.format('{0}.failure'.format(new_version)), 'w') as failure:
                failure.write('Failed to update gateway_service to {0}: {1}'.format(new_version, ex))
            raise

    @staticmethod
    def _check_gateway_service_health(logger, timeout=60):
        since = time.time()
        pending = ['unknown']
        http_port = Platform.http_port()
        while since > time.time() - timeout:
            try:
                response = requests.get('http://127.0.0.1:{}/health_check'.format(http_port), timeout=2)
                data = response.json()
                if data['success']:
                    pending = [k for k, v in data['health'].items() if not v['state']]
                    if not pending:
                        return True
            except Exception:
                pass
            time.sleep(10)
        logger.error('Health-check failed with pending {0}'.format(', '.join(pending)))
        return False

    @staticmethod
    def _extract_tgz(filename, output_dir, logger):
        UpdateController._execute(command=['tar', '--no-same-owner', '-xzf', filename, '-C', output_dir],
                                  logger=logger)

    @staticmethod
    def _execute(command, logger, **kwargs):
        # type: (Union[str, List[str]], Logger, Any) -> str
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                close_fds=True, **kwargs)
        output = b''
        if proc.stdout is not None:
            for line in proc.stdout:
                if line:
                    logger.info(line.rstrip(b'\n'))
                output += line
        return_code = proc.wait()
        if return_code != 0:
            raise Exception('Command {} failed'.format(command))
        return str(output)

    def _download_firmware(self, firmware_type, version, logger, target_filename=None):
        """
        Example metadata:
        > {'type': 'master_coreplus',
        >  'version': '3.12.3'
        >  'dependencies': ['gateway_service >= 3.1.1'],
        >  'sha256': 'abcdef',
        >  'urls': ['https://foo.bar/master-coreplus_3.12.3.hex',
        >           'https://foo.bar/master-coreplus_3.12.3.hex'],
        >  'url': 'https://foo.bar/master-coreplus_3.12.3.hex'}
        Where the order of download is based on `firmware.get('urls', [firmware['url']])`
        """
        response = requests.get(self._get_update_firmware_metadata_url(firmware_type, version), timeout=2)
        if response.status_code != 200:
            raise ValueError('Failed to get update firmware metadata for {0} {1}'.format(firmware_type, version))
        metadata = response.json()
        return UpdateController._download_urls(urls=metadata.get('urls', [metadata['url']]),
                                               checksum=metadata['sha256'],
                                               logger=logger,
                                               target_filename=target_filename)

    @staticmethod
    def _download_urls(urls, checksum, logger, target_filename=None):  # type: (List[str], str, Logger, Optional[str]) -> Optional[str]
        handle = None  # type: Optional[TextIO]
        filename = None  # type: Optional[str]
        downloaded = False
        try:
            if target_filename is None:
                file_descripor, filename = tempfile.mkstemp()
                handle = os.fdopen(file_descripor, 'w')
            else:
                filename = target_filename
                handle = open(filename, 'w')
            if handle is None or filename is None:
                raise RuntimeError('Could not open {0} to store firmware'.format(filename))
            for url in urls:
                try:
                    response = requests.get(url, stream=True)
                    shutil.copyfileobj(response.raw, handle)
                    downloaded = True
                except Exception as ex:
                    logger.error('Could not download firmware from {0}: {1}'.format(url, ex))
        finally:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
        if not downloaded:
            raise RuntimeError('No update could be downloaded')
        hasher = hashlib.sha256()
        with open(filename, 'rb') as f:
            hasher.update(f.read())
        calculated_hash = hasher.hexdigest()
        if calculated_hash != checksum:
            raise RuntimeError('Downloaded firmware {0} checksum {1} does not match'.format(filename, calculated_hash))
        return filename

    def _get_update_metadata_url(self, version):
        query = 'uuid={0}'.format(self._gateway_uuid)
        update_url = Config.get_entry('update_metadata_url', None)  # type: Optional[str]
        if update_url is None:
            parsed_url = urlparse(self._cloud_url)
            path = '/api/v1/base/updates/metadata/{0}'.format(version)
        else:
            parsed_url = urlparse(update_url)
            path = parsed_url.path
        return urlunparse((parsed_url.scheme, parsed_url.netloc, path, '', query, ''))

    def _get_update_firmware_metadata_url(self, firmware_type, version):
        query = 'uuid={0}'.format(self._gateway_uuid)
        update_url = Config.get_entry('update_firmware_metadata_url', None)  # type: Optional[str]
        if update_url is None:
            parsed_url = urlparse(self._cloud_url)
            path = '/api/v1/base/updates/metadata/firmwares/{0}/{1}'.format(firmware_type, version)
        else:
            parsed_url = urlparse(update_url)
            path = parsed_url.path
        return urlunparse((parsed_url.scheme, parsed_url.netloc, path, '', query, ''))

    @staticmethod
    def _archive_firmwares(target_filename, filename_base):
        # type: (str, str) -> None
        # For below examples; /y = /x/versions/firmwares
        current_filename = UpdateController.FIRMWARE_FILENAME_TEMPLATE.format(filename_base.format('current'))  # e.g. /y/OMFXY_current.hex
        current_target = None
        if os.path.exists(current_filename):
            current_target = os.readlink(current_filename)  # e.g. /y/OMFXY_1.0.1.hex
        previous_filename = UpdateController.FIRMWARE_FILENAME_TEMPLATE.format(filename_base.format('previous'))  # e.g. /y/OMFXY_previous.hex
        if target_filename == current_target:
            return  # No real update, no need to remove the previous
        if os.path.exists(previous_filename):
            os.unlink(previous_filename)
        if os.path.exists(current_filename):
            os.unlink(current_filename)
        if current_target is not None:
            os.symlink(current_target, previous_filename)  # /foo/OMFXY_previous.hex -> /foo/OMFXY_1.0.1.hex
        os.symlink(target_filename, current_filename)  # /foo/OMFXY_current.hex -> /foo/OMFXY_1.0.2.hex
