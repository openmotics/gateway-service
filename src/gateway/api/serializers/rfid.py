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

logger = logging.getLogger('openmotics')

class RfidSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (RfidDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'tag_string': dto_object.tag_string,
                'label': dto_object.label,
                'timestamp_created': dto_object.timestamp_created,
                'timestamp_last_used': dto_object.timestamp_last_used,
                'user_id': dto_object.user.id if dto_object.user is not None else None}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> RfidDTO
        raise NotImplementedError("Should never receive RFID data trough the api")
