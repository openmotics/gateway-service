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
            return
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
        apartment_orm = Apartment.select().where(Apartment.id == apartment_id).first()

    def save_apartment(self, apartment_dto):
        # type: (ApartmentDTO) -> ApartmentDTO
        _ = self
        apartment_orm = ApartmentMapper.dto_to_orm(apartment_dto)
        apartment_orm.save()
        return self.load_apartment(apartment_orm.id)


