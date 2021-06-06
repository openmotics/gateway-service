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
import six
import time
from ioc import Injectable, Inject, INJECTED, Singleton
from serial_utils import CommunicationTimedOutException
from gateway.dto import ModuleDTO
from gateway.base_controller import BaseController
from gateway.models import Module
from gateway.mappers.module import ModuleMapper

if False:  # MYPY
    from typing import Dict, List, Optional, Any
    from gateway.hal.master_controller import MasterController

logger = logging.getLogger("openmotics")


@Injectable.named('module_controller')
@Singleton
class ModuleController(BaseController):

    @Inject
    def __init__(self, master_controller=INJECTED):
        # type: (MasterController) -> None
        super(ModuleController, self).__init__(master_controller, sync_interval=None)

    def _sync_orm(self):
        # type: () -> bool
        if self._sync_running:
            logger.info('ORM sync (Modules): Already running')
            return False
        self._sync_running = True

        logger.info('ORM sync (Modules)')

        amounts = {None: 0, True: 0, False: 0}
        try:
            ids = []
            module_dtos = []
            module_dtos += self._master_controller.get_modules_information()
            for dto in module_dtos:
                module = Module.get_or_none(source=dto.source,
                                            address=dto.address)
                if module is None:
                    module = Module(source=dto.source,
                                    address=dto.address)
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
            Module.delete().where(Module.id.not_in(ids)).execute()  # type: ignore
            logger.info('ORM sync (Modules): completed ({0} online, {1} offline, {2} emulated/virtual)'.format(
                amounts[True], amounts[False], amounts[None]
            ))
        except CommunicationTimedOutException as ex:
            logger.error('ORM sync (Modules): Failed: {0}'.format(ex))
        except Exception:
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

    def update_master_firmware(self, hex_filename):
        self._master_controller.update_master(hex_filename)

    def update_slave_firmware(self, module_type, hex_filename):
        self._master_controller.update_slave_modules(module_type, hex_filename)

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
