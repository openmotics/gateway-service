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

from gateway.daemon_thread import DaemonThread, DaemonThreadWait
from ioc import INJECTED, Inject
from master.classic import master_api
from serial_utils import CommunicationStatus, CommunicationTimedOutException

if False:  # MYPY
    from typing import Literal, Optional
    from master.classic.master_communicator import MasterCommunicator

    HEALTH = Literal['success', 'unstable', 'failure']

logger = logging.getLogger('openmotics')


class MasterHeartbeat(object):
    """
    Monitors the status of the master communication.
    """
    @Inject
    def __init__(self, master_communicator=INJECTED):
        # type: (MasterCommunicator) -> None
        self._master_communicator = master_communicator
        self._failures = -1  # Start "offline"
        self._backoff = 60
        self._last_restart = 0.0
        self._min_threshold = 2
        self._thread = DaemonThread(name='masterheartbeat',
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
        if self._failures == -1:
            self._thread.request_single_run()
            time.sleep(2)
        return self._failures == 0

    def set_offline(self):
        # type: () -> None
        self._failures += 1

    def get_communicator_health(self):
        # type: () -> HEALTH
        if self._failures > self._min_threshold:
            stats = self._check_stats()
            if stats is None:
                return CommunicationStatus.UNSTABLE
            elif stats:
                return CommunicationStatus.SUCCESS
            else:
                return CommunicationStatus.FAILURE
        else:
            return CommunicationStatus.SUCCESS

    def _heartbeat(self):
        # type: () -> None
        if self._failures > self._min_threshold and self._last_restart < time.time() - self._backoff:
            logger.error('Master heartbeat failure, restarting communication')
            try:
                self._master_communicator.stop()
            finally:
                self._master_communicator.start()
            self._last_restart = time.time()
            self._backoff = self._backoff * 2
        try:
            self._master_communicator.do_command(master_api.status())
            if self._failures > 0:
                logger.info('Master heartbeat recovered after %s failures', self._failures)
            self._failures = 0
        except CommunicationTimedOutException:
            self._failures += 1
            logger.error('Master heartbeat %s failures', self._failures)
            raise DaemonThreadWait()
        except Exception:
            logger.error('Master heartbeat unhandled exception')
            raise

    def _check_stats(self):
        # type: () -> Optional[bool]
        """
        """
        stats = self._master_communicator.get_communication_statistics()
        calls_timedout = [call for call in stats['calls_timedout']]
        calls_succeeded = [call for call in stats['calls_succeeded']]
        all_calls = sorted(calls_timedout + calls_succeeded)

        if len(calls_timedout) == 0:
            # If there are no timeouts at all
            return True

        if len(all_calls) <= 10:
            # Not enough calls made to have a decent view on what's going on
            logger.warning('Observed master communication failures, but not enough calls')
            return None

        calls_last_x_minutes = [t for t in all_calls if t > time.time() - 180]
        if len(calls_last_x_minutes) <= 5:
            # Not enough calls in the last 3 minutes to have a decent view on what's going on
            logger.warning('Observed master communication failures, but not recent enough')
            return None

        if len(all_calls) >= 30 and not any(t in calls_timedout for t in all_calls[-30:]):
            # The last 30 calls are successfull, consider "recoverd"
            return True
        if not any(t in calls_timedout for t in all_calls[-10:]):
            # The last 10 calls are successfull, consider "recovering"
            logger.warning('Observed master communication failures, but recovering')
            return None

        ratio = len([t for t in calls_last_x_minutes if t in calls_timedout]) / float(len(calls_last_x_minutes))
        if ratio < 0.25:
            # Less than 25% of the calls fail, let's assume everything is just "fine"
            logger.warning('Observed master communication failures, but there\'s only a failure ratio of {:.2f}%'.format(ratio * 100))
            return None

        return False
