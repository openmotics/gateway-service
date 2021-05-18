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
System config dto's
"""

from gateway.dto.base import BaseDTO, capture_fields, generic_equal_func
from toolbox import Toolbox

if False:  # MYPY
    from typing import Any, Optional


@generic_equal_func
class SystemDoorbellConfigDTO(BaseDTO):
    @capture_fields
    def __init__(self, enabled=None):
        self.enabled = enabled


@generic_equal_func
class SystemRFIDConfigDTO(BaseDTO):
    @capture_fields
    def __init__(self, enabled=None, security_enabled=None, max_tags=None):
        self.enabled = enabled
        self.security_enabled = security_enabled
        self.max_tags = max_tags


@generic_equal_func
class SystemRFIDSectorBlockConfigDTO(BaseDTO):
    @capture_fields
    def __init__(self, rfid_sector_block=None):
        self.rfid_sector_block = rfid_sector_block


@generic_equal_func
class SystemTouchscreenConfigDTO(BaseDTO):
    @capture_fields
    def __init__(self, calibrated=None):
        self.calibrated = calibrated


@generic_equal_func
class SystemGlobalConfigDTO(BaseDTO):
    @capture_fields
    def __init__(self, device_name=None, country=None, postal_code=None, city=None, street=None, house_number=None, language=None):
        self.device_name = device_name
        self.country = country
        self.postal_code = postal_code
        self.city = city
        self.street = street
        self.house_number = house_number
        self.language = language


@generic_equal_func
class SystemActivateUserConfigDTO(BaseDTO):
    @capture_fields
    def __init__(self, change_first_name=None, change_last_name=None, change_language=None, change_pin_code=None):
        self.change_first_name = change_first_name
        self.change_last_name = change_last_name
        self.change_language = change_language
        self.change_pin_code = change_pin_code
