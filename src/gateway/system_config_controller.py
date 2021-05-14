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
from gateway.models import Config
from gateway.dto import SystemDoorbellConfigDTO, SystemRFIDConfigDTO, \
    SystemRFIDSectorBlockConfigDTO, SystemTouchscreenConfigDTO, SystemGlobalConfigDTO, \
    SystemActivateUserConfigDTO

from ioc import Injectable, Singleton

if False:  # MyPy
    from typing import Dict, Any, List, Optional
    from gateway.dto.base import BaseDTO


@Injectable.named('system_config_controller')
@Singleton
class SystemConfigController(object):

    ESAFE_CONFIG_PREFIX = 'ESAFE_'
    DEFAULT_CONFIG = {
        # 'db_version': '006',
        'ESAFE_doorbell_enabled': True,
        'ESAFE_rfid_enabled': True,
        'ESAFE_device_name': 'ESAFE',
        'ESAFE_country': 'BE',
        'ESAFE_postal_code': '',
        'ESAFE_city': '',
        'ESAFE_street': '',
        'ESAFE_house_number': '',
        'ESAFE_max_rfid': 4,
        'ESAFE_rfid_auth_key_A': '',
        'ESAFE_rfid_auth_key_B': '',
        'ESAFE_rfid_sector_block': 1,
        'ESAFE_language': 'English',
        'ESAFE_rfid_security_enabled': False,
        'ESAFE_activate_change_first_name_enabled': True,
        'ESAFE_activate_change_last_name_enabled': True,
        'ESAFE_activate_change_language_enabled': True,
        'ESAFE_activate_change_user_code_enabled': False
    }

    # # This translates the DTO name to the actual name that is used in the database
    # # KEY = Database-name; VALUE = DTO-name
    # TRANSLATIONS = {
    #     'doorbell_enabled': 'enabled',
    #     'rfid_enabled': 'enabled',
    #     'rfid_security_enabled': 'security_enabled',
    #     'max_rfid': 'max_tags',
    #     'activate_change_first_name_enabled': 'change_first_name',
    #     'activate_change_last_name_enabled': 'change_last_name',
    #     'activate_change_language_enabled': 'change_language',
    #     'activate_change_user_code_enabled': 'change_pin_code',
    # }
    # TRANSLATIONS_REVERSED = {TRANSLATIONS[x]: x for x in TRANSLATIONS}

    def __init__(self):
        # SystemConfigController.TRANSLATIONS_REVERSED = {SystemConfigController.TRANSLATIONS[x]: x for x in SystemConfigController.TRANSLATIONS}
        pass

    @classmethod
    def _get_config_value(cls, config_name):
        # type: (str) -> Any
        config_name = cls.ESAFE_CONFIG_PREFIX + config_name
        default = cls.DEFAULT_CONFIG[config_name]
        config_value = Config.get_entry(config_name, default)
        if config_value == default:
            Config.set_entry(config_name, config_value)
        return config_value

    @classmethod
    def _save_config_value(cls, config_name, config_value):
        # type: (str, Any) -> None
        config_name = cls.ESAFE_CONFIG_PREFIX + config_name
        Config.set_entry(config_name, config_value)

    @classmethod
    def _get_config_values(cls, config_names, translation=None):
        # type: (List[str], Optional[Dict[str, str]]) -> Dict[str]
        if translation is None:
            translation = {}

        config_values = {}
        for conf_name in config_names:
            config_name = translation.get(conf_name, conf_name)
            config_values[config_name] = cls._get_config_value(conf_name)
        return config_values

    @classmethod
    def _save_config_values(cls, config_dto, translation=None):
        # type: (BaseDTO, Optional[Dict[str, str]]) -> None
        if translation is None:
            translation = {}
        translations_reversed = {translation[x]: x for x in translation}
        for field in config_dto.loaded_fields:
            value = getattr(config_dto, field)
            field_translated = field
            if field in translations_reversed:
                field_translated = translations_reversed[field]
            cls._save_config_value(field_translated, value)

    @classmethod
    def get_doorbell_config(cls):
        # type: () -> SystemDoorbellConfigDTO
        conf = cls._get_config_values(['doorbell_enabled'], {'doorbell_enabled': 'enabled'})
        return SystemDoorbellConfigDTO(**conf)

    @classmethod
    def save_doorbell_config(cls, config_dto):
        # type: (SystemDoorbellConfigDTO) -> None
        cls._save_config_values(config_dto, {'doorbell_enabled': 'enabled'})

    @classmethod
    def get_rfid_config(cls):
        # type: () -> SystemRFIDConfigDTO
        conf = cls._get_config_values(['rfid_enabled', 'rfid_security_enabled', 'max_rfid'],
                                      {'rfid_enabled': 'enabled', 'rfid_security_enabled': 'security_enabled', 'max_rfid': 'max_tags'})
        return SystemRFIDConfigDTO(**conf)

    @classmethod
    def save_rfid_config(cls, config_dto):
        # type: (SystemRFIDConfigDTO) -> None
        cls._save_config_values(config_dto, {'rfid_enabled': 'enabled', 'rfid_security_enabled': 'security_enabled', 'max_rfid': 'max_tags'})

    @classmethod
    def get_rfid_sector_block_config(cls):
        # type: () -> SystemRFIDSectorBlockConfigDTO
        conf = cls._get_config_values(['rfid_sector_block'])
        return SystemRFIDSectorBlockConfigDTO(**conf)

    @classmethod
    def save_rfid_sector_block_config(cls, config_dto):
        # type: (SystemRFIDSectorBlockConfigDTO) -> None
        cls._save_config_values(config_dto)

    @classmethod
    def get_touchscreen_config(cls):
        # type: () -> SystemTouchscreenConfigDTO
        return SystemTouchscreenConfigDTO(calibrated=os.path.exists(constants.get_esafe_touchscreen_calibration_file()))

    @classmethod
    def save_touchscreen_config(cls):
        # type: () -> None
        # TODO: run the calibrate touchscreen script
        raise NotImplementedError()

    @classmethod
    def get_global_config(cls):
        # type: () -> SystemGlobalConfigDTO
        conf = cls._get_config_values(['device_name', 'country', 'postal_code', 'city', 'street', 'house_number', 'language'])
        return SystemGlobalConfigDTO(**conf)

    @classmethod
    def save_global_config(cls, config_dto):
        # type: (SystemGlobalConfigDTO) -> None
        cls._save_config_values(config_dto)

    @classmethod
    def get_activate_user_config(cls):
        # type: () -> SystemActivateUserConfigDTO
        conf = cls._get_config_values(['activate_change_first_name_enabled',
                                       'activate_change_last_name_enabled',
                                       'activate_change_language_enabled',
                                       'activate_change_user_code_enabled'],
                                      {
                                          'activate_change_first_name_enabled': 'change_first_name',
                                          'activate_change_last_name_enabled': 'change_last_name',
                                          'activate_change_language_enabled': 'change_language',
                                          'activate_change_user_code_enabled': 'change_pin_code',
                                      })
        return SystemActivateUserConfigDTO(**conf)

    @classmethod
    def save_activate_user_config(cls, config_dto):
        # type: (SystemActivateUserConfigDTO) -> None
        cls._save_config_values(config_dto,
                                {
                                    'activate_change_first_name_enabled': 'change_first_name',
                                    'activate_change_last_name_enabled': 'change_last_name',
                                    'activate_change_language_enabled': 'change_language',
                                    'activate_change_user_code_enabled': 'change_pin_code',
                                })
