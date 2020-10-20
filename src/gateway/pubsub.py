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

from ioc import Injectable, Singleton

if False:  # MYPY
    from typing import Callable, Dict, List, Literal
    from gateway.events import GatewayEvent
    from gateway.hal.master_event import MasterEvent
    MASTER_TOPIC = Literal['eeprom', 'maintenance', 'master']

logger = logging.getLogger('openmotics')


@Injectable.named('pubsub')
@Singleton
class PubSub(object):

    class MasterTopics:
        EEPROM = 'eeprom'  # type: MASTER_TOPIC
        MAINTENANCE = 'maintenance'  # type: MASTER_TOPIC
        MASTER = 'master'  # type: MASTER_TOPIC

    def __init__(self):
        # type: () -> None
        self._master_topics = defaultdict(list)  # type: Dict[MASTER_TOPIC,List[Callable[[MasterEvent],None]]]

    def subscribe_master_events(self, topic, callback):
        # type: (MASTER_TOPIC, Callable[[MasterEvent],None]) -> None
        self._master_topics[topic].append(callback)

    def publish_master_event(self, topic, master_event):
        # type: (MASTER_TOPIC, MasterEvent) -> None
        callbacks = self._master_topics[topic]
        if not callbacks:
            logger.warning('Received master event %s on topic %s without subscribers', master_event.type, topic)
        for callback in callbacks:
            callback(master_event)
