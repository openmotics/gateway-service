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
System config BLL
"""
import os

import constants
from gateway.events import EsafeEvent
from gateway.models import Config
from gateway.pubsub import PubSub
from gateway.dto import SystemDoorbellConfigDTO, SystemRFIDConfigDTO, \
    SystemRFIDSectorBlockConfigDTO, SystemTouchscreenConfigDTO, SystemGlobalConfigDTO, \
    SystemActivateUserConfigDTO

from ioc import Injectable, Singleton, INJECTED, Inject

if False:  # MyPy
    from typing import Dict, Any, List, Optional
    from gateway.dto.base import BaseDTO
    from gateway.system_controller import SystemController


@Injectable.named('system_config_controller')
@Singleton
class SystemConfigController(object):

    def __init__(self):
        pass

    DEFAULT_CONFIG = {
        'doorbell_config': {'enabled': True},
        'rfid_config': {'enabled': True, 'security_enabled': False, 'max_tags': 4},
        'rfid_sector_block_config': {'rfid_sector_block': 1},
        'global_config': {'device_name': 'ESAFE', 'country': 'BE', 'postal_code': '', 'city': '', 'street': '', 'house_number': '', 'language': 'en'},
        'activate_user_config': {'change_first_name': True, 'change_last_name': True, 'change_language': True, 'change_pin_code': False},
        'rfid_auth_key_A': '',
        'rfid_auth_key_B': '',

    }

    @classmethod
    @Inject
    def send_event(cls, event_type, pubsub=INJECTED):
        # type: (str, PubSub) -> None
        event = EsafeEvent(EsafeEvent.Types.CONFIG_CHANGE, {'type': event_type})
        pubsub.publish_esafe_event(PubSub.EsafeTopics.CONFIG, event)

    @classmethod
    def get_config_value(cls, config_name):
        # type: (str) -> Any
        default = cls.DEFAULT_CONFIG[config_name]
        config_value = Config.get_entry(config_name, default)
        if config_value == default:
            Config.set_entry(config_name, config_value)
        return config_value

    @classmethod
    def save_config_value(cls, config_name, config_value):
        # type: (str, Any) -> None
        to_update_value = Config.get_entry(config_name, fallback=None)
        # first check if the values has been saved to the database
        if to_update_value is None:
            to_update_value = cls.DEFAULT_CONFIG[config_name]
        # if not, check if the combined values are all in the database, and add the ones that are not included
        elif isinstance(to_update_value, dict):
            for key in cls.DEFAULT_CONFIG[config_name]:
                if key not in to_update_value:
                    to_update_value[key] = cls.DEFAULT_CONFIG[config_name][key]

        # if it is a combined value, check if no other keys are set that aren't supposed too.
        if isinstance(to_update_value, dict):
            if isinstance(config_value, dict):
                for new_key in config_value:
                    if new_key in to_update_value:
                        to_update_value[new_key] = config_value[new_key]
                    else:
                        ValueError('Key "{}" does not exists in the old stored value, cannot add a new key')

            else:
                raise ValueError('Old stored value is a dict, but new value is not')

        Config.set_entry(config_name, to_update_value)

    @classmethod
    def get_doorbell_config(cls):
        # type: () -> SystemDoorbellConfigDTO
        config = cls.get_config_value('doorbell_config')
        return SystemDoorbellConfigDTO(**config)

    @classmethod
    def save_doorbell_config(cls, config_dto):
        # type: (SystemDoorbellConfigDTO) -> None
        cls.save_config_value('doorbell_config', {x: getattr(config_dto, x) for x in config_dto.loaded_fields})
        cls.send_event('doorbell')

    @classmethod
    def get_rfid_config(cls):
        # type: () -> SystemRFIDConfigDTO
        conf = cls.get_config_value('rfid_config')
        return SystemRFIDConfigDTO(**conf)

    @classmethod
    def save_rfid_config(cls, config_dto):
        # type: (SystemRFIDConfigDTO) -> None
        cls.save_config_value('rfid_config', {x: getattr(config_dto, x) for x in config_dto.loaded_fields})
        cls.send_event('rfid')

    @classmethod
    def get_rfid_sector_block_config(cls):
        # type: () -> SystemRFIDSectorBlockConfigDTO
        conf = cls.get_config_value('rfid_sector_block_config')
        return SystemRFIDSectorBlockConfigDTO(**conf)

    @classmethod
    def save_rfid_sector_block_config(cls, config_dto):
        # type: (SystemRFIDSectorBlockConfigDTO) -> None
        cls.save_config_value('rfid_sector_block_config', {x: getattr(config_dto, x) for x in config_dto.loaded_fields})
        cls.send_event('rfid_sector_block')

    @classmethod
    @Inject
    def get_touchscreen_config(cls, system_controller=INJECTED):
        # type: (SystemController) -> SystemTouchscreenConfigDTO
        return SystemTouchscreenConfigDTO(calibrated=system_controller.is_esafe_touchscreen_calibrated())

    @classmethod
    @Inject
    def save_touchscreen_config(cls, system_controller=INJECTED):
        # type: (SystemController) -> None
        system_controller.calibrate_esafe_touchscreen()
        cls.send_event('touchscreen')

    @classmethod
    def get_global_config(cls):
        # type: () -> SystemGlobalConfigDTO
        conf = cls.get_config_value('global_config')
        return SystemGlobalConfigDTO(**conf)

    @classmethod
    def save_global_config(cls, config_dto):
        # type: (SystemGlobalConfigDTO) -> None
        cls.save_config_value('global_config', {x: getattr(config_dto, x) for x in config_dto.loaded_fields})
        cls.send_event('global')

    @classmethod
    def get_activate_user_config(cls):
        # type: () -> SystemActivateUserConfigDTO
        conf = cls.get_config_value('activate_user_config')
        return SystemActivateUserConfigDTO(**conf)

    @classmethod
    def save_activate_user_config(cls, config_dto):
        # type: (SystemActivateUserConfigDTO) -> None
        cls.save_config_value('activate_user_config', {x: getattr(config_dto, x) for x in config_dto.loaded_fields})
        cls.send_event('activate_user')
