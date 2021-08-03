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

from six.moves.queue import Queue, Empty

from gateway.daemon_thread import DaemonThread

from ioc import Injectable, Singleton

if False:  # MYPY
    from typing import Callable, Dict, List, Literal, Tuple
    from gateway.events import GatewayEvent, EsafeEvent
    from gateway.hal.master_event import MasterEvent
    GATEWAY_TOPIC = Literal['config', 'state']
    MASTER_TOPIC = Literal['configuration', 'module', 'power', 'output', 'input', 'shutter', 'sensor']
    ESAFE_TOPIC = Literal['delivery', 'lock', 'config', 'rfid']

logger = logging.getLogger(__name__)


@Injectable.named('pubsub')
@Singleton
class PubSub(object):

    class MasterTopics(object):
        CONFIGURATION = 'configuration'  # type: MASTER_TOPIC
        OUTPUT = 'output'  # type: MASTER_TOPIC
        INPUT = 'input'  # type: MASTER_TOPIC
        SHUTTER = 'shutter'  # type: MASTER_TOPIC
        SENSOR = 'sensor'  # type: MASTER_TOPIC

    class GatewayTopics(object):
        CONFIG = 'config'  # type: GATEWAY_TOPIC
        STATE = 'state'  # type: GATEWAY_TOPIC

    class EsafeTopics(object):
        DELIVERY = 'delivery'   # type: ESAFE_TOPIC
        LOCK = 'lock'           # type: ESAFE_TOPIC
        CONFIG = 'config'       # type: ESAFE_TOPIC
        RFID = 'rfid'           # type: ESAFE_TOPIC

    def __init__(self):
        # type: () -> None
        self._gateway_topics = defaultdict(list)  # type: Dict[GATEWAY_TOPIC,List[Callable[[GatewayEvent],None]]]
        self._master_topics = defaultdict(list)  # type: Dict[MASTER_TOPIC,List[Callable[[MasterEvent],None]]]
        self._esafe_topics = defaultdict(list)  # type: Dict[ESAFE_TOPIC,List[Callable[[EsafeEvent],None]]]
        self._master_events = Queue()  # type: Queue  # Queue[Tuple[str, MasterEvent]]
        self._gateway_events = Queue()  # type: Queue  # Queue[Tuple[str, GatewayEvent]]
        self._esafe_events = Queue()  # type: Queue  # Queue[Tuple[str, GatewayEvent]]
        self._pub_thread = DaemonThread(name='pubsub', target=self._publisher_loop, interval=0.1, delay=0.2)
        self._is_running = False

    def start(self):
        # type: () -> None
        self._is_running = True
        self._pub_thread.start()

    def stop(self):
        # type: () -> None
        self._is_running = False
        self._master_events.put(None)
        self._gateway_events.put(None)
        self._esafe_events.put(None)
        self._pub_thread.stop()

    def _publisher_loop(self):
        while self._is_running:
            self._publish_all_events()

    def _publish_all_events(self, blocking=True):
        while True:
            try:
                event = self._master_events.get(block=blocking, timeout=0.25)
                if event is None:
                    return
                self._publish_master_event(*event)
            except Empty:
                break
        while True:
            try:
                event = self._gateway_events.get(block=blocking, timeout=0.25)
                if event is None:
                    return
                self._publish_gateway_event(*event)
            except Empty:
                break
        while True:
            try:
                event = self._esafe_events.get(block=blocking, timeout=0.25)
                if event is None:
                    return
                self._publish_esafe_event(*event)
            except Empty:
                break

    def subscribe_master_events(self, topic, callback):
        # type: (MASTER_TOPIC, Callable[[MasterEvent],None]) -> None
        self._master_topics[topic].append(callback)

    def publish_master_event(self, topic, master_event):
        # type: (MASTER_TOPIC, MasterEvent) -> None
        self._master_events.put((topic, master_event))

    def _publish_master_event(self, topic, master_event):
        # type: (MASTER_TOPIC, MasterEvent) -> None
        callbacks = self._master_topics[topic]
        if callbacks:
            logger.debug('Received master event %s on topic "%s"', master_event.type, topic)
        else:
            logger.warning('Received master event %s on topic "%s" without subscribers', master_event.type, topic)
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
        self._gateway_events.put((topic, gateway_event))

    def _publish_gateway_event(self, topic, gateway_event):
        # type: (GATEWAY_TOPIC, GatewayEvent) -> None
        logger.debug('Publishing gateway event {} {}'.format(topic, gateway_event))
        callbacks = self._gateway_topics[topic]
        if callbacks:
            logger.debug('Received gateway event %s on topic "%s"', gateway_event.type, topic)
        else:
            logger.warning('Received gateway event %s on topic "%s" without subscribers', gateway_event.type, topic)
        for callback in callbacks:
            try:
                logger.debug('Executing callback {} with {}'.format(callback.__name__, gateway_event))
                callback(gateway_event)
            except Exception:
                logger.exception('Failed to call handle %s for topic %s', callback, topic)

    def subscribe_esafe_events(self, topic, callback):
        # type: (ESAFE_TOPIC, Callable[[EsafeEvent],None]) -> None
        self._esafe_topics[topic].append(callback)

    def publish_esafe_event(self, topic, esafe_event):
        # type: (ESAFE_TOPIC, EsafeEvent) -> None
        self._esafe_events.put((topic, esafe_event))

    def _publish_esafe_event(self, topic, esafe_event):
        # type: (ESAFE_TOPIC, EsafeEvent) -> None
        logger.debug('Publishing esafe event {} {}'.format(topic, esafe_event))
        callbacks = self._esafe_topics[topic]
        if callbacks:
            logger.debug('Received esafe event %s on topic "%s"', esafe_event.type, topic)
        else:
            logger.warning('Received esafe event %s on topic "%s" without subscribers', esafe_event.type, topic)
        for callback in callbacks:
            try:
                logger.debug('Executing callback {} with {}'.format(callback.__name__, esafe_event))
                callback(esafe_event)
            except Exception:
                logger.exception('Failed to call handle %s for topic %s', callback, topic)
