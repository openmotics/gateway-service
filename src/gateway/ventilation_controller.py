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
from gateway.mappers import VentilationMapper
from gateway.models import Ventilation
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@Injectable.named('ventilation_controller')
@Singleton
class VentilationController(object):

    @Inject
    def __init__(self, message_client=INJECTED):
        # type: (MessageClient) -> None
        self._levels = {}  # type: Dict[int,int]

    def start(self):
        # type: () -> None
        pass

    def stop(self):
        # type: () -> None
        pass

    def load_ventilations(self):
        # type: () -> List[VentilationDTO]
        ventilations = []
        for ventilation in Ventilation.select():
            ventilations.append(VentilationMapper.orm_to_dto(ventilation))
        return ventilations

    def load_ventilation(self, ventilation_id):
        # type: (int) -> VentilationDTO
        ventilation = Ventilation.get(id=ventilation_id)
        return VentilationMapper.orm_to_dto(ventilation)

    def save_ventilation(self, ventilation_dto, fields):
        # type: (VentilationDTO, List[str]) -> VentilationDTO
        ventilation = VentilationMapper.dto_to_orm(ventilation_dto, fields)
        ventilation.save()
        return VentilationMapper.orm_to_dto(ventilation)

    def get_level(self, ventilation_id):
        # type: (int) -> Optional[int]
        if Ventilation.select(id == ventilation_id).count() == 1:
            return self._levels[ventilation_id]
        else:
            return None

    def set_level(self, ventilation_id, level, timer=None):
        # type: (int, int, Optional[float]) -> Optional[int]
        ventilation = Ventilation.get(id=ventilation_id)
        if level < 0 or level > ventilation.amount_of_levels:
            values = list(range(ventilation.amount_of_levels + 1))
            raise ValueError('level {0} not in {1}'.format(level, values))
        current_level = self._levels.get(ventilation_id)
        if level != current_level:
            self._levels[ventilation_id] = level
            # TODO broadcast gateway event
        return level
