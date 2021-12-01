# Copyright (C) 2018 OpenMotics BV
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
Metrics caching/buffer controller
"""

from __future__ import absolute_import
import time
import sqlite3
import logging
import ujson as json
from random import randint
from ioc import Injectable, Inject, INJECTED, Singleton

logger = logging.getLogger(__name__)


@Injectable.named('metrics_cache_controller')
@Singleton
class MetricsCacheController(object):

    @Inject
    def __init__(self, metrics_db=INJECTED, metrics_db_lock=INJECTED):
        """
        Constructs a new MetricsCacheController.

        :param metrics_db: filename of the sqlite database used to store the cache/buffer
        :param metrics_db_lock: DB lock
        """
        self._lock = metrics_db_lock
        self._connection = sqlite3.connect(metrics_db,
                                           detect_types=sqlite3.PARSE_DECLTYPES,
                                           check_same_thread=False,
                                           isolation_level=None)
        self._cursor = self._connection.cursor()
        self._check_tables()

    def _execute(self, *args, **kwargs):
        with self._lock:
            return self._execute_unlocked(*args, **kwargs)

    def _execute_unlocked(self, *args, **kwargs):
        try:
            # the reason for the type ignore:
            # https://stackoverflow.com/questions/47493293/why-does-mypy-say-i-have-too-many-arguments
            # https://github.com/python/mypy/issues/4290
            # TL;DR: __init__ is defined after the execute function here, seems to be a bug in mypy...
            return self._cursor.execute(*args, **kwargs)  # type: ignore
        except sqlite3.OperationalError:
            time.sleep(randint(1, 20) / 10.0)
            return self._cursor.execute(*args, **kwargs)  # type: ignore

    def _check_tables(self):
        """
        Creates tables and execute migrations
        """
        self._execute("CREATE TABLE IF NOT EXISTS counter_sources (id INTEGER PRIMARY KEY, source TEXT, type TEXT, identifier TEXT);")
        self._execute("CREATE TABLE IF NOT EXISTS counters (id INTEGER PRIMARY KEY, source_id INTEGER , name TEXT, last_value REAL, counter REAL, timestamp INTEGER);")
        self._execute("CREATE TABLE IF NOT EXISTS counters_buffer (id INTEGER PRIMARY KEY, source_id INTEGER, counters TEXT, timestamp INTEGER);")

    def process_counter(self, source, mtype, tags, name, value, timestamp):
        with self._lock:
            identifier = json.dumps(tags, sort_keys=True)
            id = self._get_counter_id(source, mtype, identifier)
            data = self._execute_unlocked("SELECT last_value, counter FROM counters WHERE source_id=? AND name=?;", (id, name))
            for entry in data:
                last_value, counter = entry
                if last_value == value:
                    return counter
                if last_value < value:
                    counter += (value - last_value)
                else:
                    counter += value
                self._execute_unlocked("UPDATE counters SET last_value=?, counter=?, timestamp=? WHERE source_id=? AND name=?;", (value, counter, timestamp, id, name))
                return counter
            self._execute_unlocked("INSERT INTO counters (source_id, name, last_value, counter, timestamp) VALUES (?, ?, ?, ?, ?);", (id, name, value, value, timestamp))
            return value

    def buffer_counter(self, source, mtype, tags, counters, timestamp):
        with self._lock:
            identifier = json.dumps(tags, sort_keys=True)
            id = self._get_counter_id(source, mtype, identifier)
            data = self._execute_unlocked("SELECT timestamp FROM counters_buffer WHERE source_id=? ORDER BY timestamp DESC LIMIT 1;", (id,)).fetchone()
            if data is None or MetricsCacheController._floored_timestamp(data[0]) < MetricsCacheController._floored_timestamp(timestamp):
                self._execute_unlocked("INSERT INTO counters_buffer (source_id, counters, timestamp) VALUES (?, ?, ?);", (id, json.dumps(counters), timestamp))
                return True
            return False

    @staticmethod
    def _floored_timestamp(timestamp, window=60 * 60 * 24):
        return int(timestamp) - (int(timestamp) % window)

    def load_buffer(self, before):
        with self._lock:
            buffer_items = self._execute_unlocked("SELECT source, type, identifier, counters, timestamp FROM counters_buffer INNER JOIN counter_sources ON counter_sources.id = counters_buffer.source_id;")
        for item in buffer_items:
            if before == -1 or before > item[4]:
                yield {'source': item[0],
                       'type': item[1],
                       'tags': json.loads(item[2]),
                       'values': json.loads(item[3]),
                       'timestamp': item[4]}

    def clear_buffer(self, timestamp):
        with self._lock:
            self._execute_unlocked("DELETE FROM counters_buffer WHERE timestamp < ?;", (timestamp,))
            return self._execute_unlocked("SELECT changes();").fetchone()[0]

    def _get_counter_id(self, source, mtype, identifier):
        data = self._execute_unlocked("SELECT id FROM counter_sources WHERE source=? AND type=? AND identifier=?;", (source, mtype, identifier)).fetchone()
        if data is not None:
            return data[0]
        result = self._execute_unlocked("INSERT INTO counter_sources (source, type, identifier) VALUES (?, ?, ?);", (source, mtype, identifier))
        return result.lastrowid

    def close(self):
        """ Close the database connection. """
        self._connection.close()
