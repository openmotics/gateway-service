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
Output BLL
"""
from __future__ import absolute_import

import copy
import logging
import time
from threading import Lock
from peewee import JOIN

from gateway.base_controller import BaseController, SyncStructure
from gateway.daemon_thread import DaemonThread, DaemonThreadWait
from gateway.dto import OutputDTO, OutputStatusDTO, GlobalFeedbackDTO
from gateway.events import GatewayEvent
from gateway.hal.master_controller import CommunicationFailure
from gateway.hal.master_event import MasterEvent
from gateway.models import Output, Room, Floor
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Injectable, Singleton
from serial_utils import CommunicationTimedOutException
from toolbox import Toolbox

if False:  # MYPY
    from typing import Dict, List, Optional, Tuple, Literal
    from gateway.hal.master_controller import MasterController

logger = logging.getLogger('openmotics')


@Injectable.named('output_controller')
@Singleton
class OutputController(BaseController):

    SYNC_STRUCTURES = [SyncStructure(Output, 'output')]

    @Inject
    def __init__(self, master_controller=INJECTED):
        # type: (MasterController) -> None
        super(OutputController, self).__init__(master_controller)
        self._cache = OutputStateCache()
        self._sync_state_thread = None  # type: Optional[DaemonThread]

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.OUTPUT, self._handle_master_event)

    def start(self):
        # type: () -> None
        super(OutputController, self).start()
        self._sync_state_thread = DaemonThread(name='outputsyncstate',
                                               target=self._sync_state,
                                               interval=600, delay=10)
        self._sync_state_thread.start()

    def stop(self):
        # type: () -> None
        super(OutputController, self).stop()
        if self._sync_state_thread:
            self._sync_state_thread.stop()
            self._sync_state_thread = None

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        super(OutputController, self)._handle_master_event(master_event)
        if master_event.type == MasterEvent.Types.OUTPUT_STATUS:
            self._handle_output_status(master_event.data['state'])
        if master_event.type == MasterEvent.Types.EXECUTE_GATEWAY_API:
            if master_event.data['type'] == MasterEvent.APITypes.SET_LIGHTS:
                action = master_event.data['data']['action']  # type: Literal['ON', 'OFF', 'TOGGLE']
                floor_id = master_event.data['data']['floor_id']  # type: Optional[int]
                self.set_all_lights(action=action, floor_id=floor_id)

    def _handle_output_status(self, state_dto):
        # type: (OutputStatusDTO) -> None
        changed, output_dto = self._cache.handle_change(state_dto)
        if changed and output_dto is not None:
            self._publish_output_change(output_dto)

    def _sync_state(self):
        try:
            self.load_outputs()
            for state_dto in self._master_controller.load_output_status():
                _, output_dto = self._cache.handle_change(state_dto)
                if output_dto is not None:
                    # Always send events on the background sync
                    self._publish_output_change(output_dto)
        except CommunicationTimedOutException:
            logger.error('Got communication timeout during synchronization, waiting 10 seconds.')
            raise DaemonThreadWait
        except CommunicationFailure:
            # This is an expected situation
            raise DaemonThreadWait

    def _publish_output_change(self, output_dto):
        # type: (OutputDTO) -> None
        event_status = {'on': output_dto.state.status, 'locked': output_dto.state.locked}
        if output_dto.module_type in ['d', 'D']:
            event_status['value'] = output_dto.state.dimmer
        event_data = {'id': output_dto.id,
                      'status': event_status,
                      'location': {'room_id': Toolbox.denonify(output_dto.room, 255)}}
        gateway_event = GatewayEvent(GatewayEvent.Types.OUTPUT_CHANGE, event_data)
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def get_output_status(self, output_id):
        # type: (int) -> OutputStatusDTO
        # TODO also support plugins
        output_state_dto = self._cache.get_state().get(output_id)
        if output_state_dto is None:
            raise ValueError('Output with id {} does not exist'.format(output_id))
        return output_state_dto

    def get_output_statuses(self):
        # type: () -> List[OutputStatusDTO]
        # TODO also support plugins
        return list(self._cache.get_state().values())

    def load_output(self, output_id):  # type: (int) -> OutputDTO
        output = Output.select(Room) \
                       .join_from(Output, Room, join_type=JOIN.LEFT_OUTER) \
                       .where(Output.number == output_id) \
                       .get()  # type: Output  # TODO: Load dict
        output_dto = self._master_controller.load_output(output_id=output_id)
        output_dto.room = output.room.number if output.room is not None else None
        return output_dto

    def load_outputs(self):  # type: () -> List[OutputDTO]
        output_dtos = []
        for output in list(Output.select(Output, Room)
                                 .join_from(Output, Room, join_type=JOIN.LEFT_OUTER)):  # TODO: Load dicts
            output_dto = self._master_controller.load_output(output_id=output.number)
            output_dto.room = output.room.number if output.room is not None else None
            output_dtos.append(output_dto)
        self._cache.update_outputs(output_dtos)
        return output_dtos

    def save_outputs(self, outputs):  # type: (List[OutputDTO]) -> None
        outputs_to_save = []
        for output_dto in outputs:
            output = Output.get_or_none(number=output_dto.id)  # type: Output
            if output is None:
                logger.info('Ignored saving non-existing Output {0}'.format(output_dto.id))
            if 'room' in output_dto.loaded_fields:
                if output_dto.room is None:
                    output.room = None
                elif 0 <= output_dto.room <= 100:
                    output.room, _ = Room.get_or_create(number=output_dto.room)
                output.save()
            outputs_to_save.append(output_dto)
        self._master_controller.save_outputs(outputs_to_save)

    def set_all_lights(self, action, floor_id=None):  # type: (Literal['ON', 'OFF', 'TOGGLE'], Optional[int]) -> None
        # TODO: Also include other sources (e.g. plugins) once implemented
        if floor_id is None:
            self._master_controller.set_all_lights(action=action)
            return

        # TODO: Filter on output type "light" once available
        query = Output.select(Output.number) \
                      .join_from(Output, Room, join_type=JOIN.INNER) \
                      .join_from(Room, Floor, join_type=JOIN.INNER) \
                      .where(Floor.number == floor_id)
        output_ids = [output['number'] for output in query.dicts()]

        # It is unknown whether `floor` is known to the Master implementation. So pass both the floor_id
        # and the list of Output ids to the MasterController
        self._master_controller.set_all_lights(action=action,
                                               floor_id=floor_id,
                                               output_ids=output_ids)

    def set_output_status(self, output_id, is_on, dimmer=None, timer=None):
        # type: (int, bool, Optional[int], Optional[int]) -> None
        self._master_controller.set_output(output_id=output_id, state=is_on, dimmer=dimmer, timer=timer)

    def get_last_outputs(self):  # type: () -> List[int]
        """
        Get the X last changed outputs during the last Y seconds.
        """
        return self._cache.get_recent_outputs()

    # Global (led) feedback

    def load_global_feedback(self, global_feedback_id):  # type: (int) -> GlobalFeedbackDTO
        return self._master_controller.load_global_feedback(global_feedback_id=global_feedback_id)

    def load_global_feedbacks(self):  # type: () -> List[GlobalFeedbackDTO]
        return self._master_controller.load_global_feedbacks()

    def save_global_feedbacks(self, global_feedbacks):  # type: (List[GlobalFeedbackDTO]) -> None
        self._master_controller.save_global_feedbacks(global_feedbacks)


class OutputStateCache(object):
    def __init__(self):
        self._cache = {}  # type: Dict[int,OutputDTO]
        self._lock = Lock()
        self._loaded = False

    def get_state(self):
        # type: () -> Dict[int,OutputStatusDTO]
        return {x.id: x.state for x in self._cache.values()}

    def update_outputs(self, output_dtos):
        # type: (List[OutputDTO]) -> None
        with self._lock:
            new_state = {}
            for output_dto in output_dtos:
                output_dto = copy.copy(output_dto)
                if output_dto.id in self._cache:
                    output_dto.state = self._cache[output_dto.id].state
                else:
                    output_dto.state = OutputStatusDTO(output_dto.id)
                new_state[output_dto.id] = output_dto
            self._cache = new_state
            self._loaded = True

    def get_recent_outputs(self, threshold=10):
        # type: (int) -> List[int]
        sorted_outputs = sorted(list(self._cache.values()), key=lambda x: x.state.updated_at if x.state else 0.0)
        return [y.id for y in sorted_outputs if y.state and y.state.updated_at > time.time() - threshold]

    def handle_change(self, state_dto):
        # type: (OutputStatusDTO) -> Tuple[bool, Optional[OutputDTO]]
        """
        Cache output state and detect changes.
        The classic master will send multiple status events when an output changes,
        this deduplicates actual changes based on the cached state.
        """
        with self._lock:
            if not self._loaded:
                return False, None
            output_id = state_dto.id
            if output_id not in self._cache:
                logger.warning('Received change for unknown output {0}: {1}'.format(output_id, state_dto))
                return False, None
            changed = False
            current_state = self._cache[output_id].state
            if current_state is None:
                self._cache[output_id].state = state_dto
                changed = True
            else:
                if 'status' in state_dto.loaded_fields:
                    status = state_dto.status
                    changed |= current_state.status != status
                    current_state.status = status
                if 'ctimer' in state_dto.loaded_fields:
                    current_state.ctimer = state_dto.ctimer
                if 'dimmer' in state_dto.loaded_fields:
                    dimmer = state_dto.dimmer
                    changed |= current_state.dimmer != dimmer
                    current_state.dimmer = dimmer
                if 'locked' in state_dto.loaded_fields:
                    locked = state_dto.locked
                    changed |= current_state.locked != locked
                    current_state.locked = locked
                if changed:
                    current_state.updated_at = state_dto.updated_at
            return changed, self._cache[output_id]
