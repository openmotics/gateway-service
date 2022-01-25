"""
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
from __future__ import absolute_import
import unittest
import xmlrunner
from mock import Mock
from ioc import Scope, SetTestMode, SetUpTestInjections
from gateway.enums import LedStates, SerialPorts, Leds
from gateway.hal.frontpanel_controller_core import FrontpanelCoreController


class FrontpanelControllerCoreTest(unittest.TestCase):
    """ Tests for FrontpanelCoreController. """
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self._controller = FrontpanelControllerCoreTest._get_controller()

    def test_serial_activity(self):
        self._controller._report_serial_activity(SerialPorts.P1, False)
        self.assertLed(Leds.P1, LedStates.SOLID)
        self._controller._report_serial_activity(SerialPorts.P1, True)
        self.assertLed(Leds.P1, LedStates.BLINKING_50)

    def test_report_carrier(self):
        self._controller._report_carrier(False)
        self._controller._report_connectivity(False)
        self.assertLed(Leds.LAN_RED, LedStates.SOLID)
        self.assertLed(Leds.LAN_GREEN, LedStates.OFF)
        self._controller._report_carrier(True)
        self._controller._report_connectivity(False)
        self.assertLed(Leds.LAN_RED, LedStates.BLINKING_50)
        self.assertLed(Leds.LAN_GREEN, LedStates.OFF)
        self._controller._report_carrier(True)
        self._controller._report_connectivity(True)
        self.assertLed(Leds.LAN_RED, LedStates.OFF)
        self.assertLed(Leds.LAN_GREEN, LedStates.SOLID)

    def test_report_network_activity(self):
        self._controller._carrier = True
        self._controller._connectivity = True
        self._controller._report_network_activity(False)
        self.assertLed(Leds.LAN_GREEN, LedStates.SOLID)
        self._controller._report_network_activity(True)
        self.assertLed(Leds.LAN_GREEN, LedStates.BLINKING_50)

    def test_report_cloud_vpn(self):
        self._controller._report_cloud_reachable(False)
        self._controller._report_vpn_open(False)
        self.assertLed(Leds.CLOUD, LedStates.OFF)
        self._controller._report_cloud_reachable(True)
        self._controller._report_vpn_open(False)
        self.assertLed(Leds.CLOUD, LedStates.BLINKING_50)
        self._controller._report_cloud_reachable(False)
        self._controller._report_vpn_open(True)
        self.assertLed(Leds.CLOUD, LedStates.BLINKING_50)
        self._controller._report_cloud_reachable(True)
        self._controller._report_vpn_open(True)
        self.assertLed(Leds.CLOUD, LedStates.SOLID)

    def assertLed(self, led, state):
        self.assertEqual(state, self._controller._led_states.get(led))

    @staticmethod
    @Scope
    def _get_controller():
        driver_map = {}
        for chip_id, chip_mapping in FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM['CORE'].items():
            for led_id, led_name in chip_mapping.items():
                driver_map[led_name] = (chip_id, led_id)

        led_states = {}
        led_modes = {}
        for chip_id in range(2):
            led_states[chip_id] = {}
            led_modes[chip_id] = {}
            for led_id in range(16):
                led_states[chip_id][led_id] = False
                led_modes[chip_id][led_id] = LedStates.SOLID

        def drive_led(led, state):
            drive_chip_id, drive_led_id = driver_map[led]
            led_states[drive_chip_id][drive_led_id] = 'ON' if state != LedStates.OFF else 'OFF'
            led_modes[drive_chip_id][drive_led_id] = state if state != LedStates.OFF else LedStates.SOLID

        SetUpTestInjections(master_communicator=Mock(),
                            master_controller=Mock(),
                            energy_communicator=Mock(),
                            uart_controller=Mock(),
                            energy_module_controller=Mock())
        controller = FrontpanelCoreController()
        controller._master_controller.drive_led = drive_led
        controller._platform = 'CORE'
        return controller


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
