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
rfid (de)serializer
"""
from __future__ import absolute_import

import logging

from gateway.api.serializers.base import SerializerToolbox
from gateway.api.serializers.user import UserSerializer
from gateway.dto.rfid import RfidDTO

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)

class RfidSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (RfidDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'tag_string': dto_object.tag_string,
                'uid_manufacturer': dto_object.uid_manufacturer,
                'uid_extension': dto_object.uid_extension,
                'enter_count': dto_object.enter_count,
                'blacklisted': dto_object.blacklisted,
                'label': dto_object.label,
                'timestamp_created': dto_object.timestamp_created,
                'timestamp_last_used': dto_object.timestamp_last_used,
                'user': None}
        user_data = UserSerializer.serialize(dto_object.user)
        data['user'] = user_data
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> RfidDTO
        id = api_data['id'] if 'id' in api_data else None
        tag_string = api_data['tag_string'] if 'tag_string' in api_data else None
        uid_manufacturer = api_data['uid_manufacturer'] if 'uid_manufacturer' in api_data else None
        time_created = api_data['time_created'] if 'time_created' in api_data else None
        user_dto = UserSerializer.deserialize(api_data['user']) if 'user' in api_data else None

        rfid_dto = RfidDTO(id, tag_string, uid_manufacturer, time_created, user_dto)
        for field in ['uid_extension', 'enter_count', 'blacklisted', 'label', 'timestamp_last_used']:
            if field in api_data:
                setattr(rfid_dto, field, api_data[field])
        return rfid_dto
