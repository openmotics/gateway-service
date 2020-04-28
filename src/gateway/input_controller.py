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
from ioc import Injectable, Inject, INJECTED, Singleton
from gateway.dto import InputDTO
from gateway.models import Input, Room
from gateway.hal.master_controller import MasterController

if False:  # MYPY
    from typing import List, Tuple

logger = logging.getLogger("openmotics")


@Injectable.named('input_controller')
@Singleton
class InputController(object):

    @Inject
    def __init__(self, master_controller=INJECTED):
        self._master_controller = master_controller  # type: MasterController

    def load_input(self, input_id):  # type: (int) -> InputDTO
        input_ = Input.get(number=input_id)  # type: Input
        input_dto = self._master_controller.load_input(input_id=input_.number)
        input_dto.room = input_.room.number if input_.room is not None else None
        return input_dto

    def load_inputs(self):  # type: () -> List[InputDTO]
        inputs_dtos = []
        for input_ in Input.select():
            input_dto = self._master_controller.load_input(input_id=input_.number)
            input_dto.room = input_.room.number if input_.room is not None else None
            inputs_dtos.append(input_dto)
        return inputs_dtos

    def save_inputs(self, inputs):  # type: (List[Tuple[InputDTO, List[str]]]) -> None
        inputs_to_save = []
        for input_dto, fields in inputs:
            input_ = Input.get_or_none(number=input_dto.id)  # type: Input
            if input_ is None:
                continue
            if 'room' in fields:
                if input_dto.room is None:
                    input_.room = None
                elif 0 <= input_dto.room <= 100:
                    input_.room, _ = Room.get_or_create(number=input_dto.room)
                input_.save()
            inputs_to_save.append((input_dto, fields))
        self._master_controller.save_inputs(inputs_to_save)
