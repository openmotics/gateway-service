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
import logging
from peewee import JOIN
from ioc import Injectable, Inject, INJECTED, Singleton
from gateway.dto import InputDTO
from gateway.events import GatewayEvent
from gateway.models import Input, Room
from gateway.hal.master_event import MasterEvent
from gateway.base_controller import BaseController, SyncStructure
from gateway.pubsub import PubSub

if False:  # MYPY
    from typing import Any, Dict, List

logger = logging.getLogger('openmotics')


@Injectable.named('input_controller')
@Singleton
class InputController(BaseController):
    SYNC_STRUCTURES = [SyncStructure(Input, 'input', skip=lambda i: i.module_type not in ['i', 'I'])]

    @Inject
    def __init__(self, master_controller=INJECTED):
        super(InputController, self).__init__(master_controller)
        self._pubsub.subscribe_master_events(PubSub.MasterTopics.INPUT, self._handle_master_event)

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        if master_event.type == MasterEvent.Types.INPUT_CHANGE:
            gateway_event = GatewayEvent(event_type=GatewayEvent.Types.INPUT_CHANGE,
                                         data=master_event.data)
            self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def load_input(self, input_id):  # type: (int) -> InputDTO
        input_ = Input.select(Input, Room) \
                      .join_from(Input, Room, join_type=JOIN.LEFT_OUTER) \
                      .where(Input.number == input_id) \
                      .get()  # type: Input  # TODO: Load dict
        input_dto = self._master_controller.load_input(input_id=input_id)
        input_dto.room = input_.room.number if input_.room is not None else None
        input_dto.event_enabled = input_.event_enabled
        return input_dto

    def load_inputs(self):  # type: () -> List[InputDTO]
        inputs_dtos = []
        for input_ in list(Input.select(Input, Room)
                                .join_from(Input, Room, join_type=JOIN.LEFT_OUTER)):  # TODO: Load dicts
            input_dto = self._master_controller.load_input(input_id=input_.number)
            input_dto.room = input_.room.number if input_.room is not None else None
            input_dto.event_enabled = input_.event_enabled
            inputs_dtos.append(input_dto)
        return inputs_dtos

    def save_inputs(self, inputs):  # type: (List[InputDTO]) -> None
        inputs_to_save = []
        for input_dto in inputs:
            input_ = Input.get_or_none(number=input_dto.id)  # type: Input
            if input_ is None:
                logger.info('Ignored saving non-existing Input {0}'.format(input_dto.id))
            if 'event_enabled' in input_dto.loaded_fields:
                input_.event_enabled = input_dto.event_enabled
                input_.save()
            if 'room' in input_dto.loaded_fields:
                if input_dto.room is None:
                    input_.room = None
                elif 0 <= input_dto.room <= 100:
                    # TODO: Validation should happen on API layer
                    input_.room, _ = Room.get_or_create(number=input_dto.room)
                input_.save()
            inputs_to_save.append(input_dto)
        self._master_controller.save_inputs(inputs_to_save)

    def get_input_status(self):  # type: () -> List[Dict[str, Any]]
        """
        Get a list containing the status of the Inputs.
        :returns: A list is a dicts containing the following keys: id, status.
        """
        # TODO: Convert to some StatusDTO similar to the OutputStatus
        return [{'id': input_port['id'], 'status': input_port['status']}
                for input_port in self._master_controller.get_inputs_with_status()]

    def set_input_status(self, input_id, status):
        self._master_controller.set_input(input_id, status)

    def get_last_inputs(self):  # type: () -> List[int]
        """
        Get the X last pressed inputs during the last Y seconds.
        """
        return self._master_controller.get_recent_inputs()

    def get_input_module_type(self, input_module_id):
        """ Gets the module type for a given Input Module ID """
        return self._master_controller.get_input_module_type(input_module_id)

    @staticmethod
    def load_inputs_event_enabled():
        return {input_['number']: input_['event_enabled']
                for input_ in Input.select().dicts()}
