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
eSafe (de)serializer
"""
from __future__ import absolute_import

import logging

from gateway.api.serializers.base import SerializerToolbox
from gateway.dto.user import UserDTO
from gateway.api.serializers.esafe import ApartmentSerializer

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple

logger = logging.getLogger('openmotics')


class UserSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (UserDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'first_name': dto_object.first_name,
                'last_name': dto_object.last_name,
                'role': dto_object.role,
                # 'pin_code': dto_object.pin_code,  # Hide the pin code for the api
                'apartment': None,
                'accepted_terms': dto_object.accepted_terms}
        if fields is not None:
            if 'apartment' in fields:
                apartment_data = ApartmentSerializer.serialize(dto_object.apartment)
                data['apartment'] = apartment_data
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> Tuple[UserDTO, List[str]]
        loaded_fields = []
        user_id = None
        if 'id' in api_data:
            loaded_fields.append('id')
            user_id = api_data['id']
        user_dto = UserDTO(user_id)
        for field in ['first_name', 'last_name', 'role', 'pin_code']:
            if field in api_data:
                loaded_fields.append(field)
                setattr(user_dto, field, api_data[field])
        if 'apartment' in api_data:
            apartment_dto, _ = ApartmentSerializer.deserialize(api_data['apartment'])
            user_dto.apartment = apartment_dto
            loaded_fields.append('apartment')
        if 'password' in api_data:
            user_dto.set_password(api_data['apartment'])
        return user_dto, loaded_fields

