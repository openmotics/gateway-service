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

import six

from toolbox import Toolbox

if False:  # MYPY
    from typing import Set, Any


class DTOMeta(type):

    def capture_fields(cls, func):
        @wraps(func)
        def new_init(self, *args, **kwargs):
            self._loaded_fields = set(cls._field_names[:len(args)] + list(kwargs.keys()))
            self._init_done = True
            func(self, *args, **kwargs)
        return new_init

    def __init__(cls, name, bases, dct):
        cls_init = cls.__init__
        cls._field_names = Toolbox.get_parameter_names(cls_init)
        cls._field_names.pop(0)  # Remove `self`
        cls.__init__ = cls.capture_fields(cls_init)


class BaseDTO(six.with_metaclass(DTOMeta)):
    _loaded_fields = set()  # type: Set[str]
    _init_done = False

    # Create a dummy constructor to not have a slot-method in python2... This will make the meta class possible
    def __init__(self):
        pass

    def __str__(self):
        return '<{} {}>'.format(self.__class__.__name__,
                                {field: getattr(self, field) for field in self._loaded_fields})

    def __repr__(self):
        return str(self)

    def __ne__(self, other):
        return not (self == other)

    def __setattr__(self, key, value):
        if self._init_done and key in self.__dict__:
            self._loaded_fields.add(key)
        object.__setattr__(self, key, value)

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, self.__class__):
            return False
        for field in self._field_names:
            if getattr(self, field) != getattr(other, field):
                return False
        return True

    @property
    def loaded_fields(self):
        return list(self._loaded_fields)
