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

logger = logging.getLogger('openmotics')

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
        # type: (Dict[str,Any]) -> Tuple[ApartmentDTO, List[str]]
        loaded_fields = []
        apartment_id = None
        if 'id' in api_data:
            loaded_fields.append('id')
            apartment_id = api_data['id']
        name = ''
        if 'name' in api_data:
            loaded_fields.append('name')
            name = api_data['name']
        mailbox_rebus_id = None
        if 'mailbox_rebus_id' in api_data:
            loaded_fields.append('mailbox_rebus_id')
            mailbox_rebus_id = api_data['mailbox_rebus_id']
        doorbell_rebus_id = None
        if 'doorbell_rebus_id' in api_data:
            loaded_fields.append('doorbell_rebus_id')
            doorbell_rebus_id = api_data['doorbell_rebus_id']
        apartment_dto = ApartmentDTO(apartment_id, name, mailbox_rebus_id, doorbell_rebus_id)
        return apartment_dto, loaded_fields
