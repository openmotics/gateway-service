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

from bus.om_bus_client import MessageClient
from gateway.dto import VentilationDTO, VentilationSourceDTO
from gateway.dto.base import BaseDTO
from gateway.events import GatewayEvent
from gateway.mappers import VentilationMapper
from gateway.models import Plugin, Ventilation
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@Injectable.named('ventilation_controller')
@Singleton
class VentilationController(object):

    @Inject
    def __init__(self, message_client=INJECTED):
        # type: (MessageClient) -> None
        self._event_subscriptions = []  # type: List[Callable[[GatewayEvent],None]]
        self._status = {}  # type: Dict[int, StateDTO]

    def start(self):
        # type: () -> None
        pass

    def stop(self):
        # type: () -> None
        pass

    def subscribe_events(self, callback):
        # type: (Callable[[GatewayEvent],None]) -> None
        self._event_subscriptions.append(callback)

    def _publish_events(self, state_dto, plugin=None):
        # type: (StateDTO, Optional[Plugin]) -> None
        event_data = {'id': state_dto.ventilation.id,
                      'mode': state_dto.mode,
                      'level': state_dto.level,
                      'timer': state_dto.timer}
        if state_dto.ventilation.source.is_plugin:
            event_data.update({'source': VentilationSourceDTO.Type.PLUGIN,
                               'plugin': state_dto.ventilation.source.name})
        for callback in self._event_subscriptions:
            callback(GatewayEvent(GatewayEvent.Types.VENTILATION_CHANGE, event_data))

    def load_ventilations(self):
        # type: () -> List[VentilationDTO]
        return [VentilationMapper.orm_to_dto(ventilation)
                for ventilation in Ventilation.select()]

    def load_ventilation(self, ventilation_id):
        # type: (int) -> VentilationDTO
        ventilation = Ventilation.get(id=ventilation_id)
        return VentilationMapper.orm_to_dto(ventilation)

    def save_ventilation(self, ventilation_dto, fields):
        # type: (VentilationDTO, List[str]) -> VentilationDTO
        ventilation = VentilationMapper.dto_to_orm(ventilation_dto, fields)
        ventilation.save()
        return VentilationMapper.orm_to_dto(ventilation)

    def get_status(self):
        # type: () -> List[StateDTO]
        status = []
        for ventilation in Ventilation.select():
            state_dto = self._status.get(ventilation.id)
            if state_dto:
                status.append(state_dto)
        return status

    def set_mode_auto(self, ventilation_id):
        # type: (int) -> None
        ventilation_dto = self.load_ventilation(ventilation_id)
        state_dto = StateDTO(ventilation_dto, mode=StateDTO.Mode.AUTO)
        if state_dto != self._status.get(ventilation_id):
            self._status[ventilation_id] = state_dto
            self._publish_events(state_dto)

    def set_level(self, ventilation_id, level, timer=None):
        # type: (int, int, Optional[float]) -> None
        ventilation_dto = self.load_ventilation(ventilation_id)
        state_dto = StateDTO(ventilation_dto, mode=StateDTO.Mode.MANUAL, level=level, timer=timer)
        self._validate_state(state_dto)
        if state_dto != self._status.get(ventilation_id):
            self._status[ventilation_id] = state_dto
            self._publish_events(state_dto)

    def _validate_state(self, state_dto):
        # type: (StateDTO) -> None
        if state_dto.level:
            if state_dto.mode == StateDTO.Mode.AUTO:
                raise ValueError('ventilation mode {} does not support level'.format(state_dto.level))
            if state_dto.level < 0 or state_dto.level > state_dto.ventilation.amount_of_levels:
                values = list(range(state_dto.ventilation.amount_of_levels + 1))
                raise ValueError('ventilation level {0} not in {1}'.format(state_dto.level, values))


class StateDTO(BaseDTO):
    class Mode:
        AUTO = 'auto'
        MANUAL = 'manual'

    def __init__(self, ventilation, mode, level=None, timer=None):
        # type: (VentilationDTO, str, Optional[int], Optional[float]) -> None
        self.ventilation = ventilation
        self.mode = mode
        self.level = level
        self.timer = timer

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, StateDTO):
            return False
        if self.timer:
            return False
        return (self.ventilation == other.ventilation and
                self.mode == other.mode and
                self.level == other.level)
