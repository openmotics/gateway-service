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
from select import select
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

    It uses netstring: <data_length>:<data>,\n
    * data_length: The length of `data`
    * data: The actual payload, using the format <encoding_type>:<encoded_data>
      * encoding_type: A one-character reference to the used encoding protocol
        * 1 = msgpack
      * encoded_data: The encoded data
    """

    def __init__(self, stream, logger, command_receiver=None):
        # type: (IO[bytes], Callable[[str,Exception],None], Callable[[Dict[str,Any]],None]) -> None
        self._buffer = ''
        self._command_queue = Queue()
        self._stream = stream
        self._read_thread = None  # type: Optional[Thread]
        self._logger = logger
        self._running = False
        self._command_receiver = command_receiver

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
        wait_for_length = None
        while self._running:
            try:
                if wait_for_length is None:
                    # Waiting for a new command to start. Let's do 1 second polls to make sure we're not blocking forever
                    # in case no new data will come
                    read_available, _, _ = select([self._stream], [], [], 1.0)
                    if not read_available:
                        continue
                # Minimum dataset: 0:x:,\n = 6 characters, so we always read at least 6 chars
                data = self._stream.read(6 if wait_for_length is None else wait_for_length)
                self._buffer += data
                if wait_for_length is None:
                    if ':' not in self._buffer:
                        # This is unexpected, discard data
                        self._buffer = ''
                        continue
                    length, self._buffer = self._buffer.split(':', 1)
                    # The length defines the encoded data length. We to add 4 because of the `<encoding_protocol>:` and `,\n`
                    wait_for_length = int(length) - len(self._buffer) + 2
                    if wait_for_length > 0:
                        continue
                if self._buffer.endswith(',\n'):
                    protocol, self._buffer = self._buffer.split(':', 1)
                    command = PluginIPCReader._decode(protocol, self._buffer[:-2])
                    if command is None:
                        # Unexpected protocol
                        self._buffer = ''
                        wait_for_length = None
                        continue
                    if self._command_receiver is not None:
                        self._command_receiver(command)
                    else:
                        self._command_queue.put(command)
                self._buffer = ''
                wait_for_length = None
            except Exception as ex:
                self._logger('Unexpected read exception', ex)

    def get(self, block=True, timeout=None):
        return self._command_queue.get(block, timeout)

    @staticmethod
    def write(data):
        encode_type = '1'
        data = PluginIPCReader._encode(encode_type, data)
        return '{0}:{1}:{2},\n'.format(len(data) + 2, encode_type, data)

    @staticmethod
    def _encode(encode_type, data):
        if encode_type == '1':
            return msgpack.dumps(data)
        return ''

    @staticmethod
    def _decode(encode_type, data):
        if data == '':
            return None
        if encode_type == '1':
            return msgpack.loads(data)
        return None


class PluginIPCWriter(object):
    def __init__(self, stream):
        # type: (IO[bytes]) -> None
        self._stream = stream

    def log(self, msg):
        # type: (str) -> None
        self.write({'cid': 0, 'action': 'logs', 'logs': str(msg)})

    def log_exception(self, name, exception):
        # type: (str, Exception) -> None
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
        self._stream.write(PluginIPCReader.write(response))
        self._stream.flush()


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
