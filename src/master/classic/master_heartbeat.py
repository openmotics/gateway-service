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

import logging
import time

from gateway.daemon_thread import DaemonThread
from ioc import INJECTED, Inject
from master.classic import master_api
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from master.classic.master_communicator import MasterCommunicator

logger = logging.getLogger('openmotics')


class MasterHeartbeat(object):
    """
    Monitors the status of the master communication.
    """
    @Inject
    def __init__(self, master_communicator=INJECTED):
        # type: (MasterCommunicator) -> None
        self._master_communicator = master_communicator
        self._failures = 0
        self._max_consecutive_failures = 2
        self._thread = DaemonThread(name='MasterHeartbeat',
                                    target=self._heartbeat,
                                    interval=30,
                                    delay=5)

    def start(self):
        # type: () -> None
        logger.info('Starting master heartbeat')
        self._thread.start()

    def stop(self):
        # type: () -> None
        self._thread.stop()

    def is_online(self):
        # type: () -> bool
        return self._failures == 0

    def set_offline(self):
        # type: () -> None
        self._failures += 1

    def _heartbeat(self):
        # type: () -> None
        if self._failures > self._max_consecutive_failures:
            logger.error('Master heartbeat unhealthy, restarting')
            # FIXME: just flush or rename.
            self._master_communicator.update_mode_start()
            time.sleep(1)
            self._master_communicator.update_mode_stop()
        try:
            self._master_communicator.do_command(master_api.status())
            if self._failures > 0:
                logger.error('Master heartbeat recovered')
            self._failures = 0
        except CommunicationTimedOutException:
            self._failures += 1
            logger.error('Master heartbeat communication timeout failures %s', self._failures)
            raise
        except Exception:
            raise
