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
from functools import wraps
from toolbox import Toolbox

if False:  # MYPY
    from typing import Set


class BaseDTO(object):
    _loaded_fields = set()  # type: Set[str]
    _init_done = False

    def __str__(self):
        return '<{} {}>'.format(self.__class__.__name__,
                                {field: self.__dict__[field] for field in self._loaded_fields})

    def __repr__(self):
        return str(self)

    def __ne__(self, other):
        return not (self == other)

    def __setattr__(self, key, value):
        if self._init_done and key in self.__dict__:
            self._loaded_fields.add(key)
        object.__setattr__(self, key, value)

    @property
    def loaded_fields(self):
        return list(self._loaded_fields)


def capture_fields(func):
    field_names = Toolbox.get_parameter_names(func)
    field_names.pop(0)  # Remove `self`

    @wraps(func)
    def new_init(self, *args, **kwargs):
        self._loaded_fields = set(field_names[:len(args)] + list(kwargs.keys()))
        self._init_done = True
        func(self, *args, **kwargs)

    return new_init
