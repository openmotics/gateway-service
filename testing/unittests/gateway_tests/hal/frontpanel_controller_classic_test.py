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


class FrontpanelControllerClassicTest(unittest.TestCase):
    """ Tests for FrontpanelClassicController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_serial_activity(self):
        controller = FrontpanelControllerClassicTest._get_controller()
        for activity, led_state in [(False, FrontpanelController.LedStates.OFF),
                                    (True, FrontpanelController.LedStates.BLINKING_50),
                                    (True, FrontpanelController.LedStates.BLINKING_50),
                                    (False, FrontpanelController.LedStates.OFF),
                                    (False, FrontpanelController.LedStates.OFF)]:
            controller._report_serial_activity(FrontpanelController.SerialPorts.MASTER_API, activity)
            self.assertEqual(led_state, controller._enabled_leds[FrontpanelController.Leds.COMMUNICATION_2])

    def test_report_carrier(self):
        controller = FrontpanelControllerClassicTest._get_controller()
        controller._report_carrier(False)
        self.assertEqual(FrontpanelController.LedStates.SOLID, controller._enabled_leds[FrontpanelController.Leds.STATUS_RED])
        controller._report_carrier(True)
        self.assertEqual(FrontpanelController.LedStates.OFF, controller._enabled_leds[FrontpanelController.Leds.STATUS_RED])

    def test_report_network_activity(self):
        controller = FrontpanelControllerClassicTest._get_controller()
        for activity, led_state in [(False, FrontpanelController.LedStates.OFF),
                                    (True, FrontpanelController.LedStates.BLINKING_50),
                                    (True, FrontpanelController.LedStates.BLINKING_50),
                                    (False, FrontpanelController.LedStates.OFF),
                                    (False, FrontpanelController.LedStates.OFF)]:
            controller._report_network_activity(activity)
            self.assertEqual(led_state, controller._enabled_leds[FrontpanelController.Leds.ALIVE])

    def test_report_cloud_reachable(self):
        controller = FrontpanelControllerClassicTest._get_controller()
        controller._report_cloud_reachable(False)
        self.assertEqual(FrontpanelController.LedStates.OFF, controller._enabled_leds[FrontpanelController.Leds.CLOUD])
        controller._report_cloud_reachable(True)
        self.assertEqual(FrontpanelController.LedStates.SOLID, controller._enabled_leds[FrontpanelController.Leds.CLOUD])

    def test_report_vpn_open(self):
        controller = FrontpanelControllerClassicTest._get_controller()
        controller._report_vpn_open(False)
        self.assertEqual(FrontpanelController.LedStates.OFF, controller._enabled_leds[FrontpanelController.Leds.VPN])
        controller._report_vpn_open(True)
        self.assertEqual(FrontpanelController.LedStates.SOLID, controller._enabled_leds[FrontpanelController.Leds.VPN])

    def test_mapping(self):
        controller = FrontpanelControllerClassicTest._get_controller()
        led = FrontpanelController.Leds.CLOUD
        for state, sequence in {FrontpanelController.LedStates.OFF: [False, False, False, False, False, False, False, False],
                                FrontpanelController.LedStates.SOLID: [True, True, True, True, True, True, True, True],
                                FrontpanelController.LedStates.BLINKING_25: [True, False, False, False, True, False, False, False],
                                FrontpanelController.LedStates.BLINKING_50: [True, True, False, False, True, True, False, False],
                                FrontpanelController.LedStates.BLINKING_75: [True, True, True, False, True, True, True, False]}.items():
            controller._enabled_leds[led] = state
            recorded_sequence = []
            for i in range(8):
                recorded_sequence.append(controller._map_states().get(led))
            self.assertEqual(sequence, recorded_sequence)

    @staticmethod
    @Scope
    def _get_controller():
        from gateway.hal.frontpanel_controller_classic import FrontpanelClassicController
        SetUpTestInjections(leds_i2c_address=0x0,
                            master_controller=Mock(),
                            energy_communicator=Mock(),
                            uart_controller=Mock())
        return FrontpanelClassicController()


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
