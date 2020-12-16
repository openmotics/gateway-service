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
from gateway.events import GatewayEvent
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import Any, Dict, List, Optional

logger = logging.getLogger("openmotics")


@Injectable.named('observer')
@Singleton
class Observer(object):
    """
    The Observer gets various (change) events and will also monitor certain datasets to manually detect changes
    """

    @Inject
    def __init__(self, master_controller=INJECTED, pubsub=INJECTED, message_client=INJECTED):
        self._master_controller = master_controller  # type: MasterController
        self._pubsub = pubsub  # type: PubSub
        self._message_client = message_client  # type: Optional[MessageClient]

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.INPUT, self._handle_master_event)

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        if master_event.type == MasterEvent.Types.INPUT_CHANGE:
            # TODO move to InputController
            gateway_event = GatewayEvent(event_type=GatewayEvent.Types.INPUT_CHANGE,
                                         data=master_event.data)
            self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    # Inputs

    def get_inputs(self):
        # type: () -> List[Dict[str,Any]]
        """ Returns a list of Inputs with their status """
        return self._master_controller.get_inputs_with_status()

    def get_recent(self):
        # type: () -> List[int]
        """ Returns a list of recently changed inputs """
        return self._master_controller.get_recent_inputs()
