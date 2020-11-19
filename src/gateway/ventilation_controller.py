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

import logging

from gateway.dto import VentilationDTO, VentilationStatusDTO
from gateway.events import GatewayEvent
from gateway.mappers import VentilationMapper
from gateway.models import Ventilation
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@Injectable.named('ventilation_controller')
@Singleton
class VentilationController(object):

    @Inject
    def __init__(self, pubsub=INJECTED):
        # type: (PubSub) -> None
        self._pubsub = pubsub
        self._status = {}  # type: Dict[int, VentilationStatusDTO]

    def start(self):
        # type: () -> None
        self._publish_config()

    def stop(self):
        # type: () -> None
        pass

    def _publish_config(self):
        # type: () -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'ventilation'})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def _publish_state(self, state_dto):
        # type: (VentilationStatusDTO) -> None
        event_data = {'id': state_dto.id,
                      'mode': state_dto.mode,
                      'level': state_dto.level,
                      'timer': state_dto.timer}
        gateway_event = GatewayEvent(GatewayEvent.Types.VENTILATION_CHANGE, event_data)
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def load_ventilations(self):
        # type: () -> List[VentilationDTO]
        return [VentilationMapper.orm_to_dto(ventilation)
                for ventilation in Ventilation.select()]

    def load_ventilation(self, ventilation_id):
        # type: (int) -> VentilationDTO
        ventilation = Ventilation.get(id=ventilation_id)
        return VentilationMapper.orm_to_dto(ventilation)

    def save_ventilation(self, ventilation_dto, fields):
        # type: (VentilationDTO, List[str]) -> None
        ventilation = VentilationMapper.dto_to_orm(ventilation_dto, fields)
        if ventilation.id is None:
            logger.info('Registered new ventilation unit %s', ventilation)
        changed = ventilation.save() > 0
        ventilation_dto.id = ventilation.id
        if changed:
            self._publish_config()

    def get_status(self):
        # type: () -> List[VentilationStatusDTO]
        status = []
        for ventilation in Ventilation.select():
            state_dto = self._status.get(ventilation.id)
            if state_dto:
                status.append(state_dto)
        return status

    def set_status(self, status_dto):
        # type: (VentilationStatusDTO) -> VentilationStatusDTO
        ventilation_dto = self.load_ventilation(status_dto.id)
        self._validate_state(ventilation_dto, status_dto)
        if status_dto != self._status.get(status_dto.id):
            self._publish_state(status_dto)
        self._status[status_dto.id] = status_dto
        return status_dto

    def set_mode_auto(self, ventilation_id):
        # type: (int) -> None
        _ = self.load_ventilation(ventilation_id)
        status_dto = VentilationStatusDTO(ventilation_id, mode=VentilationStatusDTO.Mode.AUTO)
        if status_dto != self._status.get(ventilation_id):
            self._status[ventilation_id] = status_dto
            self._publish_state(status_dto)

    def set_level(self, ventilation_id, level, timer=None):
        # type: (int, int, Optional[float]) -> None
        ventilation_dto = self.load_ventilation(ventilation_id)
        status_dto = VentilationStatusDTO(ventilation_id, mode=VentilationStatusDTO.Mode.MANUAL, level=level, timer=timer)
        self._validate_state(ventilation_dto, status_dto)
        if status_dto != self._status.get(ventilation_id):
            self._status[ventilation_id] = status_dto
            self._publish_state(status_dto)

    def _validate_state(self, ventilation_dto, status_dto):
        # type: (VentilationDTO, VentilationStatusDTO) -> None
        if status_dto.level:
            if status_dto.mode == VentilationStatusDTO.Mode.AUTO:
                raise ValueError('ventilation mode {} does not support level'.format(status_dto.level))
            if status_dto.level < 0 or status_dto.level > ventilation_dto.amount_of_levels:
                values = list(range(ventilation_dto.amount_of_levels + 1))
                raise ValueError('ventilation level {0} not in {1}'.format(status_dto.level, values))
