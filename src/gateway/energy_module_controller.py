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
Energy Module BLL
"""
from __future__ import absolute_import

import logging

from datetime import datetime
from gateway.base_controller import BaseController
from gateway.daemon_thread import DaemonThread
from gateway.events import GatewayEvent
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from gateway.dto import RealtimeEnergyDTO, ModuleDTO, TotalEnergyDTO, EnergyModuleDTO
from gateway.enums import EnergyEnums
from gateway.maintenance_controller import InMaintenanceModeException
from gateway.mappers import EnergyModuleMapper
from gateway.models import EnergyModule, Module, EnergyCT
from gateway.energy.module_helper_energy import EnergyModuleHelper, PowerModuleHelper
from gateway.energy.module_helper_p1c import P1ConcentratorHelper
from gateway.energy.energy_api import DAY, NIGHT, EnergyAPI
from peewee import prefetch
from serial_utils import CommunicationTimedOutException
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import Dict, List, Any, Optional
    from gateway.hal.master_controller import MasterController
    from gateway.energy.module_helper import ModuleHelper
    from gateway.energy.energy_communicator import EnergyCommunicator

logger = logging.getLogger('openmotics')


@Injectable.named('energy_module_controller')
@Singleton
class EnergyModuleController(BaseController):

    @Inject
    def __init__(self, master_controller=INJECTED, energy_communicator=INJECTED, pubsub=INJECTED):
        # type: (MasterController, EnergyCommunicator, PubSub) -> None
        super(EnergyModuleController, self).__init__(master_controller)
        self._pubsub = pubsub
        self._energy_communicator = energy_communicator
        self._enabled = energy_communicator is not None
        self._sync_time_thread = None  # type: Optional[DaemonThread]

        self._energy_module_helper = EnergyModuleHelper()
        self._power_module_helper = PowerModuleHelper()
        self._p1c_helper = P1ConcentratorHelper()

        self._time_cache = {}  # type: Dict[int, List[int]]

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.POWER, self._handle_energy_event)

    def _handle_energy_event(self, master_event):
        # type: (MasterEvent) -> None
        if master_event.type == MasterEvent.Types.POWER_ADDRESS_EXIT:
            gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'powermodule'})  # TODO: Should be called energymodule
            self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def start(self):
        # type: () -> None
        super(EnergyModuleController, self).start()
        self._sync_time_thread = DaemonThread(name='energytimesync',
                                              target=self._sync_time,
                                              interval=60, delay=10)
        self._sync_time_thread.start()

    def stop(self):
        # type: () -> None
        super(EnergyModuleController, self).stop()
        if self._sync_time_thread:
            self._sync_time_thread.stop()
            self._sync_time_thread = None

    def _sync_time(self):
        # type: () -> None
        date = datetime.now()
        energy_modules = EnergyModule.select(EnergyModule, Module) \
                                     .join_from(EnergyModule, Module) \
                                     .where(EnergyModule.version != EnergyEnums.Version.P1_CONCENTRATOR)  # type: List[EnergyModule]
        for energy_module in energy_modules:
            daynight = []  # type: List[int]
            for ct in sorted(energy_module.cts, key=lambda c: c.number):
                if EnergyModuleController._is_day_time(ct.times, date):
                    daynight.append(DAY)
                else:
                    daynight.append(NIGHT)
            if self._time_cache.get(energy_module.number) != daynight:
                logger.info('Setting day/night for EnergyModule {0} to {1}'.format(energy_module.number, daynight))
                try:
                    self._energy_communicator.do_command(int(energy_module.module.address),
                                                         EnergyAPI.set_day_night(energy_module.version),
                                                         *daynight)
                    self._time_cache[energy_module.number] = daynight
                except CommunicationTimedOutException:
                    logger.warning('Could not set day/night for EnergyModule {0}: Timed out'.format(energy_module.number))

    @staticmethod
    def _is_day_time(times, date):  # type: (Optional[str], datetime) -> bool
        if not times:
            parsed_times = [0 for _ in range(14)]  # type: List[int]
        else:
            parsed_times = [int(t.replace(":", "")) for t in times.split(",")]
        day_of_week = date.weekday()  # 0 = Monday, 6 = Sunday
        current_time = date.hour * 100 + date.minute
        start = parsed_times[day_of_week * 2]
        stop = parsed_times[day_of_week * 2 + 1]
        return stop > current_time >= start

    def _get_helper(self, version):  # type: (int) -> ModuleHelper
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return self._energy_module_helper
        if version == EnergyEnums.Version.POWER_MODULE:
            return self._power_module_helper
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return self._p1c_helper
        raise NotImplementedError()

    def get_communication_statistics(self):  # type: () -> Dict[str, Any]
        if not self._enabled:
            return {'bytes_read': 0.0,
                    'bytes_written': 0.0,
                    'calls_succeeded': [],
                    'calls_timedout': []}
        return self._energy_communicator.get_communication_statistics()

    def last_success(self):
        if self._energy_communicator is None:
            return 0
        return self._energy_communicator.get_seconds_since_last_success()

    def get_day_counters(self, energy_module):  # type: (EnergyModule) -> List[int]
        if not self._enabled:
            return []
        return [0 if value is None else value
                for value in self._get_helper(version=energy_module.version).get_day_counters(energy_module=energy_module)]

    def get_night_counters(self, energy_module):  # type: (EnergyModule) -> List[int]
        if not self._enabled:
            return []
        return [0 if value is None else value
                for value in self._get_helper(version=energy_module.version).get_night_counters(energy_module=energy_module)]

    def get_total_energy(self):
        # type: () -> Dict[str, List[TotalEnergyDTO]]
        """
        Get the total energy measurement values.
        """
        if not self._enabled:
            return {}

        output = {}
        energy_modules = EnergyModule.select(EnergyModule, Module) \
                                     .join_from(EnergyModule, Module)  # type: List[EnergyModule]
        for energy_module in energy_modules:
            try:
                helper = self._get_helper(version=energy_module.version)
                day_counters = helper.get_day_counters(energy_module=energy_module)
                night_counters = helper.get_night_counters(energy_module=energy_module)
                output[str(energy_module.number)] = [TotalEnergyDTO(day=day_counters[port_id] or 0,
                                                                    night=night_counters[port_id] or 0)
                                                     for port_id in range(EnergyEnums.NUMBER_OF_PORTS[energy_module.version])]
            except InMaintenanceModeException:
                logger.info('Could not load total energy from {0}: In maintenance mode'.format(energy_module.number))
            except CommunicationTimedOutException as ex:
                logger.error('Communication timeout while fetching total energy from {0}: {1}'.format(energy_module.number, ex))
            except Exception as ex:
                logger.exception('Got exception while fetching total energy from {0}: {1}'.format(energy_module.number, ex))
        return output

    def get_realtime_energy(self):
        # type: () -> Dict[str, List[RealtimeEnergyDTO]]
        """
        Get the realtime energy measurement values.
        """
        if not self._enabled:
            return {}

        output = {}
        energy_modules = EnergyModule.select(EnergyModule, Module) \
                                     .join_from(EnergyModule, Module)  # type: List[EnergyModule]
        for energy_module in energy_modules:
            try:
                data = self._get_helper(version=energy_module.version).get_realtime(energy_module)
                output[str(energy_module.number)] = [data[port_id] for port_id in range(EnergyEnums.NUMBER_OF_PORTS[energy_module.version])]
            except InMaintenanceModeException:
                logger.info('Could not load realtime energy from {0}: In maintenance mode'.format(energy_module.number))
            except CommunicationTimedOutException as ex:
                logger.error('Communication timeout while fetching realtime energy from {0}: {1}'.format(energy_module.number, ex))
            except Exception as ex:
                logger.exception('Got exception while fetching realtime energy from {0}: {1}'.format(energy_module.number, ex))
        return output

    def get_modules_information(self):
        # type: () -> List[ModuleDTO]
        if not self._enabled:
            return []

        information = []
        module_type_map = {EnergyEnums.Version.ENERGY_MODULE: ModuleDTO.ModuleType.ENERGY,
                           EnergyEnums.Version.POWER_MODULE: ModuleDTO.ModuleType.POWER,
                           EnergyEnums.Version.P1_CONCENTRATOR: ModuleDTO.ModuleType.P1_CONCENTRATOR}
        energy_modules = EnergyModule.select(EnergyModule, Module) \
                                     .join_from(EnergyModule, Module)  # type: List[EnergyModule]
        for energy_module in energy_modules:
            helper = self._get_helper(version=energy_module.version)
            try:
                try:
                    online, firmware_version = helper.get_information(energy_module=energy_module)
                except NotImplementedError:
                    # TODO: Remove once the P1C part is implemented
                    online, firmware_version = False, None
                information.append(ModuleDTO(source=ModuleDTO.Source.GATEWAY,
                                             address=energy_module.module.address,
                                             module_type=module_type_map.get(energy_module.version),
                                             hardware_type=ModuleDTO.HardwareType.PHYSICAL,
                                             firmware_version=firmware_version,
                                             order=energy_module.number,
                                             online=online))
            except Exception as ex:
                logger.exception('Got exception while fetching module information from {0}: {1}'.format(energy_module.number, ex))
        return information

    def load_modules(self):  # type: () -> List[EnergyModuleDTO]
        if not self._enabled:
            return []

        energy_modules = EnergyModule.select(EnergyModule, Module) \
                                     .join_from(EnergyModule, Module)  # type: List[EnergyModule]
        energy_cts = EnergyCT.select()
        merged_energy_modules = prefetch(energy_modules, energy_cts)

        return [EnergyModuleMapper.orm_to_dto(energy_module)
                for energy_module in merged_energy_modules]

    def save_modules(self, energy_module_dtos):  # type: (List[EnergyModuleDTO]) -> None
        if not self._enabled:
            return

        energy_modules = dict((energy_module.number, energy_module)
                              for energy_module in EnergyModule.select(EnergyModule, Module, EnergyCT)
                                                               .join_from(EnergyModule, Module)
                                                               .join_from(EnergyModule, EnergyCT))  # type: Dict[int, EnergyModule]
        for energy_module_dto in energy_module_dtos:
            energy_module = energy_modules.get(energy_module_dto.id)
            if energy_module is None:
                continue

            EnergyModuleMapper.dto_to_orm(energy_module_dto=energy_module_dto,
                                          energy_module_orm=energy_module)

            helper = self._get_helper(energy_module.version)
            helper.configure_cts(energy_module=energy_module)

            for ct in energy_module.cts:
                ct.save()
            energy_module.save()

    def get_realtime_p1(self):  # type: () -> List[Dict[str, Any]]
        if not self._enabled:
            return []

        # TODO: Use DTO
        realtime = []
        energy_modules = EnergyModule.select(EnergyModule, Module) \
                                     .join_from(EnergyModule, Module) \
                                     .where(EnergyModule.version == EnergyEnums.Version.P1_CONCENTRATOR)  # type: List[EnergyModule]
        for energy_module in energy_modules:
            try:
                realtime += self._get_helper(energy_module.version).get_realtime_p1(energy_module)
            except Exception as ex:
                logger.exception('Got exception while fetching realtime P1C information from {0}: {1}'.format(energy_module.number, ex))
        return realtime

    def start_address_mode(self):
        if not self._enabled:
            return
        self._energy_communicator.start_address_mode()

    def stop_address_mode(self):
        if not self._enabled:
            return
        self._energy_communicator.stop_address_mode()

    def in_address_mode(self):
        if not self._enabled:
            return False
        return self._energy_communicator.in_address_mode()

    def calibrate_module_voltage(self, module_id, voltage):
        if not self._enabled:
            return

        energy_module = EnergyModule.select().where(EnergyModule.number == module_id).first()
        self._get_helper(energy_module.version).set_module_voltage(energy_module, voltage)

    def get_energy_time(self, module_id, input_id=None):
        # type: (int, Optional[int]) -> Dict[str, Dict[str, Any]]
        if not self._enabled:
            return {}

        # TODO: Use DTO
        energy_module = EnergyModule.select().where(EnergyModule.number == module_id).first()
        return self._get_helper(energy_module.version).get_energy_time(energy_module, input_id=input_id)

    def get_energy_frequency(self, module_id, input_id=None):
        if not self._enabled:
            return {}

        # TODO: Use DTO
        energy_module = EnergyModule.select().where(EnergyModule.number == module_id).first()
        return self._get_helper(energy_module.version).get_energy_frequency(energy_module, input_id=input_id)

    def do_raw_energy_command(self, address, mode, command, data):
        if not self._enabled:
            return []
        return self._energy_communicator.do_command(address, EnergyAPI.raw_command(mode, command, len(data)), *data)
