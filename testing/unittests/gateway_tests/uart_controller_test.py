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
Tests for the UART controller.
"""
from __future__ import absolute_import

import unittest
from mock import Mock
from gateway.uart_controller import UARTController


class RoomControllerTest(unittest.TestCase):
    def test_decorators(self):
        mocked_client = Mock()
        mocked_client.read_register.return_value = 1.0
        mocked_client.write_register = Mock()

        uart_controller = UARTController(uart_port='/dev/null')
        uart_controller._get_modbus_client = lambda *args, **kwargs: mocked_client
        with self.assertRaises(RuntimeError):
            uart_controller.read_register(0, 0)
        with self.assertRaises(RuntimeError):
            uart_controller.write_register(0, 0, 0)
        uart_controller.set_mode(mode=UARTController.Mode.MODBUS)
        self.assertEqual(1.0, uart_controller.read_register(0, 0))
        uart_controller.write_register(0, 0, 2.0)
        mocked_client.write_register.assert_called_with(functioncode=16,
                                                        number_of_decimals=0,
                                                        registeraddress=0,
                                                        signed=False,
                                                        value=2.0)
