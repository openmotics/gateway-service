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
Module for the frontpanel
"""
from __future__ import absolute_import
import logging
import time
from bus.om_bus_client import MessageClient, OMBusEvents
from platform_utils import Hardware
from gateway.daemon_thread import DaemonThread

if False:  # MYPY
    from typing import Callable, List

logger = logging.getLogger("openmotics")


class FrontpanelController(object):

    INDICATE_TIMEOUT = 30
    AUTH_MODE_PRESS_DURATION = 5.75
    AUTH_MODE_TIMEOUT = 60
    BOARD_TYPE = Hardware.get_board_type()
    if BOARD_TYPE in [Hardware.BoardType.BB, Hardware.BoardType.BBB]:
        MAIN_INTERFACE = 'eth0'
    elif BOARD_TYPE == Hardware.BoardType.BBGW:
        MAIN_INTERFACE = 'wlan0'
    else:
        MAIN_INTERFACE = 'lo'

    class LedChangedEvent(object):
        def __init__(self, led, state):
            self.led = led
            self.state = state

    class Leds(object):
        RS485 = 'RS485'
        STATUS_GREEN = 'STATUS_GREEN'
        STATUS_RED = 'STATUS_RED'
        CAN_STATUS_GREEN = 'CAN_STATUS_GREEN'
        CAN_STATUS_RED = 'CAN_STATUS_RED'
        CAN_COMMUNICATION = 'CAN_COMMUNICATION'
        P1 = 'P1'
        LAN_GREEN = 'LAN_GREEN'
        LAN_RED = 'LAN_RED'
        CLOUD = 'CLOUD'
        SETUP = 'SETUP'
        RELAYS_1_8 = 'RELAYS_1_8'
        RELAYS_9_16 = 'RELAYS_9_16'
        OUTPUTS_DIG_1_4 = 'OUTPUTS_DIG_1_4'
        OUTPUTS_DIG_5_7 = 'OUTPUTS_DIG_5_7'
        OUTPUTS_ANA_1_4 = 'OUTPUTS_ANA_1_4'
        INPUTS_1_4 = 'INPUTS_1_4'
        POWER = 'POWER'
        ALIVE = 'ALIVE'
        VPN = 'VPN'
        COMMUNICATION_1 = 'COMMUNICATION_1'
        COMMUNICATION_2 = 'COMMUNICATION_2'

    class LedStates(object):
        OFF = 'OFF'
        BLINKING_25 = 'BLINKING_25'
        BLINKING_50 = 'BLINKING_50'
        BLINKING_75 = 'BLINKING_75'
        SOLID = 'SOLID'

    class ButtonPressEvent(object):
        def __init__(self, button, state):  # type: (str, str) -> None
            self.button = button
            self.state = state

    class Buttons(object):
        SELECT = 'SELECT'
        SETUP = 'SETUP'
        ACTION = 'ACTION'
        CAN_POWER = 'CAN_POWER'

    class ButtonStates(object):
        PRESSED = 'PRESSED'
        RELEASED = 'RELEASED'

    class SerialPorts(object):
        MASTER_API = 'MASTER_API'
        ENERGY = 'ENERGY'

    def __init__(self):  # type: () -> None
        self._led_change_callbacks = []  # type: List[Callable[[FrontpanelController.LedChangedEvent], None]]
        self._button_press_callbacks = []  # type: List[Callable[[FrontpanelController.ButtonPressEvent], None]]
        self._network_carrier = None
        self._network_bytes = 0
        self._check_network_activity_thread = None
        self._authorized_mode = False
        self._authorized_mode_timeout = 0
        self._indicate = False
        self._indicate_timeout = 0
        self._message_client = None

    def _event_receiver(self, event, payload):
        if event == OMBusEvents.CLOUD_REACHABLE:
            self._report_cloud_reachable(payload)
        elif event == OMBusEvents.VPN_OPEN:
            self._report_vpn_open(payload)

    def subscribe_led_change(self, callback):
        self._led_change_callbacks.append(callback)

    def subscribe_button_presses(self, callback):
        self._button_press_callbacks.append(callback)

    def start(self):
        self._check_network_activity_thread = DaemonThread(name='Frontpanel runner',
                                                           target=self._do_frontpanel_tasks,
                                                           interval=0.5)
        self._check_network_activity_thread.start()
        # Connect to IPC
        self._message_client = MessageClient('led_service')
        self._message_client.add_event_handler(self._event_receiver)

    def stop(self):
        if self._check_network_activity_thread is not None:
            self._check_network_activity_thread.stop()

    def _report_carrier(self, carrier):
        raise NotImplementedError()

    def _report_network_activity(self, activity):
        raise NotImplementedError()

    def report_serial_activity(self, serial_port, activity):
        raise NotImplementedError()

    def _report_cloud_reachable(self, reachable):
        raise NotImplementedError()

    def _report_vpn_open(self, vpn_open):
        raise NotImplementedError()

    def indicate(self):
        self._indicate = True
        self._indicate_timeout = time.time() + FrontpanelController.INDICATE_TIMEOUT

    def _do_frontpanel_tasks(self):
        # Check network activity
        try:
            with open('/sys/class/net/{0}/carrier'.format(FrontpanelController.MAIN_INTERFACE), 'r') as fh_up:
                line = fh_up.read()
            carrier = int(line) == 1
            if self._network_carrier != carrier:
                self._network_carrier = carrier
                self._report_carrier(carrier)

            with open('/proc/net/dev', 'r') as fh_stat:
                for line in fh_stat.readlines():
                    if FrontpanelController.MAIN_INTERFACE in line:
                        received, transmitted = 0, 0
                        parts = line.split()
                        if len(parts) == 17:
                            received = parts[1]
                            transmitted = parts[9]
                        elif len(parts) == 16:
                            (_, received) = tuple(parts[0].split(':'))
                            transmitted = parts[8]
                        new_bytes = received + transmitted
                        if self._network_bytes != new_bytes:
                            self._network_bytes = new_bytes
                            network_activity = True
                        else:
                            network_activity = False
                        self._report_network_activity(network_activity)
        except Exception as exception:
            logger.error('Error while checking network activity: {0}'.format(exception))

        # Clear indicate timeout
        if time.time() > self._indicate_timeout:
            self._indicate = False
