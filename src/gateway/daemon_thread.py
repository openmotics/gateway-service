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
import threading
import time

logger = logging.getLogger("openmotics")

if False:  # MYPY
    from typing import Any, Callable, Optional


class DaemonThreadWait(Exception):
    pass


class BaseThread(threading.Thread):
    def run(self):
        # type: () -> None
        try:
            import prctl
            prctl.set_name(self.name)
        except ImportError:
            pass
        super(BaseThread, self).run()


class DaemonThread(object):
    def __init__(self, name, target, interval=10, delay=None):
        # type: (str, Callable[[],Any], Optional[float], Optional[float]) -> None
        self._interval = interval
        self._delay = delay
        self._name = name
        self._target = target
        self._tick = threading.Event()
        self._stop = threading.Event()
        self._parent = threading.current_thread()
        self._thread = threading.Thread(target=self._run, name=name)

    def start(self):
        # type: () -> None
        logger.info('Starting daemon {}'.format(self._name))
        self._thread.start()

    def stop(self):
        # type: () -> None
        logger.info('Stopping daemon {}...'.format(self._name))
        self._stop.set()
        self._tick.set()
        self._thread.join(2)

    def sleep(self, timeout):
        # type: (Optional[float]) -> None
        if timeout == 0:
            return  # Don't sleep
        self._tick.wait(timeout)

    def set_interval(self, interval):
        # type: (Optional[float]) -> None
        changed = self._interval != interval
        self._interval = interval
        if changed:
            self._tick.set()

    def request_single_run(self):
        self._tick.set()

    def _get_sleep_interval(self, start):  # type: (float) -> Optional[float]
        if self._interval == 0 or self._interval is None:
            return self._interval
        min_wait_time = 0.1 if self._interval > 0.5 else 0.05
        return max(min_wait_time, self._interval - (time.time() - start))

    def _get_delay(self):  # type: () -> float
        if self._delay is not None:
            return self._delay
        if self._interval is None:
            return 20.0
        return self._interval * 2

    def _run(self):
        # type: () -> None
        try:
            import prctl
            prctl.set_name(self._name)
        except ImportError:
            pass
        backoff = 0.0
        while not self._stop.is_set():
            start = time.time()
            if not self._parent.is_alive():
                logger.info('Aborting daemon {}'.format(self._name))
                return
            try:
                self._tick.clear()
                self._target()
                self.sleep(self._get_sleep_interval(start))
                backoff = 0.0
            except DaemonThreadWait:
                logger.debug('Waiting {} seconds'.format(self._delay))
                self.sleep(self._get_delay())
            except Exception as ex:
                logger.exception('Unexpected error in daemon {}: {}'.format(self._name, ex))
                backoff += 1.0
                self.sleep(min(5.0, self._get_delay() * backoff))
        logger.info('Stopping daemon {}... Done'.format(self._name))
