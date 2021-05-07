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
Base Controller
"""
from __future__ import absolute_import

import logging
import time

from gateway.daemon_thread import DaemonThread
from gateway.events import GatewayEvent
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from gateway.models import BaseModel
from gateway.dto.base import BaseDTO
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from typing import Any, Callable, List, Optional, Type, TypeVar
    from gateway.maintenance_controller import MaintenanceController

logger = logging.getLogger('openmotics')


class SyncStructure(object):
    def __init__(self, orm_model, name, skip=None):  # type: (Type[BaseModel], str, Optional[Callable[[Any], bool]]) -> None
        self.orm_model = orm_model  # type: Type[BaseModel]
        self.name = name  # type: str
        self.skip = skip  # type: Optional[Callable[[Any], bool]]


class BaseController(object):

    SYNC_STRUCTURES = None  # type: Optional[List[SyncStructure]]

    @Inject
    def __init__(self, master_controller, maintenance_controller=INJECTED, pubsub=INJECTED, sync_interval=900):
        # type: (MasterController, MaintenanceController, PubSub, Optional[float]) -> None
        self._master_controller = master_controller
        self._maintenance_controller = maintenance_controller
        self._pubsub = pubsub
        self._sync_orm_thread = None  # type: Optional[DaemonThread]
        self._sync_orm_interval = sync_interval
        self._sync_dirty = True  # Always sync after restart.
        self._sync_running = False

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.EEPROM, self._handle_master_event)
        self._pubsub.subscribe_master_events(PubSub.MasterTopics.MODULE, self._handle_master_event)

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        if master_event.type in [MasterEvent.Types.EEPROM_CHANGE,
                                 MasterEvent.Types.MODULE_DISCOVERY]:
            self._sync_dirty = True
            self.request_sync_orm()

    def start(self):
        self._sync_orm_thread = DaemonThread(name='{0}sync'.format(self.__class__.__name__.lower()[:10]),
                                             target=self._sync_orm,
                                             interval=self._sync_orm_interval,
                                             delay=300)
        self._sync_orm_thread.start()

    def stop(self):
        if self._sync_orm_thread is not None:
            self._sync_orm_thread.stop()

    def request_sync_orm(self):
        if self._sync_orm_thread is not None:
            self._sync_orm_thread.request_single_run()

    def run_sync_orm(self):
        self._sync_orm()

    def _sync_orm(self):
        # type: () -> bool
        if self.SYNC_STRUCTURES is None:
            return False

        if self._sync_running:
            for structure in self.SYNC_STRUCTURES:
                orm_model = structure.orm_model
                logger.info('ORM sync ({0}): Already running'.format(orm_model.__name__))
            return False
        self._sync_running = True

        try:
            for structure in self.SYNC_STRUCTURES:
                orm_model = structure.orm_model
                try:
                    start = time.time()
                    logger.info('ORM sync ({0})'.format(orm_model.__name__))
                    self._sync_orm_structure(structure)
                    duration = time.time() - start
                    logger.info('ORM sync ({0}): completed after {1:.1f}s'.format(orm_model.__name__, duration))
                except CommunicationTimedOutException as ex:
                    logger.error('ORM sync ({0}): Failed: {1}'.format(orm_model.__name__, ex))
                except Exception:
                    logger.exception('ORM sync ({0}): Failed'.format(orm_model.__name__))

                if self._sync_dirty:
                    type_name = orm_model.__name__.lower()
                    gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': type_name})
                    self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)
            self._sync_dirty = False
        finally:
            self._sync_running = False
        return True

    def _sync_orm_structure(self, structure):
        # type: (SyncStructure) -> None
        orm_model = structure.orm_model
        name = structure.name
        skip = structure.skip

        ids = []
        for dto in getattr(self._master_controller, 'load_{0}s'.format(name))():
            if skip is not None and skip(dto):
                continue
            id_ = dto.id
            ids.append(id_)
            if not orm_model.select().where(orm_model.number == id_).exists():
                orm_model.create(number=id_)
        orm_model.delete().where(orm_model.number.not_in(ids)).execute()
