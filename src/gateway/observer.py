# Copyright (C) 2018 OpenMotics BV
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
The observer module contains logic to observe various states of the system. It keeps track of what is changing
"""

from __future__ import absolute_import

import logging

from bus.om_bus_client import MessageClient
from bus.om_bus_events import OMBusEvents
from gateway.events import GatewayEvent
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import Any, Dict, List, Optional
    from gateway.dto import OutputStateDTO

logger = logging.getLogger("openmotics")


@Injectable.named('observer')
@Singleton
class Observer(object):
    """
    The Observer gets various (change) events and will also monitor certain datasets to manually detect changes
    """

    class Types(object):
        THERMOSTATS = 'THERMOSTATS'

    @Inject
    def __init__(self, master_controller=INJECTED, message_client=INJECTED):
        self._master_controller = master_controller  # type: MasterController
        self._message_client = message_client  # type: Optional[MessageClient]

        self._event_subscriptions = []
        self._master_controller.subscribe_event(self._master_event)

    def subscribe_events(self, callback):
        """
        Subscribes a callback to generic events
        :param callback: the callback to call
        """
        self._event_subscriptions.append(callback)

    # Handle master "events"

    def _master_event(self, master_event):
        """
        Triggers when the MasterController generates events
        :type master_event: gateway.hal.master_controller.MasterEvent
        """
        if master_event.type == MasterEvent.Types.INPUT_CHANGE:
            for callback in self._event_subscriptions:
                callback(GatewayEvent(event_type=GatewayEvent.Types.INPUT_CHANGE,
                                      data=master_event.data))
        if master_event.type == MasterEvent.Types.OUTPUT_CHANGE:
            if self._message_client is not None:
                self._message_client.send_event(OMBusEvents.OUTPUT_CHANGE, {'id': master_event.data['id']})
            for callback in self._event_subscriptions:
                callback(GatewayEvent(event_type=GatewayEvent.Types.OUTPUT_CHANGE,
                                      data=master_event.data))

    # Outputs

    def get_outputs(self):
        # type: () -> List[OutputStateDTO]
        """ Returns a list of Outputs with their status """
        # TODO: Move to the OutputController
        return self._master_controller.get_output_statuses()

    def get_output(self, output_id):
        # type: (int) -> Optional[OutputStateDTO]
        # TODO: Move to the OutputController
        return self._master_controller.get_output_status(output_id)

    # Inputs

    def get_inputs(self):
        # type: () -> List[Dict[str,Any]]
        """ Returns a list of Inputs with their status """
        return self._master_controller.get_inputs_with_status()

    def get_recent(self):
        # type: () -> List[int]
        """ Returns a list of recently changed inputs """
        return self._master_controller.get_recent_inputs()
