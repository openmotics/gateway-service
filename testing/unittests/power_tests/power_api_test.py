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
from __future__ import absolute_import

import unittest

from energy.energy_api import EnergyAPI, BROADCAST_ADDRESS, ADDRESS_MODE
from gateway.enums import EnergyEnums


def decode(data):
    return ''.join(chr(c) for c in data)


class PowerApiTest(unittest.TestCase):
    def test_get_general_status(self):
        action = EnergyAPI.get_general_status(EnergyEnums.Version.POWER_MODULE)
        assert decode(action.create_input(1, 1)) == 'STRE\x01\x01GGST\x00\x93\r\n'
        assert decode(action.create_output(1, 1, 42)) == 'RTRE\x01\x01GGST\x02*\x00\xde\r\n'

    def test_get_voltage(self):
        action = EnergyAPI.get_voltage(EnergyEnums.Version.POWER_MODULE)
        assert decode(action.create_input(1, 1)) == 'STRE\x01\x01GVOL\x00\xb6\r\n'
        assert decode(action.create_output(1, 1, 49.5)) == 'RTRE\x01\x01GVOL\x04\x00\x00FB#\r\n'

    def test_get_current(self):
        action = EnergyAPI.get_current(EnergyEnums.Version.POWER_MODULE)
        assert decode(action.create_input(1, 1)) == 'STRE\x01\x01GCUR\x00b\r\n'
        assert decode(action.create_output(1, 1, 49.5, 49.5, 49.5, 49.5, 49.5, 49.5, 49.5, 49.5)) == 'RTRE\x01\x01GCUR \x00\x00FB\x00\x00FB\x00\x00FB\x00\x00FB\x00\x00FB\x00\x00FB\x00\x00FB\x00\x00FB\x05\r\n'

    def test_get_status_p1(self):
        action = EnergyAPI.get_status_p1(EnergyEnums.Version.P1_CONCENTRATOR)
        assert decode(action.create_input(1, 1)) == 'STRC\x01\x01GSP\x00\x00\x00\r\n'
        assert decode(action.create_output(1, 1, 42)) == 'RTRC\x01\x01GSP\x00\x01*\xa9\r\n'

    def test_set_addressmode(self):
        action = EnergyAPI.set_addressmode(EnergyEnums.Version.POWER_MODULE)
        assert decode(action.create_input(BROADCAST_ADDRESS, 1, ADDRESS_MODE)) == 'STRE\xff\x01SAGT\x01\x01\x0b\r\n'
        assert decode(action.create_output(1, 1)) == 'RTRE\x01\x01SAGT\x00t\r\n'

    def test_set_addressmode_p1(self):
        action = EnergyAPI.set_addressmode(EnergyEnums.Version.P1_CONCENTRATOR)
        assert decode(action.create_input(BROADCAST_ADDRESS, 2, ADDRESS_MODE)) == 'STRC\xff\x02SAGT\x01\x01\xc5\r\n'
        assert decode(action.create_output(1, 1)) == 'RTRC\x01\x01SAGT\x00\x00\r\n'
