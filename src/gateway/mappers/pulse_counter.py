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
PulseCounter Mapper
"""
from __future__ import absolute_import
from gateway.dto import PulseCounterDTO
from gateway.models import PulseCounter, Room


class PulseCounterMapper(object):
    def __init__(self, db):
        self._db = db

    def orm_to_dto(self, orm_object):  # type: (PulseCounter) -> PulseCounterDTO
        _ = self
        return PulseCounterDTO(id=orm_object.number,
                               name=orm_object.name,
                               persistent=orm_object.persistent,
                               in_use=orm_object.in_use,
                               room=None if orm_object.room is None else orm_object.room.number)

    def dto_to_orm(self, pulse_counter_dto):  # type: (PulseCounterDTO) -> PulseCounter
        pulse_counter = self._db.query(PulseCounter).where(PulseCounter.number == pulse_counter_dto.id).one_or_none()
        if pulse_counter is None:
            pulse_counter = PulseCounter(number=pulse_counter_dto.id,
                                         name='',
                                         source='gateway',
                                         in_use=True,
                                         persistent=False)
            self._db.add(pulse_counter)
        if 'name' in pulse_counter_dto.loaded_fields:
            pulse_counter.name = pulse_counter_dto.name
        if 'persistent' in pulse_counter_dto.loaded_fields:
            pulse_counter.persistent = pulse_counter_dto.persistent
        if 'in_use' in pulse_counter_dto.loaded_fields:
            pulse_counter.in_use = pulse_counter_dto.in_use
        if 'room' in pulse_counter_dto.loaded_fields:
            if pulse_counter_dto.room is None:
                pulse_counter.room = None
            elif 0 <= pulse_counter_dto.room <= 100:
                pulse_counter.room = self._db.query(Room).where(Room.number == pulse_counter_dto.room).one()
        return pulse_counter
