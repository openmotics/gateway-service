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
System config serializer
"""

from gateway.dto.base import BaseDTO
from gateway.dto.system_config import SystemDoorbellConfigDTO, SystemRFIDConfigDTO, \
    SystemRFIDSectorBlockConfigDTO, SystemTouchscreenConfigDTO, SystemGlobalConfigDTO, \
    SystemActivateUserConfigDTO

if False:  #MyPy
    from typing import Dict, Any


class SystemConfigSerializer(object):
    TRANSLATION = {}  # type: Dict[str, str]  # KEYS = dto-naming, VALUES = api/serial-naming
    DTO = None

    @classmethod
    def serialize(cls, dto_object):
        # type: (BaseDTO) -> Dict[str, Any]
        serial_data = {}
        for dto_naming, serial_naming in cls.TRANSLATION.items():
            serial_data[serial_naming] = getattr(dto_object, dto_naming)
        return serial_data

    @classmethod
    def deserialize(cls, serial_data):
        # type: (Dict[str, Any]) -> BaseDTO
        if cls.DTO is None:
            raise RuntimeError('The dto type is not specified to return to')
        translation_reverse = {v: k for k, v in cls.TRANSLATION.items()}
        dto_object = cls.DTO()
        for serial_key, serial_value in serial_data.items():
            if serial_key not in translation_reverse:
                raise ValueError('Cannot deserialize system config {}: key "{}" is not a valid key'.format(cls.__name__, serial_key))
            dto_key_naming = translation_reverse[serial_key]
            setattr(dto_object, dto_key_naming, serial_value)
        return dto_object


class SystemDoorbellConfigSerializer(SystemConfigSerializer):
    DTO = SystemDoorbellConfigDTO
    TRANSLATION = {
        'enabled': 'enabled'
    }


class SystemRFIDConfigSerializer(SystemConfigSerializer):
    DTO = SystemRFIDConfigDTO
    TRANSLATION = {
        'enabled': 'enabled',
        'security_enabled': 'security_enabled',
        'max_tags': 'max_tags',
    }


class SystemRFIDSectorBlockConfigSerializer(SystemConfigSerializer):
    DTO = SystemRFIDSectorBlockConfigDTO
    TRANSLATION = {
        'rfid_sector_block': 'rfid_sector_block'
    }


class SystemTouchscreenConfigSerializer(SystemConfigSerializer):
    DTO = SystemTouchscreenConfigDTO
    TRANSLATION = {
        'calibrated': 'calibrated'
    }


class SystemGlobalConfigSerializer(SystemConfigSerializer):
    DTO = SystemGlobalConfigDTO
    TRANSLATION = {
        'device_name': 'device_name',
        'country': 'country',
        'postal_code': 'postal_code',
        'city': 'city',
        'street': 'street',
        'house_number': 'house_number',
        'language': 'language',
    }


class SystemActivateUserConfigSerializer(SystemConfigSerializer):
    DTO = SystemActivateUserConfigDTO
    TRANSLATION = {
        'change_first_name': 'change_first_name_enabled',
        'change_last_name': 'change_last_name_enabled',
        'change_language': 'change_language_enabled',
        'change_pin_code': 'change_user_code_enabled'
    }
