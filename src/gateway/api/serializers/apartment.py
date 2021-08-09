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
apartment (de)serializer
"""
from __future__ import absolute_import

import logging

from gateway.api.serializers.base import SerializerToolbox
from gateway.dto.apartment import ApartmentDTO

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)

class ApartmentSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (ApartmentDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'name': dto_object.name,
                'mailbox_rebus_id': dto_object.mailbox_rebus_id,
                'doorbell_rebus_id': dto_object.doorbell_rebus_id}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> ApartmentDTO
        apartment_dto = ApartmentDTO()
        SerializerToolbox.deserialize(
            dto=apartment_dto,
            api_data=api_data,
            mapping={
                'id': ('id', None),
                'name': ('name', None),
                'mailbox_rebus_id': ('mailbox_rebus_id', None),
                'doorbell_rebus_id': ('doorbell_rebus_id', None)
            }
        )
        return apartment_dto
