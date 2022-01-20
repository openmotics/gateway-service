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
from threading import Lock, Event
from gateway.enums import Leds, Buttons, ButtonStates, SerialPorts, LedStates
from gateway.daemon_thread import DaemonThread
from gateway.hal.frontpanel_controller import FrontpanelController
from ioc import INJECTED, Inject
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer
from master.core.events import Event as MasterCoreEvent
from platform_utils import Platform

if False:  # MYPY
    from typing import Any, Dict, List, Optional
    from master.core.core_communicator import CoreCommunicator
    from gateway.hal.master_controller import MasterController

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
    AVAILABLE_LEDS = {}  # type: Dict[str, List[str]]
    for platform, chip_mapping in LED_MAPPING_ID_TO_ENUM.items():
        leds = AVAILABLE_LEDS.setdefault(platform, [])
        for chip, pin_mapping in chip_mapping.items():
            leds += list(pin_mapping.values())
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
        self._led_controllers = {}  # type: Dict[str, LedController]
        self._led_controller_lock = Lock()
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

    def _handle_event(self, data):  # type: (Dict[str, Any]) -> None
        return self._process_event(MasterCoreEvent(data))

    def _process_event(self, core_event):  # type: (MasterCoreEvent) -> None
        # From both the LED_BLINK and LED_ON event, the LED_ON event will always be sent first
        if core_event.type == MasterCoreEvent.Types.LED_BLINK:
            with self._led_event_lock:
                chip = core_event.data['chip']
                if chip in FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[self._platform]:
                    for led_id in range(16):
                        led = FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[self._platform][chip].get(led_id)
                        if led is None:
                            continue
                        with self._led_controller_lock:
                            led_controller = self._led_controllers.setdefault(led, LedController(led))
                        led_controller.set_mode(core_event.data['leds'][led_id])
                        led_controller.report()
        elif core_event.type == MasterCoreEvent.Types.LED_ON:
            with self._led_event_lock:
                chip = core_event.data['chip']
                if chip in FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[self._platform]:
                    for led_id in range(16):
                        led = FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[self._platform][chip].get(led_id)
                        if led is None:
                            continue
                        new_state = core_event.data['leds'].get(led_id, MasterCoreEvent.LedStates.OFF)
                        with self._led_controller_lock:
                            led_controller = self._led_controllers.setdefault(led, LedController(led))
                        led_controller.set_on(new_state != MasterCoreEvent.LedStates.OFF)
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
            self._drive_led(led=Leds.LAN_GREEN, state=LedStates.OFF)
            state = LedStates.SOLID
            if self._carrier:
                state = LedStates.BLINKING_50
            self._drive_led(led=Leds.LAN_RED, state=state)
        else:
            self._drive_led(led=Leds.LAN_RED, state=LedStates.OFF)
            state = LedStates.SOLID
            if self._activity:
                state = LedStates.BLINKING_50
            self._drive_led(led=Leds.LAN_GREEN, state=state)

    def _report_serial_activity(self, serial_port, activity):
        # type: (str, Optional[bool]) -> None
        led = {SerialPorts.P1: Leds.P1,
               SerialPorts.EXPANSION: Leds.EXPANSION}.get(serial_port)
        if led is None:
            return
        state = LedStates.SOLID
        if activity is None:
            state = LedStates.OFF
        elif activity:
            state = LedStates.BLINKING_50
        self._drive_led(led=led, state=state)

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
        if not self._cloud and not self._vpn:
            state = LedStates.OFF
        elif self._cloud != self._vpn:
            state = LedStates.BLINKING_50
        else:
            state = LedStates.SOLID
        self._drive_led(led=Leds.CLOUD, state=state)

    def _drive_led(self, led, state):
        if led not in FrontpanelCoreController.AVAILABLE_LEDS[self._platform]:
            return
        with self._led_controller_lock:
            led_controller = self._led_controllers.setdefault(led, LedController(led))
        try:
            led_controller.set(state=state)
        except Exception as ex:
            logger.error(ex)


class LedController(object):
    FORCE_TOGGLE_WAIT = 2.0

    @Inject
    def __init__(self, led, master_controller=INJECTED):
        self._master_controller = master_controller  # type: MasterController
        self._led = led  # type: str
        self._state = 'UNKNOWN'
        self._desired_state = None  # type: Optional[str]
        self._on = None  # type: Optional[bool]
        self._mode = None  # type: Optional[str]
        self._change_pending = False
        self._event = Event()
        self._event_lock = Lock()
        self._force_toggle = True  # Ensures an event is received
        self._failures = False

    @property
    def state(self):
        return self._state

    def set(self, state, timeout=2.0):   # type: (str, float) -> None
        with self._event_lock:
            if state == self._state:
                return
            self._event.clear()
            self._desired_state = state
            if self._force_toggle:
                inverted_state = LedStates.OFF if state != LedStates.OFF else LedStates.SOLID
                self._master_controller.drive_led(led=self._led,
                                                  state=inverted_state)
                time.sleep(LedController.FORCE_TOGGLE_WAIT)  # Give a possible event some propagation time
                self._force_toggle = False
            self._master_controller.drive_led(led=self._led,
                                              state=state)
        if not self._event.wait(timeout=timeout):
            # Due to race conditions in the master it happens that events are not send. This means this code can
            # either not use the events at all and assumes state, or it forces a toggle next time to trigger a
            # new event if none has been received yet. The current implementation uses the latter.
            self._force_toggle = True
            self._failures = True
            raise RuntimeError('Could not update {0} led to {1} in {2}s'.format(self._led, state, timeout))
        elif self._failures:
            logger.info('Led {0} state recovered, current state: {1}'.format(self._led, state))
            self._failures = False

    def report(self):
        state = LedStates.OFF
        if self._on:
            state = self._mode
        with self._event_lock:
            if self._state != state:
                logger.debug('Led {0} new state: {1} -> {2}'.format(self._led, self._state, state))
            self._state = state
            if self._state == self._desired_state:
                self._desired_state = None
                self._event.set()
                return True
        return False

    def set_on(self, on):  # type: (bool) -> None
        self._on = on

    def set_mode(self, mode):  # type: (str) -> None
        self._mode = mode
