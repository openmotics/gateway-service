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
Base DTO
"""


class BaseDTO(object):

    @staticmethod
    def _nonify(value, default_value):
        return None if value == default_value else value

    @staticmethod
    def _denonify(value, default_value):
        return default_value if value is None else value

    @staticmethod
    def read_from_core_orm(core_object):
        raise NotImplementedError()

    @staticmethod
    def read_from_classic_orm(classic_object):
        raise NotImplementedError()
