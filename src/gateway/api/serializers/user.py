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
import re

import constants
from gateway.apartment_controller import ApartmentController
from gateway.api.serializers.apartment import ApartmentSerializer
from gateway.api.serializers.base import SerializerToolbox
from gateway.dto import UserDTO, ApartmentDTO

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple, Union

logger = logging.getLogger(__name__)


class UserSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None, show_pin_code=False):
        # type: (UserDTO, Optional[List[str]], bool) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'username': dto_object.username,
                'first_name': dto_object.first_name,
                'last_name': dto_object.last_name,
                'role': dto_object.role,
                'language': dto_object.language,
                'apartment': None,
                'is_active': dto_object.is_active,
                'accepted_terms': dto_object.accepted_terms,
                'email': dto_object.email}  # type: Dict[str, Any]
        if 'apartment' in dto_object.loaded_fields and isinstance(dto_object.apartment, ApartmentDTO):
            apartment_data = ApartmentSerializer.serialize(dto_object.apartment)
            data['apartment'] = apartment_data
        if show_pin_code:
            data['pin_code'] = dto_object.pin_code
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> UserDTO
        user_dto = UserDTO()
        for field in ['id', 'username', 'first_name', 'last_name', 'role', 'pin_code', 'language', 'accepted_terms', 'is_active']:
            if field in api_data:
                setattr(user_dto, field, api_data[field])
        if 'apartment' in api_data and api_data['apartment'] is not None:
            if isinstance(api_data['apartment'], list):
                apartment_element = api_data['apartment'][0]
            else:
                apartment_element = api_data['apartment']
            if isinstance(apartment_element, int):
                if ApartmentController.apartment_id_exists(apartment_element):
                    apartment_dto = ApartmentController.load_apartment(apartment_element)
                    user_dto.apartment = apartment_dto
                else:
                    raise ValueError('apartment_id provided in user json does not exists')
            else:
                raise ValueError('user json deserialize: apartment is an id (int) or an array with an id')
        if 'password' in api_data:
            user_dto.set_password(api_data['password'])
        if 'email' in api_data:
            email_string = api_data['email']
            if not re.match(constants.get_email_verification_regex(), email_string):
                raise ValueError('Provided email address is not a valid email')
            user_dto.email = email_string
        return user_dto

