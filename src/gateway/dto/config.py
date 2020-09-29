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
settings DTO
"""

from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Optional, Any


class ConfigDTO(BaseDTO):
    def __init__(self, setting, data=None):
        # type: (str, Optional[str]) -> None
        self.setting = setting
        self.data = data


    def __str__(self):
        return "ConfigDTO: {}".format(vars(self))

    def __eq__(self, other):
        if not isinstance(other, ConfigDTO):
            return False
        return self.setting.lower() == other.setting.lower() and self.data == other.data
