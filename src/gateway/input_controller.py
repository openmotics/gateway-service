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
Input BLL
"""
from __future__ import absolute_import

import copy
import logging
import time
from threading import Lock
from gateway.daemon_thread import DaemonThread, DaemonThreadWait
from gateway.dto.input import InputStatusDTO
from ioc import Injectable, Inject, INJECTED, Singleton
from gateway.dto import InputDTO
from gateway.events import GatewayEvent
from gateway.models import Input, Room, Database
from gateway.hal.master_event import MasterEvent
from gateway.exceptions import CommunicationFailure
from gateway.base_controller import BaseController, SyncStructure
from gateway.pubsub import PubSub
from serial_utils import CommunicationTimedOutException
from toolbox import Toolbox

if False:  # MYPY
    from typing import Dict, List, Optional, Tuple, Any
    from gateway.hal.master_controller import MasterController

logger = logging.getLogger(__name__)


@Injectable.named('input_controller')
@Singleton
class InputController(BaseController):
    SYNC_STRUCTURES = [SyncStructure(Input, 'input', skip=lambda i: i.module_type not in ['i', 'I'])]

    @Inject
    def __init__(self, master_controller=INJECTED):
        # type: (MasterController) -> None
        super(InputController, self).__init__(master_controller)
        self._cache = InputStateCache()
        self._pubsub.subscribe_master_events(PubSub.MasterTopics.INPUT, self._handle_master_event)

    def sync_state(self):
        try:
            logger.debug('Publishing latest input status')
            for state_dto in self._master_controller.load_input_status():
                _, input_dto = self._cache.handle_change(state_dto)
                if input_dto is not None:
                    # Always send events on the background sync
                    self._publish_input_change(input_dto)
        except CommunicationTimedOutException:
            logger.error('Got communication timeout during synchronization, waiting 10 seconds.')
            raise DaemonThreadWait
        except CommunicationFailure:
            # This is an expected situation
            raise DaemonThreadWait

    def _handle_input_status(self, state_dto):
        # type: (InputStatusDTO) -> None
        changed, input_dto = self._cache.handle_change(state_dto)
        if changed and input_dto is not None:
            self._publish_input_change(input_dto)

    def _publish_config(self):
        # type: () -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'input'})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def _publish_input_change(self, input_dto):
        # type: (InputDTO) -> None
        event_data = {'id': input_dto.id,
                      'status': input_dto.state.status if input_dto.state is not None else None,
                      'location': {'room_id': Toolbox.denonify(input_dto.room, 255)}}
        gateway_event = GatewayEvent(event_type=GatewayEvent.Types.INPUT_CHANGE, data=event_data)
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        super(InputController, self)._handle_master_event(master_event)
        if master_event.type == MasterEvent.Types.INPUT_CHANGE:
            self._handle_input_status(master_event.data['state'])

    @staticmethod
    def _input_orm_to_dto(input_orm, input_dto):
        input_dto.name = input_orm.name
        input_dto.room = input_orm.room.number if input_orm.room is not None else None
        input_dto.event_enabled = input_orm.event_enabled
        input_dto.in_use = input_orm.in_use

    @staticmethod
    def _input_dto_to_orm(input_dto, input_orm, db):
        for field in ['event_enabled', 'name', 'in_use']:
            if field in input_dto.loaded_fields:
                setattr(input_orm, field, getattr(input_dto, field))
        if 'room' in input_dto.loaded_fields:
            if input_dto.room is None:
                input_orm.room = None
            elif 0 <= input_dto.room <= 100:
                # TODO: Validation should happen on API layer
                input_orm.room = db.query(Room).where(Room.number == input_dto.room).one()

    def load_input(self, input_id):  # type: (int) -> InputDTO
        with Database.get_session() as db:
            input_orm = db.query(Input)\
                .join(Input.room, isouter=True) \
                .where(Input.number == input_id) \
                .one()  # type: Input
            input_dto = self._master_controller.load_input(input_id=input_id)
            InputController._input_orm_to_dto(input_orm=input_orm, input_dto=input_dto)
        return input_dto

    def load_inputs(self):  # type: () -> List[InputDTO]
        inputs_dtos = []
        with Database.get_session() as db:
            inputs = db.query(Input).join(Input.room, isouter=True).all()
            for input_orm in inputs:
                try:
                    input_dto = self._master_controller.load_input(input_id=input_orm.number)
                except TypeError as ex:
                    logger.error('Could not load input {0}: {1}'.format(input_orm.number, ex))
                    continue
                InputController._input_orm_to_dto(input_orm=input_orm, input_dto=input_dto)
                inputs_dtos.append(input_dto)
        self._cache.update_inputs(inputs_dtos)
        return inputs_dtos

    def save_inputs(self, inputs):  # type: (List[InputDTO]) -> None
        inputs_to_save = []
        with Database.get_session() as db:
            for input_dto in inputs:
                input_orm = db.query(Input) \
                    .where(Input.number == input_dto.id) \
                    .join(Input.room, isouter=True) \
                    .one_or_none()  # type: Input
                if input_orm is None:
                    logger.info('Ignored saving non-existing Input {0}'.format(input_dto.id))
                else:
                    InputController._input_dto_to_orm(input_dto=input_dto, input_orm=input_orm, db=db)
                inputs_to_save.append(input_dto)
            publish = bool(db.dirty)
            db.commit()
        self._master_controller.save_inputs(inputs_to_save)
        if publish:
            self._publish_config()

    def get_input_status(self, input_id):
        # type: (int) -> Optional[InputStatusDTO]
        input_state_dto = self._cache.get_input_status().get(input_id)
        if input_state_dto is None:
            raise ValueError('Input with id {} does not exist'.format(input_id))
        return input_state_dto

    def get_input_statuses(self):
        # type: () -> List[Optional[InputStatusDTO]]
        return list(self._cache.get_input_status().values())

    def set_input_status(self, status_dto):
        # type: (InputStatusDTO) -> InputStatusDTO
        self._cache.handle_change(status_dto)
        # TODO: only update cache if input is not on master (e.g. if status_dto.id < 200)
        self._master_controller.set_input(status_dto.id, status_dto.status)
        return status_dto

    def get_last_inputs(self):  # type: () -> List[int]
        """
        Get the X last changed inputs during the last Y seconds.
        """
        return self._cache.get_recent_inputs()

    def get_input_module_type(self, input_module_id):
        """ Gets the module type for a given Input Module ID """
        return self._master_controller.get_input_module_type(input_module_id)

    @staticmethod
    def load_inputs_event_enabled():
        with Database.get_session() as db:
            return {input_.number: input_.event_enabled for input_ in db.query(Input).all()}


class InputStateCache(object):
    def __init__(self):
        self._cache = {}  # type: Dict[int,InputDTO]
        self._lock = Lock()

    def get_input_status(self):
        # type: () -> Dict[int,Optional[InputStatusDTO]]
        return {x.id: x.state for x in self._cache.values()}

    def set_input_status(self, input_id, status):
        # type: (int, bool) -> bool
        changed, _ = self.handle_change(InputStatusDTO(input_id, status=status))
        return changed

    def update_inputs(self, input_dtos):
        # type: (List[InputDTO]) -> None
        with self._lock:
            new_state = {}
            for input_dto in input_dtos:
                input_dto = copy.copy(input_dto)
                if input_dto.id in self._cache:
                    input_dto.state = self._cache[input_dto.id].state
                else:
                    input_dto.state = InputStatusDTO(input_dto.id)
                new_state[input_dto.id] = input_dto
            self._cache = new_state

    def get_recent_inputs(self, threshold=10):
        # type: (int) -> List[int]
        sorted_inputs = sorted(list(self._cache.values()), key=lambda x: x.state.updated_at if x.state else 0.0)
        recent_changed_inputs = [y.id for y in sorted_inputs if y.state and y.state.updated_at > time.time() - threshold]
        return recent_changed_inputs[-5:]

    def handle_change(self, state_dto):
        # type: (InputStatusDTO) -> Tuple[bool, Optional[InputDTO]]
        """
        Cache input state and detect changes.
        The classic master will send multiple status events when an input changes,
        this deduplicates actual changes based on the cached state.
        """
        with self._lock:
            input_id = state_dto.id
            if input_id not in self._cache:
                logger.warning('Received change for unknown input {0}: {1}'.format(input_id, state_dto))
                self._cache[input_id] = InputDTO(input_id, state=state_dto)
                return False, None
            changed = False
            if 'status' in state_dto.loaded_fields and self._cache[input_id].state != state_dto:
                logger.debug('Change detected in input status')
                self._cache[input_id].state = state_dto
                changed = True
            else:
                logger.debug('No change detected in input status')
            return changed, self._cache[input_id]
