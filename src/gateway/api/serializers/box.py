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
Box Serializer (mailbox and parcelbox_
"""

from __future__ import absolute_import

import logging

from gateway.api.serializers.base import SerializerToolbox
from gateway.api.serializers import ApartmentSerializer
from gateway.dto import ParcelBoxDTO, MailBoxDTO
from ioc import Inject, INJECTED

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)


class MailboxSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (MailBoxDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'label': dto_object.label,
                'open': dto_object.is_open,
                'apartment': None}
        if dto_object.apartment is not None:
            data['apartment'] = [ApartmentSerializer.serialize(dto_object.apartment)]
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> MailBoxDTO
        raise NotImplementedError('Api should never receive mailbox serial data')


class ParcelBoxSerializer(object):
    @staticmethod
    def serialize(dto_object, fields=None):
        # type: (ParcelBoxDTO, Optional[List[str]]) -> Dict[str,Any]
        data = {'id': dto_object.id,
                'label': dto_object.label,
                'height': dto_object.height,
                'width': dto_object.width,
                'size': dto_object.size.name,
                'available': dto_object.available,
                'open': dto_object.is_open}
        return SerializerToolbox.filter_fields(data, fields)

    @staticmethod
    def deserialize(api_data):
        # type: (Dict[str,Any]) -> MailBoxDTO
        raise NotImplementedError('Api should never receive parcelbox serial data')
