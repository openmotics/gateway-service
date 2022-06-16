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
Tests for metrics.
"""
from __future__ import absolute_import

import copy
import logging
import time
import unittest
from threading import Lock

import requests
import ujson as json
from mock import Mock, patch
from sqlalchemy import create_engine, select
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

import fakesleep
from gateway.metrics_caching import MetricsCacheController
from gateway.metrics_collector import MetricsCollector
from gateway.metrics_controller import MetricsController
from gateway.models import Base, Config, Database, Input, Room
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs

from cloud.cloud_api_client import CloudAPIClient

logger = logging.getLogger('test')

MODELS = [Config]


class MetricsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(MetricsTest, cls).setUpClass()
        SetTestMode()
        # Logs.set_loglevel(logging.DEBUG, namespace='sqlalchemy.engine')

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=True, bind=engine)

        self.session = session_factory()
        session_mock = patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()
        self.addCleanup(session_mock.stop)

        fakesleep.monkey_patch()
        fakesleep.reset(seconds=0)

        self.definitions = [{'type': 'foobar',
                             'tags': ['id', 'name'],
                             'metrics': [{'name': 'counter',
                                          'description': 'Some field',
                                          'type': 'counter',
                                          'policies': ['buffer'],
                                          'unit': ''}]}]

        Config.set_entry('cloud_endpoint', 'tests.openmotics.com')
        Config.set_entry('cloud_endpoint_metrics', 'metrics')
        Config.set_entry('cloud_metrics_interval|foobar', 5)
        Config.set_entry('cloud_metrics_batch_size', 0)
        Config.set_entry('cloud_metrics_min_interval', 0)

        SetUpTestInjections(metrics_db=':memory:', metrics_db_lock=Lock())

        self.cloud_api_client = Mock(CloudAPIClient)

        self.metrics_collector = Mock(MetricsCollector)
        self.metrics_collector.intervals = {}
        self.metrics_collector.get_definitions.return_value = self.definitions

        self.metrics_cache_controller = MetricsCacheController()
        SetUpTestInjections(cloud_api_client=self.cloud_api_client,
                            metrics_cache_controller=self.metrics_cache_controller,
                            metrics_collector=self.metrics_collector,
                            plugin_controller=Mock())

        self.controller = MetricsController()

    def tearDown(self):
        fakesleep.monkey_restore()

    def test_set_cloud_interval(self):
        self.metrics_collector.intervals = {'energy': 300}
        self.controller._refresh_cloud_interval()
        self.metrics_collector.set_cloud_interval.assert_called_with('energy', 300)
        self.controller.set_cloud_interval('energy', 900)
        self.metrics_collector.set_cloud_interval.assert_called_with('energy', 900)
        self.assertEqual(Config.get_entry('cloud_metrics_interval|energy', 0), 900)

    def test_needs_upload(self):
        Config.set_entry('cloud_enabled', True)
        Config.set_entry('cloud_metrics_types', ['counter', 'energy'])
        Config.set_entry('cloud_metrics_sources', ['openmotics'])
        Config.set_entry('cloud_metrics_enabled|energy', True)

        definitions = {'OpenMotics': {'counter': Mock(), 'energy': Mock()}}
        self.controller.definitions = definitions

        # 2. test simple metric
        metric = {'source': 'OpenMotics',
                  'type': 'energy',
                  'timestamp': 1234,
                  'tags': {'device': 'OpenMotics energy ID1', 'id': 'E7.3'},
                  'values': {'counter': 5678, 'power': 9012}}

        needs_upload = self.controller._needs_upload_to_cloud(metric)
        self.assertTrue(needs_upload)

        # 3. disable energy metric type, now test again
        Config.set_entry('cloud_metrics_enabled|energy', False)
        needs_upload = self.controller._needs_upload_to_cloud(metric)
        self.assertFalse(needs_upload)
        Config.set_entry('cloud_metrics_enabled|energy', True)

        # 3. disable energy metric type, now test again
        Config.set_entry('cloud_metrics_types', ['counter'])
        needs_upload = self.controller._needs_upload_to_cloud(metric)
        self.assertFalse(needs_upload)
        Config.set_entry('cloud_metrics_types', ['counter', 'energy'])

        # 4. test metric with unconfigured definition
        metric = {'source': 'MBus',
                  'type': 'energy',
                  'timestamp': 1234,
                  'tags': {'device': 'OpenMotics energy ID1', 'id': 'E7.3'},
                  'values': {'counter': 5678, 'power': 9012}}

        needs_upload = self.controller._needs_upload_to_cloud(metric)
        self.assertFalse(needs_upload)

        # 5. configure definition, now test again
        definitions['MBus'] = {'counter': Mock(), 'energy': Mock()}
        needs_upload = self.controller._needs_upload_to_cloud(metric)
        self.assertFalse(needs_upload)

        # 5. configure source, now test again
        cnf = Config.get_entry('cloud_metrics_sources', [])
        cnf.append('mbus')
        Config.set_entry('cloud_metrics_sources', cnf)
        needs_upload = self.controller._needs_upload_to_cloud(metric)
        self.assertTrue(needs_upload)

        # 7. disable cloud, now test again
        Config.set_entry('cloud_enabled', False)
        needs_upload = self.controller._needs_upload_to_cloud(metric)
        self.assertFalse(needs_upload)

    def test_startup(self):
        self.controller._needs_upload_to_cloud = lambda *args, **kwargs: True
        self.assertEqual(self.controller._buffer_counters, {'OpenMotics': {'foobar': {'counter': True}}})

        # Validate initial state
        self.assert_fields(cache={},
                           queue=[],
                           stats={'queue': 0, 'buffer': 0, 'time_ago_send': 0, 'time_ago_try': 0},
                           buffer=[],
                           last_send=0,
                           last_try=0,
                           retry_interval=None)

    def test_send_retry(self):
        self.controller._needs_upload_to_cloud = lambda *args, **kwargs: True
        self.cloud_api_client.send_metrics.side_effect = Exception('Cloud error')

        time.sleep(10)
        metric_1 = self._send_metric(counter=0)

        self.cloud_api_client.send_metrics.assert_called_with([
            [{'source': 'OpenMotics',
              'type': 'foobar',
              'timestamp': 10,
              'tags': {'name': 'name', 'id': 0},
              'values': {'counter': 0}}]
        ])

        self.assert_fields(cache={'OpenMotics': {'foobar': {'id=0|name=name': {'timestamp': 10}}}},
                           queue=[[metric_1]],
                           stats={'queue': 1, 'buffer': 0, 'time_ago_send': 10, 'time_ago_try': 10},  # Nothing buffered yet
                           buffer=[],
                           last_send=0,
                           last_try=10,
                           retry_interval=0)
        buffered_metrics = self._load_buffered_metrics()
        self.assertEqual(buffered_metrics, [{'timestamp': 10, 'counter': 0}])

        time.sleep(10)
        metric_2 = self._send_metric(counter=1)

        self.cloud_api_client.send_metrics.assert_called_with([
            [{'source': 'OpenMotics',
              'type': 'foobar',
              'timestamp': 10,
              'tags': {'name': 'name', 'id': 0},
              'values': {'counter': 0}}],
            [{'source': 'OpenMotics',
              'type': 'foobar',
              'timestamp': 20,
              'tags': {'name': 'name', 'id': 0},
              'values': {'counter': 1}}]
        ])

        self.assert_fields(cache={'OpenMotics': {'foobar': {'id=0|name=name': {'timestamp': 20}}}},
                           queue=[[metric_1], [metric_2]],
                           stats={'queue': 2, 'buffer': 1, 'time_ago_send': 20, 'time_ago_try': 10},
                           buffer=[],
                           last_send=0,
                           last_try=20,
                           retry_interval=0)
        buffered_metrics = self._load_buffered_metrics()
        self.assertEqual(buffered_metrics, [{'timestamp': 10, 'counter': 0}])

    def test_offline_buffer(self):
        self.controller._needs_upload_to_cloud = lambda *args, **kwargs: True
        self.cloud_api_client.send_metrics.side_effect = Exception('Cloud error')

        time.sleep(10)
        metric_1 = self._send_metric(counter=0)
        time.sleep(10)
        metric_2 = self._send_metric(counter=1)

        self.cloud_api_client.send_metrics.side_effect = None

        time.sleep(10)
        metric_3 = self._send_metric(counter=8)

        self.cloud_api_client.send_metrics.assert_called_with([
            [{'source': 'OpenMotics',
              'type': 'foobar',
              'timestamp': 10,
              'tags': {'name': 'name', 'id': 0},
              'values': {'counter': 0}}],
            [{'source': 'OpenMotics',
              'type': 'foobar',
              'timestamp': 20,
              'tags': {'name': 'name', 'id': 0},
              'values': {'counter': 1}}],
            [{'source': 'OpenMotics',
              'type': 'foobar',
              'timestamp': 30,
              'tags': {'name': 'name', 'id': 0},
              'values': {'counter': 8}}]
        ])

        self.assert_fields(cache={'OpenMotics': {'foobar': {'id=0|name=name': {'timestamp': 30}}}},
                           queue=[],  # empty
                           stats={'queue': 3, 'buffer': 1, 'time_ago_send': 30, 'time_ago_try': 10},
                           buffer=[],
                           last_send=30,
                           last_try=30,
                           retry_interval=0)
        buffered_metrics = self._load_buffered_metrics()
        self.assertEqual(buffered_metrics, [])

        time.sleep(30)
        metric_4 = self._send_metric(counter=9)

        self.cloud_api_client.send_metrics.assert_called_with([
            [{'source': 'OpenMotics',
              'type': 'foobar',
              'timestamp': 60,
              'tags': {'name': 'name', 'id': 0},
              'values': {'counter': 9}}]
        ])

        self.assert_fields(cache={'OpenMotics': {'foobar': {'id=0|name=name': {'timestamp': 60}}}},
                           queue=[],
                           stats={'queue': 1, 'buffer': 0, 'time_ago_send': 30, 'time_ago_try': 30},
                           buffer=[],
                           last_send=60,
                           last_try=60,
                           retry_interval=0)
        buffered_metrics = self._load_buffered_metrics()
        self.assertEqual(buffered_metrics, [])


    def test_send_batch(self):
        Config.set_entry('cloud_metrics_batch_size', 2)
        Config.set_entry('cloud_metrics_min_interval', 300)

        self.controller._needs_upload_to_cloud = lambda *args, **kwargs: True

        time.sleep(10)
        metric_1 = self._send_metric(counter=1)
        time.sleep(1)
        self._send_metric(counter=2)  # This metric has the same (rounded) timestamp, so should be discarded

        self.cloud_api_client.send_metrics.assert_not_called()  # queue == 1

        time.sleep(9)
        metric_2 = self._send_metric(counter=8)

        self.cloud_api_client.send_metrics.assert_called_with([
            [{'source': 'OpenMotics',
              'type': 'foobar',
              'timestamp': 10,
              'tags': {'name': 'name', 'id': 0},
              'values': {'counter': 1}}],
            [{'source': 'OpenMotics',
              'type': 'foobar',
              'timestamp': 20,
              'tags': {'name': 'name', 'id': 0},
              'values': {'counter': 8}}]
        ])

        self.assert_fields(cache={'OpenMotics': {'foobar': {'id=0|name=name': {'timestamp': 20}}}},
                           queue=[],
                           stats={'queue': 2, 'buffer': 0, 'time_ago_send': 20, 'time_ago_try': 20},
                           buffer=[],
                           last_send=20,
                           last_try=20,
                           retry_interval=300)
        buffered_metrics = self._load_buffered_metrics()
        self.assertEqual(buffered_metrics, [])

    def test_metrics_cache(self):
        tags = {'name': 'name', 'id': 0}

        expected_metrics = []
        for i in range(10):
            timestamp = 300 + 60 * 60 * 12 * i  # Metric every 12 hours
            self.metrics_cache_controller.buffer_counter('OpenMotics', 'foobar', tags, {'counter': i}, timestamp)
            if not (i % 2):
                # Only one metric every day is expected to be buffered
                expected_metrics.append({'counter': i, 'timestamp': timestamp})

        buffered_metrics = self._load_buffered_metrics()
        self.assertEqual(5, len(buffered_metrics))
        self.assertEqual(expected_metrics, buffered_metrics)

        removed = self.metrics_cache_controller.clear_buffer(60 * 60 * 24 * 2)
        self.assertEqual(2, removed)
        buffered_metrics = self._load_buffered_metrics()
        self.assertEqual(3, len(buffered_metrics))
        self.assertEqual(expected_metrics[2:], buffered_metrics)

    def assert_fields(self, cache, queue, stats, buffer, last_send, last_try, retry_interval):
        self.assertDictEqual(self.controller._cloud_cache, cache)
        self.assertListEqual(self.controller._cloud_queue, queue)
        self.assertDictEqual(self.controller.cloud_stats, stats)
        self.assertListEqual(self.controller._cloud_buffer, buffer)
        self.assertEqual(self.controller._cloud_last_send, last_send)
        self.assertEqual(self.controller._cloud_last_try, last_try)
        self.assertEqual(self.controller._cloud_retry_interval, retry_interval)

    def _send_metric(self, **kwargs):
        metric = {'source': 'OpenMotics',
                  'type': 'foobar',
                  'tags': {'name': 'name', 'id': 0},
                  'values': {}}
        metric['timestamp'] = time.time()
        metric['values'].update(kwargs)
        self.controller.receiver(metric)
        return metric

    def _load_buffered_metrics(self):
        buffered_metrics = []
        buffer_items = self.metrics_cache_controller._execute_unlocked("SELECT counters, timestamp FROM counters_buffer INNER JOIN counter_sources ON counter_sources.id = counters_buffer.source_id;")
        for item in buffer_items:
            buffered_metrics.append({'counter': json.loads(item[0])['counter'], 'timestamp': item[1]})
        return buffered_metrics
