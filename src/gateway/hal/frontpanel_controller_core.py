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
    #  * Send button press events
    #  * Support various reports
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

    @Inject
    def __init__(self, master_communicator=INJECTED):  # type: (CoreCommunicator) -> None
        super(FrontpanelCoreController, self).__init__()
        self._master_communicator = master_communicator
        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
        )
        self._led_states = {}  # type: Dict[int, str]
        self._active_leds = set()  # type: Set[int]
        self._authorized_mode = True  # TODO: Replace

    def _handle_event(self, data):
        # type: (Dict[str, Any]) -> None
        core_event = MasterCoreEvent(data)
        if core_event.type == MasterCoreEvent.Types.LED_BLINK:
            chip = core_event.data['chip']
            if chip in FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM:
                for led_id in range(16):
                    current_state = self._led_states.get(led_id)
                    new_state = FrontpanelController.LedStates.OFF
                    if led_id in self._active_leds:
                        new_state = core_event.data['leds'][led_id]
                    if new_state != current_state:
                        logger.info('LED {0} state change: {1} > {2}'.format(led_id, current_state, new_state))
                        self._led_states[led_id] = new_state
                        for callback in self._led_change_callbacks:
                            callback(FrontpanelController.LedChangedEvent(
                                led=FrontpanelCoreController.LED_MAPPING_ID_TO_ENUM[chip][led_id],
                                state=new_state
                            ))
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
            logger.info('Got button press: {0}'.format(core_event))

    def start(self):
        super(FrontpanelCoreController, self).start()

    def stop(self):
        super(FrontpanelCoreController, self).stop()

    def _report_carrier(self, carrier):
        pass  # TODO: Set correct led

    def _report_network_activity(self, activity):
        pass  # TODO: Set correct led

    def report_serial_activity(self, serial_port, activity):
        pass  # TODO: Set correct led

    def _report_cloud_reachable(self, reachable):
        pass  # TODO: Set correct led

    def _report_vpn_open(self, vpn_open):
        pass  # TODO: Set correct led
