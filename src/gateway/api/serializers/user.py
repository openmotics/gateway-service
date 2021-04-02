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
user (de)serializer
"""
from __future__ import absolute_import

import logging

from gateway.api.serializers.base import SerializerToolbox
from gateway.dto.user import UserDTO
from gateway.api.serializers.apartment import ApartmentSerializer

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple, Union

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
                'accepted_terms': dto_object.accepted_terms}  # type: Dict[str, Any]
        if fields is not None and 'apartment' in fields:
            apartment_data = ApartmentSerializer.serialize(dto_object.apartment)
            data['apartment'] = apartment_data
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> UserDTO
        user_id = api_data['id'] if 'id' in api_data else None
        user_dto = UserDTO(user_id)
        for field in ['first_name', 'last_name', 'role', 'pin_code', 'accepted_terms']:
            if field in api_data:
                setattr(user_dto, field, api_data[field])
        apartment_dto = None
        if 'apartment' in api_data:
            if api_data['apartment'] is not None:
                apartment_dto = ApartmentSerializer.deserialize(api_data['apartment'])
            user_dto.apartment = apartment_dto
        if 'password' in api_data:
            user_dto.set_password(api_data['password'])
        return user_dto

