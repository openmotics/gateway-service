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


if False:  # MyPy
    from typing import Dict, Any, List



class SystemConfigController(object):
    ESAFE_CONFIG_PREFIX = 'ESAFE_'
    DEFAULT_CONFIG = {
        # 'db_version': '006',
        'ESAFE_doorbell_enabled': '1',
        'ESAFE_rfid_enabled': '1',
        'ESAFE_device_name': 'ESAFE',
        'ESAFE_country': 'BE',
        'ESAFE_postal_code': '',
        'ESAFE_city': '',
        'ESAFE_street': 'vgs',
        'ESAFE_house_number': 'test',
        'ESAFE_max_rfid': '4',
        'ESAFE_rfid_auth_key_A': '01deadbeef01',
        'ESAFE_rfid_auth_key_B': '01cafebabe01',
        'ESAFE_rfid_sector_block': '1',
        'ESAFE_language': 'Français',
        'ESAFE_rfid_security_enabled': '0',
        'ESAFE_activate_change_first_name_enabled': '1',
        'ESAFE_activate_change_last_name_enabled': '0',
        'ESAFE_activate_change_language_enabled': '1',
        'ESAFE_activate_change_user_code_enabled': '1'
    }

    @classmethod
    def get_config_value(cls, config_name):
        # type: (str) -> str
        config_name = cls.ESAFE_CONFIG_PREFIX + config_name
        default = cls.DEFAULT_CONFIG[config_name]
        config_value = Config.get_entry(config_name, default)
        if config_value == default:
            Config.set_entry(config_name, config_value)
        return config_value

    @classmethod
    def get_config_values(cls, config_names):
        # type: (List[str]) -> Dict[str]
        config_values = {x: cls.get_config_value(x) for x in config_names}
        return config_values

    @classmethod
    def get_doorbell_config(cls):
        # type: () -> Dict
        return cls.get_config_values(['doorbell_enabled'])

    @classmethod
    def get_rfid_config(cls):
        # type: () -> Dict
        return cls.get_config_values(['rfid_enabled', 'rfid_security_enabled', 'max_rfid', 'rfid_sector_block'])

    @classmethod
    def get_touchscreen_config(cls):
        # type: () -> Dict
        return {'calibrated': os.path.exists(constants.get_esafe_touchscreen_calibration_file())}

    @classmethod
    def get_global_config(cls):
        # type: () -> Dict
        return cls.get_config_values(['device_name', 'country', 'postal_code', 'city', 'street', 'house_number', 'language'])
