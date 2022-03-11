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
Ventilation Mapper
"""
from __future__ import absolute_import

import logging

from gateway.dto.ventilation import VentilationDTO, VentilationSourceDTO
from gateway.models import Plugin, Ventilation

if False:  # MYPY
    from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VentilationMapper(object):
    def __init__(self, db):
        self._db = db

    def orm_to_dto(self, orm_object):
        # type: (Ventilation) -> VentilationDTO
        source_dto = VentilationSourceDTO(None, type=orm_object.source)
        if orm_object.source == Ventilation.Sources.PLUGIN and orm_object.plugin:
            source_dto.id = orm_object.plugin.id
            source_dto.name = orm_object.plugin.name
        return VentilationDTO(orm_object.id,
                              source=source_dto,
                              external_id=orm_object.external_id,
                              name=orm_object.name,
                              amount_of_levels=orm_object.amount_of_levels,
                              device_vendor=orm_object.device_vendor,
                              device_type=orm_object.device_type,
                              device_serial=orm_object.device_serial)

    def dto_to_orm(self, ventilation_dto):  # type: (VentilationDTO) -> Ventilation
        lookup_kwargs = {}  # type: Dict[str,Any]
        if ventilation_dto.id is not None:
            lookup_kwargs.update({'id': ventilation_dto.id})
        if 'external_id' in ventilation_dto.loaded_fields:
            lookup_kwargs.update({'external_id': ventilation_dto.external_id})
        if ventilation_dto.source.is_plugin:
            plugin = self._db.query(Plugin) \
                .filter_by(name=ventilation_dto.source.name) \
                .one()  # type: Plugin
            lookup_kwargs.update({'plugin': plugin,
                                  'source': ventilation_dto.source.type})
        ventilation = self._db.query(Ventilation) \
            .filter_by(**lookup_kwargs) \
            .one_or_none()  # type: Optional[Ventilation]
        if ventilation is None:
            ventilation = Ventilation(**lookup_kwargs)
        if 'name' in ventilation_dto.loaded_fields:
            ventilation.name = ventilation_dto.name
        if 'amount_of_levels' in ventilation_dto.loaded_fields:
            ventilation.amount_of_levels = ventilation_dto.amount_of_levels
        if 'device_vendor' in ventilation_dto.loaded_fields and 'device_type' in ventilation_dto.loaded_fields:
            ventilation.device_vendor = ventilation_dto.device_vendor
            ventilation.device_type = ventilation_dto.device_type
            if ventilation_dto.device_serial:
                ventilation.device_serial = ventilation_dto.device_serial
        return ventilation
