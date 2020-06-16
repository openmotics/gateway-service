# Copyright (C) 2016 OpenMotics BV
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
The valiationbits module contains classes to track the current state of the validation bits on
the master.
"""

from __future__ import absolute_import
from threading import Lock
import six

if False:  # MYPY
    from typing import Dict


class ValidationBitStatus(object):
    """ Contains a cached version of the current validation bits of the master. """

    def __init__(self, on_validationbit_change=None):
        self._validationbits = {}
        self.on_validationbit_change = on_validationbit_change
        self._merge_lock = Lock()

    def full_update(self, validationbits):  # type: (Dict[int, bool]) -> None
        """ Update the status of the bits using a dict. """
        for bit_nr, value in six.iteritems(validationbits):
            self.update(bit_nr, value)

    def update(self, bit_nr, value):  # type: (int, bool) -> None
        """ Sets the validation bit value """
        with self._merge_lock:
            if value != self._validationbits.get(bit_nr):
                self._validationbits[bit_nr] = value
                self._report_change(bit_nr)

    def _report_change(self, bit_nr):
        if self.on_validationbit_change is not None:
            self.on_validationbit_change(bit_nr, self._validationbits.get(bit_nr))

    def get_validation_bit(self, bit_nr):
        return self._validationbits.get(bit_nr, False)
