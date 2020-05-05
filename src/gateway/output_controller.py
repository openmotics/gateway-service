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
from ioc import Injectable, Inject, INJECTED, Singleton
from gateway.base_controller import BaseController, SyncStructure
from gateway.dto import OutputDTO
from gateway.models import Output, Room

if False:  # MYPY
    from typing import List, Tuple

logger = logging.getLogger("openmotics")


@Injectable.named('output_controller')
@Singleton
class OutputController(BaseController):

    SYNC_STRUCTURES = [SyncStructure(Output, 'output')]

    @Inject
    def __init__(self, master_controller=INJECTED):
        super(OutputController, self).__init__(master_controller)

    def load_output(self, output_id):  # type: (int) -> OutputDTO
        output = Output.get(number=output_id)  # type: Output
        output_dto = self._master_controller.load_output(output_id=output.number)
        output_dto.room = output.room.number if output.room is not None else None
        return output_dto

    def load_outputs(self):  # type: () -> List[OutputDTO]
        outputs_dtos = []
        for output in Output.select():
            output_dto = self._master_controller.load_output(output_id=output.number)
            output_dto.room = output.room.number if output.room is not None else None
            outputs_dtos.append(output_dto)
        return outputs_dtos

    def save_outputs(self, outputs):  # type: (List[Tuple[OutputDTO, List[str]]]) -> None
        outputs_to_save = []
        for output_dto, fields in outputs:
            output = Output.get_or_none(number=output_dto.id)  # type: Output
            if output is None:
                continue
            if 'room' in fields:
                if output_dto.room is None:
                    output.room = None
                elif 0 <= output_dto.room <= 100:
                    output.room, _ = Room.get_or_create(number=output_dto.room)
                output.save()
            outputs_to_save.append((output_dto, fields))
        self._master_controller.save_outputs(outputs_to_save)
