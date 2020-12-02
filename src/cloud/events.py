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
Sends events to the cloud
"""
from __future__ import absolute_import
import logging
import time
from collections import deque
from peewee import DoesNotExist

from cloud.cloud_api_client import APIException, CloudAPIClient
from gateway.daemon_thread import DaemonThread, DaemonThreadWait
from gateway.events import GatewayEvent
from gateway.input_controller import InputController
from gateway.models import Config
from serial_utils import CommunicationTimedOutException
from ioc import INJECTED, Inject, Injectable, Singleton

logger = logging.getLogger('openmotics')

if False:  # MYPY
    from typing import Dict


@Injectable.named('event_sender')
@Singleton
class EventSender(object):

    @Inject
    def __init__(self, cloud_api_client=INJECTED, input_controller=INJECTED):  # type: (CloudAPIClient, InputController) -> None
        self._queue = deque()  # type: deque
        self._stopped = True
        self._cloud_client = cloud_api_client
        self._input_controller = input_controller
        self._event_enabled_cache = {}  # type: Dict[int, bool]
        self._events_queue = deque()  # type: deque
        self._events_thread = DaemonThread(name='EventSender loop',
                                           target=self._send_events_loop,
                                           interval=0.1, delay=0.2)

    def start(self):
        # type: () -> None
        self._events_thread.start()

    def stop(self):
        # type: () -> None
        self._events_thread.stop()

    def enqueue_event(self, event):
        if Config.get('cloud_enabled') is False:
            return
        if event.type == GatewayEvent.Types.CONFIG_CHANGE:
            if event.data.get('type') == 'input':
                self._event_enabled_cache = {}
        if self._should_send_event(event):
            event.data['timestamp'] = time.time()
            self._queue.appendleft(event)

    def _should_send_event(self, event):
        if event.type != GatewayEvent.Types.INPUT_CHANGE:
            return True
        input_id = event.data['id']
        if input_id in self._event_enabled_cache:
            return self._event_enabled_cache[input_id]
        try:
            try:
                input_ = self._input_controller.load_input(input_id)
                should_send = input_.event_enabled
            except DoesNotExist:
                should_send = False
            self._event_enabled_cache[input_id] = should_send
        except CommunicationTimedOutException:
            should_send = False
        return should_send

    def _send_events_loop(self):
        # type: () -> None
        try:
            if not self._batch_send_events():
                raise DaemonThreadWait
        except APIException as ex:
            logger.error('Error sending events to the cloud: {}'.format(str(ex)))

    def _batch_send_events(self):
        events = []
        while len(events) < 25:
            try:
                events.append(self._queue.pop())
            except IndexError:
                break
        if len(events) > 0:
            self._cloud_client.send_events(events)
            return True
        return False
