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
A few helper classes
"""

from __future__ import absolute_import

import inspect
import logging
import time
import traceback
from collections import deque
from threading import Thread

import msgpack
import six

logger = logging.getLogger('openmotics')

if False:  # MYPY
    from typing import Any, Callable, Dict, IO, List, Optional


class Full(Exception):
    pass


class Empty(Exception):
    pass


class Queue(object):
    def __init__(self, size=None):
        self._queue = deque()  # type: deque
        self._size = size  # Not used

    def put(self, value, block=False):
        _ = block
        self._queue.appendleft(value)

    def get(self, block=True, timeout=None):
        if not block:
            try:
                return self._queue.pop()
            except IndexError:
                raise Empty()
        start = time.time()
        while timeout is None or time.time() - start < timeout:
            try:
                return self._queue.pop()
            except IndexError:
                sleep = 0.025
                if timeout is None or timeout > 1:
                    sleep = 0.1
                time.sleep(sleep)
        raise Empty()

    def qsize(self):
        return len(self._queue)

    def clear(self):
        return self._queue.clear()


class PluginIPCReader(object):
    """
    This class handles IPC communications.

    It uses a stream of msgpack encoded dict values.
    """

    def __init__(self, stream, logger, command_receiver=None, name=None):
        # type: (IO[bytes], Callable[[str,Exception],None], Callable[[Dict[str,Any]],None],Optional[str]) -> None
        self._command_queue = Queue()
        self._unpacker = msgpack.Unpacker(stream, read_size=1, raw=False)  # type: msgpack.Unpacker[Dict[str,Any]]
        self._read_thread = None  # type: Optional[Thread]
        self._logger = logger
        self._running = False
        self._command_receiver = command_receiver
        self._name = name

    def start(self):
        # type: () -> None
        self._running = True
        self._read_thread = Thread(target=self._read)
        self._read_thread.daemon = True
        self._read_thread.start()

    def stop(self):
        # type: () -> None
        self._running = False
        if self._read_thread is not None:
            self._read_thread.join()

    def _read(self):
        # type: () -> None
        while self._running:
            try:
                command = next(self._unpacker)
                if not isinstance(command, dict):
                    raise ValueError('invalid value %s' % command)
                if self._command_receiver is not None:
                    self._command_receiver(command)
                else:
                    self._command_queue.put(command)
            except StopIteration as ex:
                self._logger('PluginIPCReader %s stopped' % self._name, ex)
                self._running = False
            except Exception as ex:
                self._logger('Unexpected read exception', ex)

    def get(self, block=True, timeout=None):
        return self._command_queue.get(block, timeout)


class PluginIPCWriter(object):
    def __init__(self, stream):
        # type: (IO[bytes]) -> None
        self._packer = msgpack.Packer()  # type: msgpack.Packer[Dict[str,Any]]
        self._stream = stream

    def log(self, msg):
        # type: (str) -> None
        self.write({'cid': 0, 'action': 'logs', 'logs': str(msg)})

    def log_exception(self, name, exception):
        # type: (str, BaseException) -> None
        self.log('Exception ({0}) in {1}: {2}'.format(exception, name, traceback.format_exc()))

    def with_catch(self, name, target, args):
        # type: (str, Callable[...,None], List[Any]) -> None
        """ Logs Exceptions that happen in target(*args). """
        try:
            return target(*args)
        except Exception as exception:
            self.log_exception(name, exception)

    def write(self, response):
        # type: (Dict[str,Any]) -> None
        try:
            self._stream.write(self._packer.pack(response))
            self._stream.flush()
        except IOError:
            pass  # Ignore exceptions if the stream is not available (nothing that can be done anyway)


class Toolbox(object):
    @staticmethod
    def nonify(value, default_value):
        return None if value == default_value else value

    @staticmethod
    def denonify(value, default_value):
        return default_value if value is None else value

    @staticmethod
    def get_parameter_names(func):
        if six.PY2:
            return inspect.getargspec(func).args
        return list(inspect.signature(func).parameters.keys())

    @staticmethod
    def shorten_name(name, maxlength=16):
        if len(name) <= maxlength:
            return name
        return '{0}~{1}'.format(name[:maxlength - 2], name[-1:])
