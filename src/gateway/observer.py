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

import logging
import ujson as json
from ioc import Injectable, Inject, INJECTED, Singleton
from toolbox import Toolbox
from gateway.dto import ShutterDTO
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from gateway.shutters import ShutterController
from bus.om_bus_events import OMBusEvents
from bus.om_bus_client import MessageClient

if False:  # MYPY
    from typing import Any, Dict, List

logger = logging.getLogger("openmotics")


class Event(object):
    """
    Event object
    """

    class Types(object):
        INPUT_CHANGE = 'INPUT_CHANGE'
        OUTPUT_CHANGE = 'OUTPUT_CHANGE'
        SHUTTER_CHANGE = 'SHUTTER_CHANGE'
        THERMOSTAT_CHANGE = 'THERMOSTAT_CHANGE'
        THERMOSTAT_GROUP_CHANGE = 'THERMOSTAT_GROUP_CHANGE'
        ACTION = 'ACTION'
        PING = 'PING'
        PONG = 'PONG'

    def __init__(self, event_type, data):
        self.type = event_type
        self.data = data

    def serialize(self):
        return {'type': self.type,
                'data': self.data,
                '_version': 1.0}  # Add version so that event processing code can handle multiple formats

    def __str__(self):
        return json.dumps(self.serialize())

    @staticmethod
    def deserialize(data):
        return Event(event_type=data['type'],
                     data=data['data'])


@Injectable.named('observer')
@Singleton
class Observer(object):
    """
    The Observer gets various (change) events and will also monitor certain datasets to manually detect changes
    """

    class Types(object):
        THERMOSTATS = 'THERMOSTATS'

    @Inject
    def __init__(self, master_controller=INJECTED, message_client=INJECTED, shutter_controller=INJECTED):
        self._master_controller = master_controller  # type: MasterController
        self._message_client = message_client  # type: MessageClient
        self._shutter_controller = shutter_controller  # type: ShutterController

        self._event_subscriptions = []
        self._master_controller.subscribe_event(self._master_event)
        self._shutter_controller.subscribe_shutter_change(self._shutter_changed)

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
                callback(Event(event_type=Event.Types.INPUT_CHANGE,
                               data=master_event.data))
        if master_event.type == MasterEvent.Types.OUTPUT_CHANGE:
            self._message_client.send_event(OMBusEvents.OUTPUT_CHANGE, {'id': master_event.data['id']})
            for callback in self._event_subscriptions:
                callback(Event(event_type=Event.Types.OUTPUT_CHANGE,
                               data=master_event.data))

    # Outputs

    def get_outputs(self):
        """ Returns a list of Outputs with their status """
        # TODO: also include other outputs (e.g. from plugins)
        return self._master_controller.get_output_statuses()

    def get_output(self, output_id):
        # TODO: also address other outputs (e.g. from plugins)
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

    # Shutters

    def _shutter_changed(self, shutter_id, shutter_data, shutter_state):  # type: (int, ShutterDTO, str) -> None
        """ Executed by the Shutter Status tracker when a shutter changed state """
        for callback in self._event_subscriptions:
            callback(Event(event_type=Event.Types.SHUTTER_CHANGE,
                           data={'id': shutter_id,
                                 'status': {'state': shutter_state},
                                 'location': {'room_id': Toolbox.nonify(shutter_data.room, 255)}}))
