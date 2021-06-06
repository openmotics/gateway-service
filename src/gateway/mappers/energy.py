# Copyright (C) 2021 OpenMotics BV
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
Energy Mappers
"""
from __future__ import absolute_import
from gateway.dto import EnergyModuleDTO
from gateway.models import EnergyModule
from gateway.enums import EnergyEnums


class EnergyModuleMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EnergyModule) -> EnergyModuleDTO
        kwargs = {}
        for ct in sorted(orm_object.cts, key=lambda c: c.number):
            kwargs.update({'input{0}'.format(ct.number): ct.name,
                           'times{0}'.format(ct.number): ct.times,
                           'sensor{0}'.format(ct.number): ct.sensor_type,
                           'inverted{0}'.format(ct.number): ct.inverted})
        return EnergyModuleDTO(id=orm_object.number,
                               name=orm_object.name,
                               version=orm_object.version,
                               address=int(orm_object.module.address),
                               **kwargs)

    @staticmethod
    def dto_to_orm(energy_module_dto, energy_module_orm):  # type: (EnergyModuleDTO, EnergyModule) -> None
        """ Maps a DTO to a referenced ORM instance """
        if energy_module_dto.id != energy_module_orm.number:
            raise ValueError('DTO and ORM objects do not match')

        for field in ['name']:  # Not possible to update (hardware)version or address
            if field in energy_module_dto.loaded_fields:
                setattr(energy_module_orm, field, getattr(energy_module_dto, field))

        for port_id in range(EnergyEnums.NUMBER_OF_PORTS[energy_module_orm.version]):
            ct_orm = [ct for ct in energy_module_orm.cts if ct.number == port_id][0]
            field = 'input{0}'.format(port_id)
            if field in energy_module_dto.loaded_fields:
                ct_orm.name = getattr(energy_module_dto, field)
            field = 'times{0}'.format(port_id)
            if field in energy_module_dto.loaded_fields:
                ct_orm.times = getattr(energy_module_dto, field)
            field = 'sensor{0}'.format(port_id)
            if field in energy_module_dto.loaded_fields:
                ct_orm.sensor_type = getattr(energy_module_dto, field)
            field = 'inverted{0}'.format(port_id)
            if field in energy_module_dto.loaded_fields:
                ct_orm.inverted = getattr(energy_module_dto, field)
