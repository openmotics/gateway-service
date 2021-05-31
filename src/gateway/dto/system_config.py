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

from gateway.dto.base import BaseDTO
from toolbox import Toolbox

if False:  # MYPY
    from typing import Any, Optional


class SystemDoorbellConfigDTO(BaseDTO):
    def __init__(self, enabled=None):
        # type: (bool) -> None
        self.enabled = enabled


class SystemRFIDConfigDTO(BaseDTO):
    def __init__(self, enabled=None, security_enabled=None, max_tags=None):
        # type: (bool, bool, int) -> None
        self.enabled = enabled
        self.security_enabled = security_enabled
        self.max_tags = max_tags


class SystemRFIDSectorBlockConfigDTO(BaseDTO):
    def __init__(self, rfid_sector_block=None):
        # type: (int) -> None
        self.rfid_sector_block = rfid_sector_block


class SystemTouchscreenConfigDTO(BaseDTO):
    def __init__(self, calibrated=None):
        # type: (bool) -> None
        self.calibrated = calibrated


class SystemGlobalConfigDTO(BaseDTO):
    def __init__(self, device_name=None, country=None, postal_code=None, city=None, street=None, house_number=None, language=None):
        # type: (str, str, str, str, str, str, str) -> None
        self.device_name = device_name
        self.country = country
        self.postal_code = postal_code
        self.city = city
        self.street = street
        self.house_number = house_number
        self.language = language


class SystemActivateUserConfigDTO(BaseDTO):
    def __init__(self, change_first_name=None, change_last_name=None, change_language=None, change_pin_code=None):
        # type: (bool, bool, bool, bool) -> None
        self.change_first_name = change_first_name
        self.change_last_name = change_last_name
        self.change_language = change_language
        self.change_pin_code = change_pin_code
