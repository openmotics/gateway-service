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
from __future__ import absolute_import, print_function

import logging
import threading

logger = logging.getLogger("openmotics")

if False:  # MYPY
    from typing import Any, Callable


class DaemonThreadWait(Exception):
    pass


class DaemonThread(object):
    def __init__(self, name, target, interval=10, delay=None):
        # type: (str, Callable[[],Any], float, float) -> None
        self._interval = interval
        self._delay = delay or self._interval * 2
        self._name = name
        self._target = target
        self._tick = threading.Event()
        self._stop = threading.Event()
        self._parent = threading.current_thread()
        self._thread = threading.Thread(target=self._run, name=name)

    def start(self):
        # type: () -> None
        logger.debug('Starting daemon {}'.format(self._name))
        self._thread.start()

    def stop(self):
        # type: () -> None
        logger.info('Stopping daemon {}...'.format(self._name))
        self._stop.set()
        self._tick.set()
        self._thread.join(2)

    def sleep(self, timeout):
        # type: (float) -> None
        self._tick.wait(timeout)

    def set_interval(self, interval):
        # type: (float) -> None
        changed = self._interval != interval
        self._interval = interval
        if changed:
            self._tick.set()

    def _run(self):
        # type: () -> None
        backoff = 0
        while not self._stop.is_set():
            if not self._parent.is_alive():
                logger.info('Aborting daemon {}'.format(self._name))
                return
            try:
                logger.debug('Running {}'.format(self._name))
                self._target()
                self.sleep(self._interval)
                backoff = 0
            except DaemonThreadWait as ex:
                logger.debug('{}, waiting {} seconds'.format(ex, self._delay))
                self.sleep(self._delay)
            except Exception as ex:
                logger.exception('Unexpected error in daemon {}: {}'.format(self._name, ex))
                backoff += 1
                self.sleep(self._delay * backoff)
        logger.info('Stopping daemon {}... Done'.format(self._name))
