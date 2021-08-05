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
RFID device abstract class to create an interface between rfid devices and others
"""

from six import add_metaclass
from abc import ABCMeta, abstractmethod


# Abstract class that will be the main interface for an rfid device
@add_metaclass(ABCMeta)
class RfidDevice:

    def __init__(self, callback=None):
        self.callback = callback

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    # Able to set a callback and call this function when a new
    # rfid badge is scanned in
    def set_new_scan_callback(self, callback):
        self.callback = callback
