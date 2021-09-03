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
from collections import namedtuple
from urlparse import urlparse, urlunparse
from ioc import INJECTED, Inject, Injectable
from logs import Logs
from gateway.dto import ModuleDTO
from gateway.daemon_thread import DaemonThread
from gateway.models import Config, EnergyModule, Module
from platform_utils import Platform, System
from gateway.enums import EnergyEnums, ModuleType, UpdateEnums, HardwareType

if False:  # MYPY
    from typing import Any, List, Union, Optional, Tuple, Dict, Set
    from gateway.module_controller import ModuleController
    from gateway.hal.master_controller import MasterController
    from gateway.energy_module_controller import EnergyModuleController
    from logging import Logger

# Different name to reduce confusion between multiple used loggers
global_logger = logging.getLogger(__name__)

FirmwareInfo = namedtuple('FirmwareInfo', 'code  module_types')


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
    FIRMWARE_INFO_MAP = {'temperature': FirmwareInfo('TE', [ModuleType.SENSOR]),
                         'input': FirmwareInfo('IT', [ModuleType.INPUT]),
                         'input_gen3': FirmwareInfo('IT', [ModuleType.INPUT]),
                         'output': FirmwareInfo('OT', [ModuleType.OUTPUT, ModuleType.SHUTTER]),
                         'output_gen3': FirmwareInfo('RY', [ModuleType.OUTPUT]),
                         'dimmer': FirmwareInfo('DL', [ModuleType.DIM_CONTROL]),
                         'dimmer_gen3': FirmwareInfo('ZL', [ModuleType.DIM_CONTROL]),
                         'can': FirmwareInfo('CL', [ModuleType.CAN_CONTROL]),
                         'can_gen3': FirmwareInfo('CL', [ModuleType.CAN_CONTROL]),
                         'ucan': FirmwareInfo('MN', [ModuleType.MICRO_CAN]),
                         'master_classic': FirmwareInfo('GY', []),
                         'master_coreplus': FirmwareInfo('BN', []),
                         'energy': FirmwareInfo('EY', []),
                         'p1_concentrator': FirmwareInfo('PR', [])}  # type: Dict[str, FirmwareInfo]
    MODULE_TYPE_MAP = {'temperature': {2: 'temperature'},
                       'input': {2: 'input', 3: 'input_gen3'},
                       'output': {2: 'output', 3: 'output_gen3'},
                       'shutter': {2: 'output'},
                       'dim_control': {2: 'dimmer', 3: 'dimmer_gen3'},
                       'can_control': {2: 'can', 3: 'can_gen3'},
                       'ucan': {3: 'ucan'},
                       'master_classic': {2: 'master_classic'},
                       'master_core': {3: 'master_coreplus'},
                       'energy': {3: 'energy'},
                       'p1_concentrator': {3: 'p1_concentrator'}}  # type: Dict[str, Dict[int, str]]

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
        self._update_thread = None  # type: Optional[DaemonThread]
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
        modules = {}  # type: Dict[str, List[Module]]
        for module in Module.select().where(Module.hardware_type == HardwareType.PHYSICAL):
            modules.setdefault(module.module_type, []).append(module)
        global_logger.info('Request for update to {0}'.format(new_version))
        platform = Platform.get_platform()
        if metadata is None:
            response = requests.get(url=self._get_update_metadata_url(version=new_version),
                                    timeout=2)
            if response.status_code != 200:
                raise ValueError('Failed to get update metadata for {0}'.format(new_version))
            metadata = response.json()
        target_versions = {}
        for firmware in metadata.get('firmwares', []):
            version = firmware['version']
            firmware_type = firmware['type']
            if firmware_type not in UpdateController.SUPPORTED_FIRMWARES.get(platform, []):
                global_logger.info('Skip firmware {0} as it is unsupported on platform {1}'.format(firmware_type, platform))
                continue
            target_versions[firmware_type] = {'target_version': version}
            if firmware_type in UpdateController.FIRMWARE_INFO_MAP:
                module_types = UpdateController.FIRMWARE_INFO_MAP[firmware_type].module_types
                for module_type in module_types:
                    for module in modules.get(module_type, []):
                        if module.firmware_version != version:
                            module.update_success = None  # Allow the update to be re-tried
                            module.save()
            global_logger.info('Request for update firmware {0} to {1}'.format(firmware_type, version))
        Config.set_entry('firmware_target_versions', target_versions)

    def _execute_pending_updates(self):
        if self._update_threshold > time.time():
            return  # Wait a bit, making sure the service is completely up-and-running before starting updates

        success, target_version = UpdateController._get_target_version_info('gateway_service')
        gateway_service_up_to_date = success and target_version == gateway.__version__

        firmware_types = UpdateController.SUPPORTED_FIRMWARES.get(Platform.get_platform(), [])
        for firmware_type in firmware_types:
            success, target_version = UpdateController._get_target_version_info(firmware_type)
            if target_version is None:
                continue  # Nothing can be done
            if success is not None:
                continue  # Update was successfull, or it failed (but retries are not yet supported)

            component_logger = Logs.get_update_logger(name=firmware_type)
            if firmware_type == 'gateway_service':
                try:
                    component_logger.info('Updating gateway_service to {0}'.format(target_version))
                    # Validate whether an update is needed
                    if target_version == gateway.__version__:
                        component_logger.info('Firmware for gateway_service up-to-date')
                        UpdateController._register_version_success(firmware_type, success=True)
                        continue  # Already up-to-date
                    # Check whether `current` isn't already pointing to the target version (would indicate some version mismatch)
                    target_version_folder = UpdateController.SERVICE_BASE_TEMPLATE.format(target_version)
                    if os.path.exists(UpdateController.SERVICE_CURRENT) and target_version_folder == os.readlink(UpdateController.SERVICE_CURRENT):
                        raise RuntimeError('Symlinked current version seems not what the code states it should be')
                    # Read failure report
                    failure_filename = UpdateController.SERVICE_BASE_TEMPLATE.format('{0}.failure'.format(target_version))
                    if os.path.exists(failure_filename):
                        with open(failure_filename, 'w') as failure:
                            failure_content = failure.read()
                        os.remove(failure_filename)
                        raise RuntimeError('Update failure reported: {0}'.format(failure_content))
                    # Download archive if needed
                    filename = UpdateController.SERVICE_BASE_TEMPLATE.format('gateway_{0}.tgz'.format(target_version))
                    if not os.path.exists(filename):
                        self._load_firmware(firmware_type=firmware_type,
                                            version=target_version,
                                            logger=component_logger,
                                            target_filename=filename)
                    # Start actual update
                    component_logger.info('Detaching gateway_service update process')
                    UpdateController._execute(command=['python',
                                                       os.path.join(UpdateController.PREFIX, 'python', 'openmotics_update.py'),
                                                       '--execute-gateway-service-update',
                                                       target_version],
                                              logger=component_logger)
                    time.sleep(300)  # Wait 5 minutes, the service should be stopped by above detached process anyway
                except Exception as ex:
                    component_logger.error('Could not update gateway_service to {0}: {1}'.format(target_version, ex))
                    UpdateController._register_version_success(firmware_type, success=False)
                continue

            if not gateway_service_up_to_date:
                # Every other firmware should only be installed when the gateway is up-to-date
                # TODO: Implement proper dependencies
                continue

            if firmware_type == 'gateway_frontend':
                try:
                    self._update_gateway_frontend(new_version=target_version,
                                                  logger=component_logger)
                    success = True
                except Exception as ex:
                    component_logger.error('Could not update gateway_frontend to {0}: {1}'.format(target_version, ex))
                    success = False
                UpdateController._register_version_success(firmware_type, success=success)
                continue

            # Hex firmwares
            try:
                self._update_module_firmware(firmware_type=firmware_type,
                                             target_version=target_version,
                                             mode=UpdateEnums.Modes.AUTOMATIC,
                                             module_address=None)
            except Exception as ex:
                component_logger.error('Could not update {0} to {1}: {2}'.format(firmware_type, target_version, ex))

    def update_module_firmware(self, module_type, target_version, mode, module_address, firmware_filename=None):
        # type: (str, str, str, Optional[str], Optional[str]) -> Tuple[int, int]
        if module_type not in UpdateController.MODULE_TYPE_MAP:
            raise RuntimeError('Cannot update unknown module type {0}'.format(module_type))
        # Load firmware type
        parsed_version = tuple(int(part) for part in target_version.split('.'))
        if module_type in ['master_classic', 'master_core']:
            generation = 3 if parsed_version < (2, 0, 0) else 2  # Core = 1.x.x, classic = 3.x.x
        elif module_type in ['energy', 'p1_concentrator']:
            generation = 3  # Generation doesn't matter for these modules
        else:
            generation = 3 if parsed_version >= (6, 0, 0) else 2  # Gen3 = 6.x.x, gen2 = 3.x.x
        if generation not in UpdateController.MODULE_TYPE_MAP[module_type]:
            raise RuntimeError('Calculated generation {0} is not suppored on {1}'.format(generation, module_type))
        firmware_type = UpdateController.MODULE_TYPE_MAP[module_type][generation]
        platform = Platform.get_platform()
        if firmware_type not in UpdateController.SUPPORTED_FIRMWARES.get(platform, []):
            raise RuntimeError('Firmware {0} cannot be updated on platform {1}'.format(firmware_type, platform))
        # Execute update
        return self._update_module_firmware(firmware_type=firmware_type,
                                            target_version=target_version,
                                            mode=mode,
                                            module_address=module_address,
                                            firmware_filename=firmware_filename)

    def _update_module_firmware(self, firmware_type, target_version, mode, module_address, firmware_filename=None):
        # type: (str, str, str, Optional[str], Optional[str]) -> Tuple[int, int]
        component_logger = Logs.get_update_logger(name=firmware_type)

        if firmware_type not in UpdateController.FIRMWARE_INFO_MAP:
            raise RuntimeError('Dynamic update for {0} not yet supported'.format(firmware_type))

        if firmware_type in ['master_classic', 'master_coreplus']:
            return self._update_master_firmware(firmware_type=firmware_type,
                                                target_version=target_version,
                                                firmware_filename=firmware_filename,
                                                logger=component_logger,
                                                mode=mode)
        elif firmware_type in ['energy', 'p1_concentrator']:
            return self._update_energy_firmware(firmware_type=firmware_type,
                                                target_version=target_version,
                                                module_address=module_address,
                                                firmware_filename=firmware_filename,
                                                logger=component_logger,
                                                mode=mode)
        else:
            return self._update_master_slave_firmware(firmware_type=firmware_type,
                                                      target_version=target_version,
                                                      module_address=module_address,
                                                      firmware_filename=firmware_filename,
                                                      logger=component_logger,
                                                      mode=mode)

    def _update_master_slave_firmware(self, firmware_type, target_version, module_address, firmware_filename, logger, mode):
        # type: (str, str, Optional[str], Optional[str], Logger, str) -> Tuple[int, int]
        module_types = UpdateController.FIRMWARE_INFO_MAP[firmware_type].module_types
        where_expression = ((Module.source == ModuleDTO.Source.MASTER) &
                            (Module.hardware_type == HardwareType.PHYSICAL) &
                            (Module.module_type.in_(module_types)))
        if module_address is not None:
            where_expression &= (Module.address == module_address)
        modules = Module.select().where(where_expression)  # type: List[Module]

        modules_to_update = UpdateController._filter_modules_to_update(all_modules=modules,
                                                                       target_version=target_version,
                                                                       mode=mode)
        if not modules_to_update:
            return 0, 0

        filename_code = UpdateController.FIRMWARE_INFO_MAP[firmware_type].code
        filename_base = UpdateController.FIRMWARE_NAME_TEMPLATE.format(filename_code)
        target_filename = UpdateController.FIRMWARE_FILENAME_TEMPLATE.format(filename_base.format(target_version))
        self._load_firmware(firmware_type=firmware_type,
                            version=target_version,
                            logger=logger,
                            target_filename=target_filename,
                            source_filename=firmware_filename)

        successes, failures = 0, 0
        for module in modules:
            module_address = module.address
            individual_logger = Logs.get_update_logger('{0}_{1}'.format(firmware_type, module_address))
            try:
                new_version = self._master_controller.update_slave_module(firmware_type=firmware_type,
                                                                          address=module_address,
                                                                          hex_filename=target_filename,
                                                                          version=target_version)
                if new_version is not None:
                    module.firmware_version = new_version
                module.last_online_update = int(time.time())
                module.update_success = True
                successes += 1
            except Exception as ex:
                individual_logger.exception('Error when updating {0}: {1}'.format(firmware_type, ex))
                module.update_success = False
                failures += 1
            module.save()
        return successes, failures

    def _update_energy_firmware(self, firmware_type, target_version, module_address, firmware_filename, logger, mode):
        # type: (str, str, Optional[str], Optional[str], Logger, str) -> Tuple[int, int]
        module_version = {'energy': EnergyEnums.Version.ENERGY_MODULE,
                          'p1_concentrator': EnergyEnums.Version.P1_CONCENTRATOR}[firmware_type]
        where_expression = ((EnergyModule.version == module_version) &
                            (Module.hardware_type == HardwareType.PHYSICAL))
        if module_address is not None:
            where_expression &= (Module.address == module_address)
        modules = [em.module for em in EnergyModule.select(EnergyModule, Module)
                                                   .join_from(EnergyModule, Module)
                                                   .where(where_expression)]  # type: List[Module]

        modules_to_update = UpdateController._filter_modules_to_update(all_modules=modules,
                                                                       target_version=target_version,
                                                                       mode=mode)
        if not modules_to_update:
            return 0, 0

        filename_code = UpdateController.FIRMWARE_INFO_MAP[firmware_type].code
        filename_base = UpdateController.FIRMWARE_NAME_TEMPLATE.format(filename_code)
        target_filename = UpdateController.FIRMWARE_FILENAME_TEMPLATE.format(filename_base.format(target_version))
        self._load_firmware(firmware_type=firmware_type,
                            version=target_version,
                            logger=logger,
                            target_filename=target_filename,
                            source_filename=firmware_filename)

        successes, failures = 0, 0
        for module in modules_to_update:
            module_address = module.address
            individual_logger = Logs.get_update_logger('{0}_{1}'.format(EnergyEnums.VERSION_TO_STRING[module_version], module_address))
            try:
                new_version = self._energy_module_controller.update_module(module_version=module_version,
                                                                           module_address=module_address,
                                                                           firmware_filename=target_filename,
                                                                           firmware_version=target_version)
                if new_version is not None:
                    module.firmware_version = new_version
                module.last_online_update = int(time.time())
                module.update_success = True
                successes += 1
            except Exception as ex:
                individual_logger.exception('Error when updating {0}: {1}'.format(firmware_type, ex))
                module.update_success = False
                failures += 1
            module.save()
        return successes, failures

    @staticmethod
    def _filter_modules_to_update(all_modules, target_version, mode):
        # type: (List[Module], str, str) -> List[Module]
        modules_to_update = []
        for module in all_modules:
            if module.firmware_version == target_version:
                # Only update an alread-up-to-date module if it's forced
                if mode == UpdateEnums.Modes.FORCED:
                    modules_to_update.append(module)
                else:
                    module.update_success = True
                    module.save()
            else:
                # When an outdated module is automatic updated, it should
                # take the update_success into account (no retries yet), but
                # otherwise (manual or forced) it can be updated
                if mode == UpdateEnums.Modes.AUTOMATIC:
                    if module.update_success is None:
                        modules_to_update.append(module)
                else:
                    modules_to_update.append(module)
        return modules_to_update

    def _update_master_firmware(self, firmware_type, target_version, firmware_filename, logger, mode):
        # type: (str, str, Optional[str], Logger, str) -> Tuple[int, int]
        try:
            try:
                current_version = '.'.join(str(e) for e in self._master_controller.get_firmware_version())  # type: Optional[str]
            except Exception:
                current_version = None
            if mode != UpdateEnums.Modes.FORCED and current_version == target_version:
                logger.info('Master already up-to-date')
                UpdateController._register_version_success(firmware_type, success=True)
                return 0, 0

            filename_code = UpdateController.FIRMWARE_INFO_MAP[firmware_type].code
            filename_base = UpdateController.FIRMWARE_NAME_TEMPLATE.format(filename_code)
            target_filename = UpdateController.FIRMWARE_FILENAME_TEMPLATE.format(filename_base.format(target_version))
            self._load_firmware(firmware_type=firmware_type,
                                version=target_version,
                                logger=logger,
                                target_filename=target_filename,
                                source_filename=firmware_filename)

            self._master_controller.update_master(hex_filename=target_filename,
                                                  version=target_version)
            UpdateController._register_version_success(firmware_type, success=True)
            return 1, 0
        except Exception as ex:
            logger.exception('Error when updating {0}: {1}'.format(firmware_type, ex))
            UpdateController._register_version_success(firmware_type, success=False)
            return 0, 1

    def _update_gateway_frontend(self, new_version, logger):
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
            logger.info('Firmware for gateway_frontend up-to-date')
            return

        new_version_folder = UpdateController.FRONTEND_BASE_TEMPLATE.format(new_version)
        if not os.path.exists(new_version_folder):
            os.mkdir(new_version_folder)

            # Download firmware
            filename = UpdateController.FRONTEND_BASE_TEMPLATE.format('frontend_{0}.tgz'.format(new_version))
            self._load_firmware(firmware_type='gateway_frontend',
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

        # Cleanup
        UpdateController._clean_old_versions(base_template=UpdateController.SERVICE_BASE_TEMPLATE,
                                             logger=logger)

        logger.info('Update completed')

    @staticmethod
    def update_gateway_service(new_version, logger):
        # type: (str, Logger) -> None
        """ Executed from within a separate process """
        logger.info('Stopping services')
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
            logger.info('Extracting archive')
            os.makedirs(os.path.join(new_version_folder, 'python'))
            UpdateController._extract_tgz(filename=UpdateController.SERVICE_BASE_TEMPLATE.format('gateway_{0}.tgz'.format(new_version)),
                                          output_dir=os.path.join(new_version_folder, 'python'),
                                          logger=logger)

            # Copy `etc`
            logger.info('Copy `etc` folder')
            shutil.copytree(os.path.join(old_version_folder, 'etc'), os.path.join(new_version_folder, 'etc'))

            # Restore plugins
            logger.info('Copy plugins...')
            plugins = glob.glob('{0}{1}*{1}'.format(UpdateController.PLUGINS_DIRECTORY_TEMPLATE.format(old_version), os.path.sep))
            for plugin_path in plugins:
                plugin = plugin_path.strip('/').rsplit('/', 1)[-1]
                logger.info('Copy plugin {0}'.format(plugin))
                UpdateController._execute(command=['cp', '-R',
                                                   os.path.join(UpdateController.PLUGINS_DIRECTORY_TEMPLATE.format(old_version), plugin),
                                                   os.path.join(UpdateController.PLUGINS_DIRECTORY_TEMPLATE.format(new_version), '')],
                                          logger=logger)

            # Install pip dependencies
            logger.info('Installing pip dependencies')
            os.makedirs(os.path.join(new_version_folder, 'python-deps'))
            operating_system = System.get_operating_system()['ID']
            if operating_system != System.OS.BUILDROOT:
                temp_dir = tempfile.mkdtemp(dir=UpdateController.PREFIX)
                UpdateController._execute(
                    command='env TMPDIR={0} PYTHONUSERBASE={1}/python-deps python {1}/python/libs/pip.whl/pip install --no-index --user {1}/python/libs/{2}/*.whl'.format(
                        temp_dir, new_version_folder, operating_system
                    ),
                    logger=logger,
                    shell=True
                )
                os.rmdir(temp_dir)

        # Keep track of the old version, so it can be manually restored if something goes wrong
        logger.info('Tracking previous version')
        if os.path.exists(UpdateController.SERVICE_PREVIOUS):
            os.unlink(UpdateController.SERVICE_PREVIOUS)
        os.symlink(old_version_folder, UpdateController.SERVICE_PREVIOUS)

        # Symlink to new version
        logger.info('Symlink to new version')
        os.unlink(UpdateController.SERVICE_CURRENT)
        os.symlink(new_version_folder, UpdateController.SERVICE_CURRENT)

        # Prepare new code for first startup
        logger.info('Preparing for first startup')
        UpdateController._execute(command=['python',
                                           os.path.join(UpdateController.PREFIX, 'python', 'openmotics_update.py'),
                                           '--prepare-gateway-service-for-first-startup',
                                           new_version],
                                  logger=logger)

        # Startup
        logger.info('Starting services')
        System.run_service_action('start', 'openmotics')
        System.run_service_action('start', 'vpn_service')

        # Health-check
        logger.info('Checking health')
        update_successful = UpdateController._check_gateway_service_health(logger=logger)

        if not update_successful:
            logger.info('Update failed, restoring')
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

        # Cleanup
        os.unlink(UpdateController.SERVICE_PREVIOUS)
        UpdateController._clean_old_versions(base_template=UpdateController.SERVICE_BASE_TEMPLATE,
                                             logger=logger)

        logger.info('Update completed')

    @staticmethod
    def update_gateway_service_prepare_for_first_startup(logger):
        # type: (Logger) -> None
        """ Executed from within a separate process """
        # This is currently empty, but might in the future be used for:
        #  * Updating the supervisor service files
        #  * Changing system settings mandatory for the services to startup
        # This code will execute after the new version is in place and before the
        # services are started. It runs the new code, has the new imports
        # available, ...
        logger.info('Preparation for first startup completed')

    @staticmethod
    def get_update_state():
        state = 2  # 0 = ERROR, 1 = UPDATING, 2 = OK
        modules = {}  # type: Dict[str, List[Module]]
        for module in Module.select().where(Module.hardware_type == HardwareType.PHYSICAL):
            modules.setdefault(module.module_type, []).append(module)
        firmware_types = UpdateController.SUPPORTED_FIRMWARES.get(Platform.get_platform(), [])
        for firmware_type in firmware_types:
            success, target_version = UpdateController._get_target_version_info(firmware_type)
            if target_version is None:
                continue
            if firmware_type in ['gateway_service', 'gateway_frontend', 'master_classic', 'master_coreplus']:
                if success is None:
                    state = min(state, 1)  # Update in progress
                if success is False:
                    state = min(state, 0)  # Update failed
                    break
            else:
                for module_type in UpdateController.FIRMWARE_INFO_MAP[firmware_type].module_types:
                    for module in modules.get(module_type, []):
                        if module.firmware_version == target_version:
                            continue  # Up to date
                        update_success = module.update_success
                        if update_success is None:
                            state = min(state, 1)  # Update in progress
                        if update_success is False:
                            state = min(state, 0)  # Update failed
                            break
                    if state == 0:
                        break
            if state == 0:
                break
        return {0: UpdateEnums.States.ERROR,
                1: UpdateEnums.States.UPDATING,
                2: UpdateEnums.States.OK}[state]

    @staticmethod
    def _get_target_version_info(firmware_type):
        # type: (str) -> Tuple[Optional[bool], Optional[str]]
        target_versions = Config.get_entry('firmware_target_versions', None)  # type: Optional[Dict[str, Dict[str, Any]]]
        if target_versions is None:
            target_versions = {}
            Config.set_entry('firmware_target_versions', target_versions)
            return None, None
        if firmware_type not in target_versions:
            return None, None
        target_version_info = target_versions[firmware_type]
        return target_version_info.get('success'), target_version_info['target_version']

    @staticmethod
    def _register_version_success(firmware_type, success):
        # type: (str, bool) -> None
        target_versions = Config.get_entry('firmware_target_versions', None)  # type: Optional[Dict[str, Dict[str, Any]]]
        if target_versions is None:
            return
        target_versions[firmware_type]['success'] = success
        Config.set_entry('firmware_target_versions', target_versions)

    @staticmethod
    def _clean_old_versions(base_template, logger):
        logger.info('Clean up old versions')
        versions = set()  # type: Set[str]
        current_version = None  # type: Optional[str]
        previous_version = None  # type: Optional[str]
        for version_path in glob.glob(base_template.format('*')):
            version = version_path.strip('/').rsplit('/', 1)[-1]
            if 'tgz' in version:
                continue
            if version == 'current':
                current_version = os.readlink(base_template.format(version)).split(os.path.sep)[-1]

            elif version == 'previous':
                previous_version = os.readlink(base_template.format(version)).split(os.path.sep)[-1]
            else:
                versions.add(version)
        versions_to_keep = set(sorted(versions, key=lambda v: tuple(int(i) for i in v.split('.')), reverse=True)[:3])
        if current_version is not None:
            versions_to_keep.add(current_version)
        if previous_version is not None:
            versions_to_keep.add(previous_version)
        for version in versions:
            if version in versions_to_keep:
                logger.info('Keeping {0}'.format(version))
                continue
            logger.info('Removing {0}'.format(version))
            shutil.rmtree(base_template.format(version))

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

    def _load_firmware(self, firmware_type, version, logger, target_filename, source_filename=None):
        # type: (str, str, Logger, str, Optional[str]) -> None
        if source_filename is not None:
            if source_filename != target_filename:
                shutil.copy(src=source_filename,
                            dst=target_filename)
            return

        response = requests.get(self._get_update_firmware_metadata_url(firmware_type, version), timeout=2)
        if response.status_code != 200:
            raise ValueError('Failed to get update firmware metadata for {0} {1}'.format(firmware_type, version))
        metadata = response.json()
        # Example metadata:
        # > {'type': 'master_coreplus',
        # >  'version': '3.12.3'
        # >  'dependencies': ['gateway_service >= 3.1.1'],
        # >  'sha256': 'abcdef',
        # >  'urls': ['https://foo.bar/master-coreplus_3.12.3.hex',
        # >           'https://foo.bar/master-coreplus_3.12.3.hex'],
        # >  'url': 'https://foo.bar/master-coreplus_3.12.3.hex'}
        # Where the order of download is based on `firmware.get('urls', [firmware['url']])`
        UpdateController._download_urls(urls=metadata.get('urls', [metadata['url']]),
                                        checksum=metadata['sha256'],
                                        logger=logger,
                                        target_filename=target_filename)

    @staticmethod
    def _download_urls(urls, checksum, logger, target_filename):  # type: (List[str], str, Logger, str) -> None
        downloaded = False
        with open(target_filename, 'w') as handle:
            for url in urls:
                try:
                    response = requests.get(url, stream=True)
                    shutil.copyfileobj(response.raw, handle)
                    downloaded = True
                except Exception as ex:
                    logger.error('Could not download firmware from {0}: {1}'.format(url, ex))
        if not downloaded:
            raise RuntimeError('No update could be downloaded')
        hasher = hashlib.sha256()
        with open(target_filename, 'rb') as f:
            hasher.update(f.read())
        calculated_hash = hasher.hexdigest()
        if calculated_hash != checksum:
            raise RuntimeError('Downloaded firmware {0} checksum {1} does not match'.format(target_filename, calculated_hash))

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
