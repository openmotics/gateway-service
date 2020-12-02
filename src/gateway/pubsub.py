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
from __future__ import absolute_import

from collections import defaultdict
import logging

from gateway.daemon_thread import DaemonThread

from ioc import Injectable, Singleton

if False:  # MYPY
    from typing import Callable, Dict, List, Literal
    from gateway.events import GatewayEvent
    from gateway.hal.master_event import MasterEvent
    GATEWAY_TOPIC = Literal['config', 'state']
    MASTER_TOPIC = Literal['eeprom', 'maintenance', 'master', 'power']

logger = logging.getLogger('openmotics')


@Injectable.named('pubsub')
@Singleton
class PubSub(object):

    class MasterTopics(object):
        EEPROM = 'eeprom'  # type: MASTER_TOPIC
        MAINTENANCE = 'maintenance'  # type: MASTER_TOPIC
        MASTER = 'master'  # type: MASTER_TOPIC
        POWER = 'power'  # type: MASTER_TOPIC

    class GatewayTopics(object):
        CONFIG = 'config'  # type: GATEWAY_TOPIC
        STATE = 'state'  # type: GATEWAY_TOPIC

    def __init__(self):
        # type: () -> None
        self._gateway_topics = defaultdict(list)  # type: Dict[GATEWAY_TOPIC,List[Callable[[GatewayEvent],None]]]
        self._master_topics = defaultdict(list)  # type: Dict[MASTER_TOPIC,List[Callable[[MasterEvent],None]]]
        self._master_events = []  # type: List[Tuple[str, MasterEvent]]
        self._gateway_events = []  # type: List[Tuple[str, GatewayEvent]]
        self._pub_thread = DaemonThread(name='Publisher loop',
                                           target=self._publisher_loop,
                                           interval=0.1, delay=0.2)

    def start(self):
        # type: () -> None
        self._pub_thread.start()

    def stop(self):
        # type: () -> None
        self._pub_thread.stop()

    def _publisher_loop(self):
        while self._master_events:
            topic, master_event = self._master_events.pop(0)
            self._publish_master_event(topic, master_event)
        while self._gateway_events:
            topic, gateway_event = self._gateway_events.pop(0)
            self._publish_gateway_event(topic, gateway_event)

    def subscribe_master_events(self, topic, callback):
        # type: (MASTER_TOPIC, Callable[[MasterEvent],None]) -> None
        self._master_topics[topic].append(callback)

    def publish_master_event(self, topic, master_event):
        # type: (MASTER_TOPIC, MasterEvent) -> None
        self._master_events.append((topic, master_event))

    def _publish_master_event(self, topic, master_event):
        # type: (MASTER_TOPIC, MasterEvent) -> None
        callbacks = self._master_topics[topic]
        if not callbacks:
            logger.warning('Received master event %s on topic %s without subscribers', master_event.type, topic)
        for callback in callbacks:
            try:
                callback(master_event)
            except Exception:
                logger.exception('Failed to call handle %s for topic %s', callback, topic)

    def subscribe_gateway_events(self, topic, callback):
        # type: (GATEWAY_TOPIC, Callable[[GatewayEvent],None]) -> None
        self._gateway_topics[topic].append(callback)

    def publish_gateway_event(self, topic, gateway_event):
        # type: (GATEWAY_TOPIC, GatewayEvent) -> None
        self._gateway_events.append((topic, gateway_event))

    def _publish_gateway_event(self, topic, gateway_event):
        # type: (GATEWAY_TOPIC, GatewayEvent) -> None
        callbacks = self._gateway_topics[topic]
        if not callbacks:
            logger.warning('Received gateway event %s on topic %s without subscribers', gateway_event.type, topic)
        for callback in callbacks:
            try:
                callback(gateway_event)
            except Exception:
                logger.exception('Failed to call handle %s for topic %s', callback, topic)
