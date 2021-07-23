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
Module BLL
"""
from __future__ import absolute_import
import logging
import os
import six
import time
import hashlib
import requests
import shutil
from constants import OPENMOTICS_PREFIX
from ioc import Injectable, Inject, INJECTED, Singleton
from serial_utils import CommunicationTimedOutException
from gateway.dto import ModuleDTO
from gateway.base_controller import BaseController
from gateway.models import Module
from gateway.mappers.module import ModuleMapper
from six.moves.urllib.parse import urlparse, urlunparse
from platform_utils import Platform

if False:  # MYPY
    from typing import Dict, List, Optional, Any
    from gateway.hal.master_controller import MasterController
    from gateway.energy_module_controller import EnergyModuleController

logger = logging.getLogger(__name__)


@Injectable.named('module_controller')
@Singleton
class ModuleController(BaseController):

    FIRMWARE_ARCHIVE_DIR = os.path.join(OPENMOTICS_PREFIX, 'firmwares')
    FIRMWARE_BASE_NAME = 'OMF{0}_{{0}}.hex'
    FIRMWARE_MAP = {'sensor': {2: ('T', 'TE')},
                    'input': {2: ('I', 'IT'), 3: ('I', 'IT')},
                    'output': {2: ('O', 'OT'), 3: ('O', 'RY')},
                    'shutter': {2: ('R', 'OT')},
                    'dim_control': {2: ('D', 'DL'), 3: ('D', 'ZL')},
                    'can_control': {2: ('C', 'CL'), 3: ('C', 'CL')},
                    'ucan': {3: ('UC', 'MN')},
                    'master_classic': {2: ('M', 'GY')},
                    'master_core': {3: ('M', 'BN')}}

    @Inject
    def __init__(self, master_controller=INJECTED, energy_module_controller=INJECTED):
        # type: (MasterController, EnergyModuleController) -> None
        super(ModuleController, self).__init__(master_controller, sync_interval=None)
        self._energy_module_controller = energy_module_controller

    def _sync_orm(self):
        # type: () -> bool
        if self._sync_running:
            logger.info('ORM sync (Modules): Already running')
            return False
        self._sync_running = True

        logger.info('ORM sync (Modules)')

        amounts = {None: 0, True: 0, False: 0}
        try:
            # Master slave modules (update/insert/delete)
            ids = []
            for dto in self._master_controller.get_modules_information():
                module = Module.get_or_none(source=dto.source,
                                            address=dto.address)
                if module is None:
                    module = Module.create(source=dto.source,
                                           address=dto.address,
                                           module_type=dto.module_type,
                                           hardware_type=dto.hardware_type)
                else:
                    module.module_type = dto.module_type
                    module.hardware_type = dto.hardware_type
                if dto.online:
                    module.firmware_version = dto.firmware_version
                    module.hardware_version = dto.hardware_version
                    module.last_online_update = int(time.time())
                module.order = dto.order
                module.save()
                amounts[dto.online] += 1
                ids.append(module.id)
            Module.delete().where((Module.id.not_in(ids)) & (Module.source == ModuleDTO.Source.MASTER)).execute()  # type: ignore
            # Energy modules (online update live metadata)
            for dto in self._energy_module_controller.get_modules_information():
                module = Module.get_or_none(source=dto.source,
                                            address=dto.address)
                if module is None:
                    logger.warning('ORM sync (Modules): Could not find EnergyModule {0}'.format(dto.address))
                    continue
                if dto.online:
                    module.firmware_version = dto.firmware_version
                    module.hardware_version = dto.hardware_version
                    module.last_online_update = int(time.time())
                    module.save()
                amounts[dto.online] += 1
            logger.info('ORM sync (Modules): completed ({0} online, {1} offline, {2} emulated/virtual)'.format(
                amounts[True], amounts[False], amounts[None]
            ))
        except CommunicationTimedOutException as ex:
            logger.error('ORM sync (Modules): Failed: {0}'.format(ex))
        except Exception as ex:
            logger.exception('ORM sync (Modules): Failed')
        finally:
            self._sync_running = False

        return True

    def get_modules(self):
        return self._master_controller.get_modules()

    def load_master_modules(self, address=None):  # type: (Optional[str]) -> List[ModuleDTO]
        return [ModuleMapper.orm_to_dto(module)
                for module in Module.select().where(Module.source == ModuleDTO.Source.MASTER)
                if address is None or module.address == address]

    def load_energy_modules(self, address=None):  # type: (Optional[str]) -> List[ModuleDTO]
        return [ModuleMapper.orm_to_dto(module)
                for module in Module.select().where(Module.source == ModuleDTO.Source.GATEWAY)
                if address is None or module.address == address]

    def replace_module(self, old_address, new_address):
        if old_address == new_address:
            raise RuntimeError('Old and new address cannot be identical')
        all_modules = {module.address: module for module in Module.select().where(Module.source == ModuleDTO.Source.MASTER)}  # type: Dict[str, Module]
        old_module = all_modules.get(old_address)
        new_module = all_modules.get(new_address)
        if old_module is None or new_module is None:
            raise RuntimeError('The specified modules could not be found')
        if old_module.source != new_module.source or old_module.source != ModuleDTO.Source.MASTER:
            raise RuntimeError('Only `master` modules can be replaced')
        if old_module.module_type != new_module.module_type:
            raise RuntimeError('The modules should be of the same type')
        if old_module.hardware_type != new_module.hardware_type or old_module.hardware_type != ModuleDTO.HardwareType.PHYSICAL:
            raise RuntimeError('Both modules should be physical modules')
        module_types = [[ModuleDTO.ModuleType.INPUT, ModuleDTO.ModuleType.SENSOR, ModuleDTO.ModuleType.CAN_CONTROL],
                        [ModuleDTO.ModuleType.OUTPUT, ModuleDTO.ModuleType.DIM_CONTROL],
                        [ModuleDTO.ModuleType.SHUTTER]]
        module_types_map = {mtype: mtypes
                            for mtypes in module_types
                            for mtype in mtypes}
        last_module_order = max(module.order for module in six.itervalues(all_modules)
                                if module.module_type in module_types_map[old_module.module_type])
        if new_module.order != last_module_order:
            raise RuntimeError('Only the last added module in its category can be used as replacement')
        self._master_controller.replace_module(old_address, new_address)
        if not self.run_sync_orm():
            # The sync might already be running, so we'll make sure it does a full run (again)
            self.request_sync_orm()
        new_module = Module.select().where(Module.source == new_module.source).where(Module.address == new_module.address).first()
        return (ModuleMapper.orm_to_dto(old_module),
                ModuleMapper.orm_to_dto(new_module))

    def add_virtual_module(self, module_type):  # type: (str) -> None
        if module_type == ModuleDTO.ModuleType.OUTPUT:
            self._master_controller.add_virtual_output_module()
        elif module_type == ModuleDTO.ModuleType.DIM_CONTROL:
            self._master_controller.add_virtual_dim_control_module()
        elif module_type == ModuleDTO.ModuleType.INPUT:
            self._master_controller.add_virtual_input_module()
        elif module_type == ModuleDTO.ModuleType.SENSOR:
            self._master_controller.add_virtual_sensor_module()
        else:
            raise RuntimeError('Adding a virtual module of type `{0}` is not supported'.format(module_type))

    def update_firmware(self, module_type, firmware_version):
        # type: (str, str) -> None

        if module_type not in ModuleController.FIRMWARE_MAP:
            raise RuntimeError('Dynamic update for {0} not yet supported'.format(module_type))

        parsed_version = tuple(int(part) for part in firmware_version.split('.'))
        generation = 3 if parsed_version >= (6, 0, 0) else 2
        filename_code = ModuleController.FIRMWARE_MAP[module_type][generation][1]

        platform = Platform.get_platform()
        if module_type in ['master_classic', 'master_core']:
            platform_match = (
                (platform in Platform.CoreTypes and module_type == 'master_core') or
                (platform in Platform.ClassicTypes and module_type == 'master_classic')
            )
            if not platform_match:
                raise RuntimeError('Cannot update {0} on platform {1}'.format(module_type, platform))

            filename_base = ModuleController.FIRMWARE_BASE_NAME.format(filename_code)
            target_filename = '/tmp/{0}'.format(filename_base.format(firmware_version))
            self._download_firmware(module_type, firmware_version, target_filename)
            self._master_controller.update_master(target_filename)
            ModuleController._archive_firmwares(filename_base, firmware_version)
            return

        if platform in Platform.ClassicTypes and module_type == 'ucan':
            return  # A uCAN cannot be updated on the Classic platform for now

        filename_base = ModuleController.FIRMWARE_BASE_NAME.format(filename_code)
        short_module_type = ModuleController.FIRMWARE_MAP[module_type][generation][0]
        target_filename = '/tmp/{0}'.format(filename_base.format(firmware_version))
        self._download_firmware(module_type, firmware_version, target_filename)
        self._master_controller.update_slave_modules(short_module_type, target_filename, firmware_version)
        ModuleController._archive_firmwares(filename_base, firmware_version)

    def module_discover_start(self, timeout=900):  # type: (int) -> None
        self._master_controller.module_discover_start(timeout)

    def module_discover_stop(self):  # type: () -> None
        self._master_controller.module_discover_stop()

    def module_discover_status(self):  # type: () -> bool
        return self._master_controller.module_discover_status()

    def get_module_log(self):  # type: () -> List[Dict[str, Any]]
        return self._master_controller.get_module_log()

    def get_master_status(self):
        return self._master_controller.get_status()

    def get_master_online(self):  # type: () -> bool
        return self._master_controller.get_master_online()

    def get_master_version(self):
        return self._master_controller.get_firmware_version()

    def reset_master(self, power_on=True):
        # type: (bool) -> None
        self._master_controller.cold_reset(power_on=power_on)

    def raw_master_action(self, action, size, data=None):
        # type: (str, int, Optional[bytearray]) -> Dict[str, Any]
        return self._master_controller.raw_action(action, size, data=data)

    def set_master_status_leds(self, status):
        # type: (bool) -> None
        self._master_controller.set_status_leds(status)

    def get_master_backup(self):
        return self._master_controller.get_backup()

    def master_restore(self, data):
        return self._master_controller.restore(data)

    def sync_master_time(self):  # type: () -> None
        self._master_controller.sync_time()

    def flash_leds(self, led_type, led_id):
        return self._master_controller.flash_leds(led_type, led_id)

    def master_error_list(self):
        """
        Get the error list per module (input and output modules). The modules are identified by
        O1, O2, I1, I2, ...

        :returns: dict with 'errors' key, it contains list of tuples (module, nr_errors).
        """
        return self._master_controller.error_list()

    def master_communication_statistics(self):
        return self._master_controller.get_communication_statistics()

    def master_command_histograms(self):
        return self._master_controller.get_command_histograms()

    def master_last_success(self):
        """ Get the number of seconds since the last successful communication with the master.  """
        return self._master_controller.last_success()

    def master_clear_error_list(self):
        return self._master_controller.clear_error_list()

    def get_configuration_dirty_flag(self):
        # type: () -> bool
        return self._master_controller.get_configuration_dirty_flag()

    @Inject
    def _get_firmware_url(self, module_type, version, firmware_url=INJECTED, gateway_uuid=INJECTED):
        # type: (str, str, str, str) -> str
        uri = urlparse(firmware_url)
        path = '{0}/{1}/{2}/'.format(uri.path, module_type, version)
        query = 'uuid={0}'.format(gateway_uuid)
        return urlunparse((uri.scheme, uri.netloc, path, '', query, ''))

    def _download_firmware(self, module_type, version, target_filename):
        # type: (str, str, str) -> None
        url = self._get_firmware_url(module_type, version)
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError('Failed to retrieve {0} firmware from {1}: {2}'.format(module_type, url, response.status_code))
        data = response.json()
        logger.info('Downloading {0} firmware from {1} ...'.format(module_type, data['url']))
        response = requests.get(data['url'], stream=True)
        with open(target_filename, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        logger.info('Downloading {0} firmware from {1} ... Done'.format(module_type, data['url']))

        hasher = hashlib.sha256()
        with open(target_filename, 'rb') as f:
            hasher.update(f.read())
        calculated_hash = hasher.hexdigest()
        if calculated_hash != data['sha256']:
            raise ValueError('Firmware {0} checksum sha256:{1} does not match'.format(module_type, calculated_hash))

    @staticmethod
    def _archive_firmwares(filename_base, firmware_version):
        archive_dir = ModuleController.FIRMWARE_ARCHIVE_DIR
        if not os.path.exists(archive_dir):
            os.mkdir(archive_dir)
        current_filename = os.path.join(archive_dir, filename_base.format('current'))  # e.g. /foo/OMFXY_current.hex
        current_target = None
        if os.path.exists(current_filename):
            current_target = os.readlink(current_filename)  # e.g. /foo/OMFXY_1.0.1.hex
        previous_filename = os.path.join(archive_dir, filename_base.format('previous'))  # e.g. /foo/OMFXY_previous.hex
        new_target = os.path.join(archive_dir, filename_base.format(firmware_version))  # e.g. /foo/OMFXY_1.0.2.hex
        if new_target == current_target:
            return  # No real update, no need to remove the previous
        if os.path.exists(previous_filename):
            os.unlink(previous_filename)
        if os.path.exists(current_filename):
            os.unlink(current_filename)
        os.link(current_target, previous_filename)  # OMFXY_previous.hex -> OMFXY_1.0.1.hex
        os.link(new_target, current_filename)  # OMFXY_current.hex -> OMFXY_1.0.2.hex
