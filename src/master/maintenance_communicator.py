# Copyright (C) 2019 OpenMotics BV
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
The maintenance module contains the MaintenanceService class.
"""
from __future__ import absolute_import

if False:  # MYPY
    from typing import Any, Callable


class MaintenanceCommunicator(object):

    def start(self):
        # type: () -> None
        raise NotImplementedError()

    def stop(self):
        # type: () -> None
        raise NotImplementedError()

    def set_receiver(self, callback):
        # type: (Callable[[str],Any]) -> None
        raise NotImplementedError()

    def is_active(self):
        # type: () -> bool
        raise NotImplementedError()

    def activate(self):
        # type: () -> None
        raise NotImplementedError()

    def deactivate(self, join=True):
        # type: (bool) -> None
        raise NotImplementedError()

    def write(self, message):
        # type: (str) -> None
        raise NotImplementedError()
