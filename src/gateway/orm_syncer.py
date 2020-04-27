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
This module contains ORM sync logic
"""

from __future__ import absolute_import
import logging

from ioc import Inject, INJECTED
from gateway.hal.master_event import MasterEvent
from gateway.hal.master_controller import MasterController
from gateway.models import Output, Room

logger = logging.getLogger("openmotics")


class ORMSyncer(object):

    @staticmethod
    def handle_master_event(master_event):  # type: (MasterEvent) -> None
        if master_event.type == MasterEvent.Types.EEPROM_CHANGE:
            ORMSyncer.sync()

    @staticmethod
    @Inject
    def sync(master_controller=INJECTED):  # type: (MasterController) -> None
        logger.info('Sync ORM with Master/Core reality')
        output_ids = []
        for output_dto in master_controller.load_outputs():
            output_id = output_dto.id
            output_ids.append(output_id)
            output, output_created = Output.get_or_create(number=output_id)  # type: Output, bool
            room_id = output_dto.room
            if room_id is None:
                output.room = None
            else:
                room, room_created = Room.get_or_create(number=room_id)  # type: Room, bool
                output.room = room
            output.save()
        Output.delete().where(Output.number.not_in(output_ids)).execute()

        for room in Room.select():
            in_use = room.outputs.count() > 0
            if not in_use:
                room.delete()
