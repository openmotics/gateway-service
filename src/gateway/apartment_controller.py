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
apartment controller manages the apartment objects that are known in the system
"""
import logging

from gateway.base_controller import BaseController, SyncStructure
from gateway.models import Apartment
from gateway.mappers import ApartmentMapper
from gateway.dto import ApartmentDTO
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MyPy
    from typing import List, Optional

logger = logging.getLogger('openmotics')


@Injectable.named('apartment_controller')
@Singleton
class ApartmentController(object):
    def __init__(self):
        pass

    def load_apartment(self, apartment_id):
        # type: (int) -> Optional[ApartmentDTO]
        _ = self
        apartment_orm = Apartment.select().where(Apartment.id == apartment_id).first()
        if apartment_orm is None:
            return None
        apartment_dto = ApartmentMapper.orm_to_dto(apartment_orm)
        return apartment_dto

    def load_apartments(self):
        # type: () -> List[ApartmentDTO]
        _ = self
        apartments = []
        for apartment_orm in Apartment.select():
            apartment_dto = ApartmentMapper.orm_to_dto(apartment_orm)
            apartments.append(apartment_dto)
        return apartments

    def get_apartment_count(self):
        # type: () -> int
        _ = self
        return Apartment.select().count()

    def save_apartment(self, apartment_dto):
        # type: (ApartmentDTO) -> Optional[ApartmentDTO]
        _ = self
        # TODO: Check if the rebus id's actually exists
        apartment_orm = ApartmentMapper.dto_to_orm(apartment_dto)
        apartment_orm.save()
        return self.load_apartment(apartment_orm.id)

    def update_apartment(self, apartment_dto):
        # type: (ApartmentDTO) -> Optional[ApartmentDTO]
        _ = self
        # TODO: Check if the rebus id's actually exists
        if 'id' not in apartment_dto.loaded_fields or apartment_dto.id is None:
            raise RuntimeError('cannot update an apartment without the id being set')
        try:
            apartment_orm = Apartment.select().where(Apartment.id == apartment_dto.id).first()
            for field in apartment_dto.loaded_fields:
                if field == 'id':
                    continue
                if hasattr(apartment_orm, field):
                    setattr(apartment_orm, field, getattr(apartment_dto, field))
            apartment_orm.save()
        except Exception as e:
            raise RuntimeError('Could not update the user: {}'.format(e))
        return self.load_apartment(apartment_dto.id)

    def delete_apartment(self, apartment_dto):
        # type: (ApartmentDTO) -> None
        _ = self
        if "id" in apartment_dto.loaded_fields and apartment_dto.id is not None:
            Apartment.delete_by_id(apartment_dto.id)
        elif "name" in apartment_dto.loaded_fields:
            # First check if there is only one:
            if Apartment.select().where(Apartment.name == apartment_dto.name).count() <= 1:
                Apartment.delete().where(Apartment.name == apartment_dto.name).execute()
            else:
                raise RuntimeError('More than one apartment with the given name: {}'.format(apartment_dto.name))
        else:
            raise RuntimeError('Could not find an apartment with the name {} to delete'.format(apartment_dto.name))
        return

