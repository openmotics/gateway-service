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
from gateway.hal.frontpanel_controller import FrontpanelController


class FrontpanelControllerCoreTest(unittest.TestCase):
    """ Tests for FrontpanelCoreController. """

    LED_STATE = {}

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_serial_activity(self):
        controller = FrontpanelControllerCoreTest._get_controller()
        controller._report_serial_activity(FrontpanelController.SerialPorts.P1, False)
        self.assertLed(FrontpanelController.Leds.P1, True, FrontpanelController.LedStates.SOLID)
        controller._report_serial_activity(FrontpanelController.SerialPorts.P1, True)
        self.assertLed(FrontpanelController.Leds.P1, True, FrontpanelController.LedStates.BLINKING_50)

    def test_report_carrier(self):
        controller = FrontpanelControllerCoreTest._get_controller()
        controller._report_carrier(False)
        controller._report_connectivity(False)
        self.assertLed(FrontpanelController.Leds.LAN_RED, True, FrontpanelController.LedStates.SOLID)
        self.assertLed(FrontpanelController.Leds.LAN_GREEN, False, FrontpanelController.LedStates.SOLID)
        controller._report_carrier(True)
        controller._report_connectivity(False)
        self.assertLed(FrontpanelController.Leds.LAN_RED, True, FrontpanelController.LedStates.BLINKING_50)
        self.assertLed(FrontpanelController.Leds.LAN_GREEN, False, FrontpanelController.LedStates.SOLID)
        controller._report_carrier(True)
        controller._report_connectivity(True)
        self.assertLed(FrontpanelController.Leds.LAN_RED, False, FrontpanelController.LedStates.SOLID)
        self.assertLed(FrontpanelController.Leds.LAN_GREEN, True, FrontpanelController.LedStates.SOLID)

    def test_report_network_activity(self):
        controller = FrontpanelControllerCoreTest._get_controller()
        controller._carrier = True
        controller._connectivity = True
        controller._report_network_activity(False)
        self.assertLed(FrontpanelController.Leds.LAN_GREEN, True, FrontpanelController.LedStates.SOLID)
        controller._report_network_activity(True)
        self.assertLed(FrontpanelController.Leds.LAN_GREEN, True, FrontpanelController.LedStates.BLINKING_50)

    def test_report_cloud_vpn(self):
        controller = FrontpanelControllerCoreTest._get_controller()
        controller._report_cloud_reachable(False)
        controller._report_vpn_open(False)
        self.assertLed(FrontpanelController.Leds.CLOUD, False, FrontpanelController.LedStates.SOLID)
        controller._report_cloud_reachable(True)
        controller._report_vpn_open(False)
        self.assertLed(FrontpanelController.Leds.CLOUD, True, FrontpanelController.LedStates.BLINKING_50)
        controller._report_cloud_reachable(False)
        controller._report_vpn_open(True)
        self.assertLed(FrontpanelController.Leds.CLOUD, True, FrontpanelController.LedStates.BLINKING_50)
        controller._report_cloud_reachable(True)
        controller._report_vpn_open(True)
        self.assertLed(FrontpanelController.Leds.CLOUD, True, FrontpanelController.LedStates.SOLID)

    def assertLed(self, led, on, mode):
        self.assertEqual((on, mode), FrontpanelControllerCoreTest.LED_STATE.get(led))

    @staticmethod
    @Scope
    def _get_controller():
        def set_led(led, on, mode):
            FrontpanelControllerCoreTest.LED_STATE[led] = (on, mode)

        from gateway.hal.frontpanel_controller_core import FrontpanelCoreController
        SetUpTestInjections(master_communicator=Mock(),
                            master_controller=Mock(),
                            power_communicator=Mock(),
                            uart_controller=Mock())
        controller = FrontpanelCoreController()
        controller._set_led = set_led
        return controller


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
