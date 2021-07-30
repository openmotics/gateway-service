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
from threading import Lock

from gateway.enums import Leds, Buttons, ButtonStates, SerialPorts, LedStates
from gateway.daemon_thread import DaemonThread
from gateway.hal.frontpanel_controller import FrontpanelController
from ioc import INJECTED, Inject
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer
from master.core.events import Event as MasterCoreEvent
from platform_utils import Platform

if False:  # MYPY
    from typing import Any, Dict, Tuple, Optional
    from master.core.core_communicator import CoreCommunicator

logger = logging.getLogger(__name__)


class FrontpanelCoreController(FrontpanelController):
    LED_MAPPING_ID_TO_ENUM = {Platform.Type.CORE: {0: {4: Leds.STATUS_RED,
                                                       5: Leds.STATUS_GREEN,
                                                       13: Leds.SETUP,
                                                       14: Leds.CLOUD},
                                                   1: {4: Leds.CAN_STATUS_GREEN,
                                                       5: Leds.CAN_STATUS_RED,
                                                       11: Leds.LAN_RED,
                                                       12: Leds.LAN_GREEN,
                                                       13: Leds.P1,
                                                       15: Leds.CAN_COMMUNICATION}},
                              Platform.Type.CORE_PLUS: {0: {0: Leds.INPUTS,
                                                            1: Leds.EXPANSION,
                                                            2: Leds.STATUS_RED,
                                                            3: Leds.STATUS_GREEN,
                                                            5: Leds.LAN_RED,
                                                            6: Leds.CLOUD,
                                                            7: Leds.SETUP,
                                                            8: Leds.LAN_GREEN,
                                                            9: Leds.P1,
                                                            10: Leds.CAN_COMMUNICATION,
                                                            11: Leds.CAN_STATUS_RED,
                                                            12: Leds.CAN_STATUS_GREEN,
                                                            13: Leds.OUTPUTS_DIG_5_7,
                                                            14: Leds.OUTPUTS_ANA_1_4,
                                                            15: Leds.RELAYS_9_16},
                                                        1: {6: Leds.RELAYS_1_8,
                                                            7: Leds.OUTPUTS_DIG_1_4}}}
    BUTTON_STATE_MAPPING_ID_TO_ENUM = {0: ButtonStates.RELEASED,
                                       1: ButtonStates.PRESSED}
    BUTTON_MAPPING_ID_TO_ENUM = {0: Buttons.SETUP,
                                 1: Buttons.ACTION,
                                 2: Buttons.CAN_POWER,
                                 3: Buttons.SELECT}

    @Inject
    def __init__(self, master_communicator=INJECTED):  # type: (CoreCommunicator) -> None
        super(FrontpanelCoreController, self).__init__()
        self._master_communicator = master_communicator
        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
        )
        self._led_states = {}  # type: Dict[str, LedStateTracker]
        self._led_event_lock = Lock()
        self._carrier = True
        self._connectivity = True
        self._activity = False
        self._cloud = False
        self._vpn = False
        self._check_buttons_thread = None
        self._authorized_mode_buttons = [False, False]
        self._authorized_mode_buttons_pressed_since = None  # type: Optional[float]
        self._authorized_mode_buttons_released = False
        self._platform = Platform.get_platform()

    def _handle_event(self, data):
        # type: (Dict[str, Any]) -> None
        # From both the LED_BLINK and LED_ON event, the LED_ON event will always be send first
        core_event = MasterCoreEvent(data)
        if core_event.type == MasterCoreEvent.Types.LED_BLINK:
            with self._led_event_lock:
                chip = core_event.data['chip']
                if chip in FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[self._platform]:
                    for led_id in range(16):
                        led_name = FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[self._platform][chip].get(led_id)
                        if led_name is None:
                            continue
                        state_tracker = self._led_states.setdefault(led_name, LedStateTracker(led_name))
                        state_tracker.set_mode(core_event.data['leds'][led_id])
                        changed, state = state_tracker.get_state()
                        if changed:
                            logger.debug('Led {0} state: {1}'.format(led_name, state))
        elif core_event.type == MasterCoreEvent.Types.LED_ON:
            with self._led_event_lock:
                chip = core_event.data['chip']
                if chip in FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[self._platform]:
                    for led_id in range(16):
                        led_name = FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[self._platform][chip].get(led_id)
                        if led_name is None:
                            continue
                        state_tracker = self._led_states.setdefault(led_name, LedStateTracker(led_name))
                        event_state = core_event.data['leds'].get(led_id, MasterCoreEvent.LedStates.OFF)
                        state_tracker.set_on(event_state != MasterCoreEvent.LedStates.OFF)
        elif core_event.type == MasterCoreEvent.Types.BUTTON_PRESS:
            state = FrontpanelCoreController.BUTTON_STATE_MAPPING_ID_TO_ENUM.get(core_event.data['state'])
            if state is not None:
                button = FrontpanelCoreController.BUTTON_MAPPING_ID_TO_ENUM[core_event.data['button']]
                logger.info('Button {0} was {1}'.format(button, state))
                # Detect authorized mode
                if button == Buttons.ACTION:
                    self._authorized_mode_buttons[0] = state == ButtonStates.PRESSED
                elif button == Buttons.SETUP:
                    self._authorized_mode_buttons[1] = state == ButtonStates.PRESSED

    def start(self):
        super(FrontpanelCoreController, self).start()
        # Start polling/writing threads
        self._check_buttons_thread = DaemonThread(name='buttonchecker',
                                                  target=self._check_buttons,
                                                  interval=0.25)
        self._check_buttons_thread.start()

    def stop(self):
        super(FrontpanelCoreController, self).stop()
        if self._check_buttons_thread is not None:
            self._check_buttons_thread.stop()

    def _check_buttons(self):
        buttons_pressed = self._authorized_mode_buttons == [True, True]
        if not buttons_pressed:
            self._authorized_mode_buttons_released = True
        if self._authorized_mode:
            if time.time() > self._authorized_mode_timeout or (buttons_pressed and self._authorized_mode_buttons_released):
                logger.info('Authorized mode: inactive')
                self._authorized_mode = False
        else:
            if buttons_pressed:
                self._authorized_mode_buttons_released = False
                if self._authorized_mode_buttons_pressed_since is None:
                    self._authorized_mode_buttons_pressed_since = time.time()
                if time.time() - self._authorized_mode_buttons_pressed_since > FrontpanelController.AUTH_MODE_PRESS_DURATION:
                    logger.info('Authorized mode: active')
                    self._authorized_mode = True
                    self._authorized_mode_timeout = time.time() + FrontpanelController.AUTH_MODE_TIMEOUT
                    self._authorized_mode_buttons_pressed_since = None
            else:
                self._authorized_mode_buttons_pressed_since = None

    def _report_carrier(self, carrier):
        # type: (bool) -> None
        self._carrier = carrier
        self._update_lan_leds()

    def _report_connectivity(self, connectivity):
        # type: (bool) -> None
        self._connectivity = connectivity
        self._update_lan_leds()

    def _report_network_activity(self, activity):
        # type: (bool) -> None
        self._activity = activity
        self._update_lan_leds()

    def _update_lan_leds(self):
        if not self._carrier or not self._connectivity:
            self._master_controller.drive_led(led=Leds.LAN_GREEN,
                                              on=False,
                                              mode=LedStates.SOLID)
            mode = LedStates.SOLID
            if self._carrier:
                mode = LedStates.BLINKING_50
            self._master_controller.drive_led(led=Leds.LAN_RED,
                                              on=True, mode=mode)
        else:
            self._master_controller.drive_led(led=Leds.LAN_RED,
                                              on=False,
                                              mode=LedStates.SOLID)
            mode = LedStates.SOLID
            if self._activity:
                mode = LedStates.BLINKING_50
            self._master_controller.drive_led(led=Leds.LAN_GREEN,
                                              on=True, mode=mode)

    def _report_serial_activity(self, serial_port, activity):
        # type: (str, Optional[bool]) -> None
        led = {SerialPorts.P1: Leds.P1,
               SerialPorts.EXPANSION: Leds.EXPANSION}.get(serial_port)
        if led is None:
            return
        mode = LedStates.SOLID
        on = True
        if activity is None:
            on = False
        elif activity:
            mode = LedStates.BLINKING_50
        self._master_controller.drive_led(led=led, on=on, mode=mode)

    def _report_cloud_reachable(self, reachable):
        # type: (bool) -> None
        self._cloud = reachable
        self._update_cloud_led()

    def _report_vpn_open(self, vpn_open):
        # type: (bool) -> None
        self._vpn = vpn_open
        self._update_cloud_led()

    def _update_cloud_led(self):
        # Cloud led state:
        # * Off: No heartbeat
        # * Blinking: Heartbeat but VPN not (yet) open
        # * Solid: Heartbeat and VPN is open
        on = True
        if not self._cloud and not self._vpn:
            mode = LedStates.SOLID
            on = False
        elif self._cloud != self._vpn:
            mode = LedStates.BLINKING_50
        else:
            mode = LedStates.SOLID
        self._master_controller.drive_led(led=Leds.CLOUD,
                                          on=on,
                                          mode=mode)


class LedStateTracker(object):
    def __init__(self, led_name):
        self._led_name = led_name
        self._on = None  # type: Optional[bool]
        self._mode = None  # type: Optional[str]
        self._change_pending = False

    def set_on(self, on):
        # type: (bool) -> None
        if self._on != on:
            self._change_pending = True
        self._on = on

    def set_mode(self, mode):
        # type: (str) -> None
        if self._mode != mode:
            self._change_pending = True
        self._mode = mode
        if self._mode == LedStates.OFF:
            if self._on:
                self._change_pending = True
            self._on = False

    def get_state(self):
        # type: () -> Tuple[bool, str]
        if not self._on:
            state = LedStates.OFF
        else:
            state = self._mode if self._mode else LedStates.SOLID
        return_data = self._change_pending, state
        self._change_pending = False
        return return_data
