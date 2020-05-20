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
from ioc import INJECTED, Inject, Injectable, Singleton
from gateway.hal.frontpanel_controller import FrontpanelController
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer, CoreCommunicator
from master.core.events import Event as MasterCoreEvent

if False:  # MYPY
    from typing import Any, Dict, Set
    from master.core.core_communicator import CoreCommunicator

logger = logging.getLogger("openmotics")


@Injectable.named('frontpanel_controller')
@Singleton
class FrontpanelCoreController(FrontpanelController):

    # TODO:
    #  * Support authorized mode

    LED_MAPPING_ID_TO_ENUM = {0: {0: FrontpanelController.Leds.RS485,
                                  1: FrontpanelController.Leds.STATUS_GREEN,
                                  2: FrontpanelController.Leds.STATUS_RED,
                                  3: FrontpanelController.Leds.CAN_STATUS_GREEN,
                                  4: FrontpanelController.Leds.CAN_STATUS_RED,
                                  5: FrontpanelController.Leds.CAN_COMMUNICATION,
                                  6: FrontpanelController.Leds.P1,
                                  7: FrontpanelController.Leds.LAN_GREEN,
                                  8: FrontpanelController.Leds.LAN_RED,
                                  9: FrontpanelController.Leds.CLOUD,
                                  10: FrontpanelController.Leds.SETUP,
                                  11: FrontpanelController.Leds.RELAYS_1_8,
                                  12: FrontpanelController.Leds.RELAYS_9_16,
                                  13: FrontpanelController.Leds.OUTPUTS_DIG_1_4,
                                  14: FrontpanelController.Leds.OUTPUTS_DIG_5_7,
                                  15: FrontpanelController.Leds.OUTPUTS_ANA_1_4,
                                  16: FrontpanelController.Leds.INPUTS_1_4}}
    LED_TO_BA = {FrontpanelController.Leds.P1: 6,
                 FrontpanelController.Leds.LAN_GREEN: 7,
                 FrontpanelController.Leds.LAN_RED: 8,
                 FrontpanelController.Leds.CLOUD: 9}
    BLINKING_MAP = {FrontpanelController.LedStates.BLINKING_25: 25,
                    FrontpanelController.LedStates.BLINKING_50: 50,
                    FrontpanelController.LedStates.BLINKING_75: 75,
                    FrontpanelController.LedStates.SOLID: 100}
    BUTTON_STATE_MAPPING_ID_TO_ENUM = {0: FrontpanelController.ButtonStates.RELEASED,
                                       1: FrontpanelController.ButtonStates.PRESSED}
    BUTTON_MAPPING_ID_TO_ENUM = {0: FrontpanelController.Buttons.SETUP,
                                 1: FrontpanelController.Buttons.ACTION,
                                 2: FrontpanelController.Buttons.CAN_POWER,
                                 3: FrontpanelController.Buttons.SELECT}

    @Inject
    def __init__(self, master_communicator=INJECTED):  # type: (CoreCommunicator) -> None
        super(FrontpanelCoreController, self).__init__()
        self._master_communicator = master_communicator
        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
        )
        self._led_states = {}  # type: Dict[int, str]
        self._active_leds = set()  # type: Set[int]
        self._carrier = False
        self._cloud = False
        self._vpn = False
        self._lan_green_on = None
        self._serial_port_on = None
        self._authorized_mode = True  # TODO: Replace

    def _handle_event(self, data):
        # type: (Dict[str, Any]) -> None
        core_event = MasterCoreEvent(data)
        if core_event.type == MasterCoreEvent.Types.LED_BLINK:
            chip = core_event.data['chip']
            if chip in FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM:
                for led_id in range(16):
                    led_name = FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[chip][led_id]
                    current_state = self._led_states.get(led_id)
                    new_state = FrontpanelController.LedStates.OFF
                    if led_id in self._active_leds:
                        new_state = core_event.data['leds'][led_id]
                    if new_state != current_state:
                        logger.info('Led {0} state change: {1} > {2}'.format(led_name, current_state, new_state))
                        self._led_states[led_id] = new_state
        elif core_event.type == MasterCoreEvent.Types.LED_ON:
            chip = core_event.data['chip']
            if chip in FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM:
                for led_id in range(16):
                    new_state = core_event.data['leds'].get(led_id, MasterCoreEvent.LedStates.OFF)
                    if new_state == MasterCoreEvent.LedStates.OFF:
                        self._active_leds.discard(led_id)
                    else:
                        self._active_leds.add(led_id)
        elif core_event.type == MasterCoreEvent.Types.BUTTON_PRESS:
            state = FrontpanelCoreController.BUTTON_STATE_MAPPING_ID_TO_ENUM.get(core_event.data['state'])
            if state is not None:
                button = FrontpanelCoreController.BUTTON_MAPPING_ID_TO_ENUM[core_event.data['button']]
                logger.info('Button {0} was {1}'.format(button, state))

    def start(self):
        super(FrontpanelCoreController, self).start()

    def stop(self):
        super(FrontpanelCoreController, self).stop()

    def _report_carrier(self, carrier):
        self._set_led(led=FrontpanelController.Leds.LAN_RED,
                      on=not carrier,
                      mode=FrontpanelController.LedStates.SOLID)

    def _report_network_activity(self, activity):
        lan_green = activity and self._carrier,
        if self._lan_green_on != lan_green:
            self._lan_green_on = lan_green
            self._set_led(led=FrontpanelController.Leds.LAN_GREEN,
                          on=lan_green,
                          mode=FrontpanelController.LedStates.BLINKING_50)

    def report_serial_activity(self, serial_port, activity):
        if serial_port != FrontpanelController.SerialPorts.P1:
            return
        if self._serial_port_on != activity:
            self._serial_port_on = activity
            self._set_led(led=FrontpanelController.Leds.P1,
                          on=activity,
                          mode=FrontpanelController.LedStates.BLINKING_50)

    def _report_cloud_reachable(self, reachable):
        if self._cloud != reachable:
            self._cloud = reachable
            self._update_cloud_led()

    def _report_vpn_open(self, vpn_open):
        if self._vpn != vpn_open:
            self._vpn = vpn_open
            self._update_cloud_led()

    def _update_cloud_led(self):
        # Cloud led state:
        # * Off: No heartbeat
        # * Blinking: Heartbeat but VPN not (yet) open
        # * Solid: Heartbeat and VPN is open
        blinking_mode = FrontpanelController.LedStates.SOLID
        if self._cloud and not self._vpn:
            blinking_mode = FrontpanelController.LedStates.BLINKING_50

        self._set_led(led=FrontpanelController.Leds.CLOUD,
                      on=self._cloud,
                      mode=blinking_mode)

    def _set_led(self, led, on, mode):
        if led not in FrontpanelCoreController.LED_TO_BA:
            return
        action = FrontpanelCoreController.LED_TO_BA[led]
        if mode not in FrontpanelCoreController.BLINKING_MAP:
            return
        extra_parameter = FrontpanelCoreController.BLINKING_MAP[mode]
        self._master_communicator.do_basic_action(action_type=210,
                                                  action=action,
                                                  device_nr=1 if on else 0,
                                                  extra_parameter=extra_parameter)
