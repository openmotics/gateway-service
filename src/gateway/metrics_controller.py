# Copyright (C) 2016 OpenMotics BV
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
The metrics module collects and re-distributes metric data
"""

from __future__ import absolute_import

import logging
import re
import time
from collections import deque

import six

from bus.om_bus_events import OMBusEvents
from gateway.daemon_thread import DaemonThread, DaemonThreadWait
from gateway.models import Config
from ioc import INJECTED, Inject, Injectable, Singleton
from platform_utils import System

if False:  # MYPY
    from typing import Any, Dict, Optional, List
    from cloud.cloud_api_client import CloudAPIClient
    from gateway.config_controller import ConfigurationController
    from gateway.metrics_caching import MetricsCacheController
    from gateway.metrics_collector import MetricsCollector
    from plugins.base import PluginController

logger = logging.getLogger(__name__)


class MetricsDistributeFailed(Exception):
    pass


@Injectable.named('metrics_controller')
@Singleton
class MetricsController(object):
    """
    The Metrics Controller collects all metrics and pushses them to all subscribers
    """

    @Inject
    def __init__(self, cloud_api_client=INJECTED, plugin_controller=INJECTED, metrics_collector=INJECTED, metrics_cache_controller=INJECTED):
        # type: (CloudAPIClient, PluginController, MetricsCollector, MetricsCacheController) -> None
        self._cloud_api_client = cloud_api_client
        self._plugin_controller = plugin_controller
        self._metrics_collector = metrics_collector
        self._metrics_cache_controller = metrics_cache_controller
        self._persist_counters = {}  # type: Dict
        self._buffer_counters = {}  # type: Dict
        self.definitions = {}  # type: Dict
        self._definition_filters = {'source': {}, 'metric_type': {}}  # type: Dict
        self._metrics_cache = {}  # type: Dict
        self._collector_plugins = None  # type: Optional[DaemonThread]
        self._collector_openmotics = None  # type: Optional[DaemonThread]
        self._internal_stats = None
        self._distributor_plugins = None  # type: Optional[DaemonThread]
        self._distributor_openmotics = None  # type: Optional[DaemonThread]
        self.metrics_queue_plugins = deque()  # type: deque
        self.metrics_queue_openmotics = deque()  # type: deque
        self.inbound_rates = {'total': 0}
        self.outbound_rates = {'total': 0}
        self._openmotics_receivers = []  # type: List
        self._cloud_cache = {}  # type: Dict
        self._cloud_queue = []  # type: List
        self._cloud_buffer = []  # type: List
        self._cloud_buffer_length = 0
        self._load_cloud_buffer()
        self._cloud_last_send = time.time()
        self._cloud_last_try = time.time()
        self._cloud_retry_interval = None  # type: Optional[int]
        self._throttled_down = False
        self.cloud_stats = {'queue': 0,
                            'buffer': self._cloud_buffer_length,
                            'time_ago_send': 0,
                            'time_ago_try': 0}

        # Metrics generated by the Metrics_Controller_ are also defined in the collector. Trying to get them in one place.
        for definition in self._metrics_collector.get_definitions():
            self.definitions.setdefault('OpenMotics', {})[definition['type']] = definition
            settings = MetricsController._parse_definition(definition)
            self._persist_counters.setdefault('OpenMotics', {})[definition['type']] = settings['persist']
            self._buffer_counters.setdefault('OpenMotics', {})[definition['type']] = settings['buffer']

    def start(self):
        self._refresh_cloud_interval()
        self._collector_plugins = DaemonThread(name='metricplugincoll',
                                               target=self._collect_plugins,
                                               interval=1)
        self._collector_plugins.start()
        self._collector_openmotics = DaemonThread(name='metricplugindist',
                                                  target=self._collect_openmotics,
                                                  interval=1)
        self._collector_openmotics.start()
        self._distributor_plugins = DaemonThread(name='metricplugindist',
                                                 target=self._distribute_plugins,
                                                 interval=0, delay=0.1)
        self._distributor_plugins.start()
        self._distributor_openmotics = DaemonThread(name='metricomdist',
                                                    target=self._distribute_openmotics,
                                                    interval=0, delay=0.1)
        self._distributor_openmotics.start()

    def stop(self):
        # type: () -> None
        if self._collector_plugins is not None:
            self._collector_plugins.stop()
        if self._collector_openmotics is not None:
            self._collector_openmotics.stop()
        if self._distributor_plugins is not None:
            self._distributor_plugins.stop()
        if self._distributor_openmotics is not None:
            self._distributor_openmotics.stop()

    def set_cloud_interval(self, metric_type, interval, save=True):
        logger.info('Setting cloud interval {0}_{1}'.format(metric_type, interval))
        self._metrics_collector.set_cloud_interval(metric_type, interval)
        if save:
            Config.set_entry('cloud_metrics_interval|{0}'.format(metric_type), interval)

    def _refresh_cloud_interval(self):
        for metric_type in self._metrics_collector.intervals:
            interval = Config.get_entry('cloud_metrics_interval|{0}'.format(metric_type), 300)
            self.set_cloud_interval(metric_type, interval, save=False)
        self._throttled_down = False

    def add_receiver(self, receiver):
        self._openmotics_receivers.append(receiver)

    def get_filter(self, filter_type, metric_filter):
        if metric_filter in self._definition_filters[filter_type]:
            return self._definition_filters[filter_type][metric_filter]
        if filter_type == 'source':
            results = []
            re_filter = None if metric_filter is None else re.compile(metric_filter)
            for source in self.definitions.keys():
                if re_filter is None or re_filter.match(source):
                    results.append(source)
            results = set(results)
            self._definition_filters['source'][metric_filter] = results
            return results
        if filter_type == 'metric_type':
            results = []
            re_filter = None if metric_filter is None else re.compile(metric_filter)
            for source in self.definitions.keys():
                for metric_type in self.definitions.get(source, []):
                    if re_filter is None or re_filter.match(metric_type):
                        results.append(metric_type)
            results = set(results)
            self._definition_filters['metric_type'][metric_filter] = results
            return results

    def set_plugin_definitions(self, definitions):
        # {
        #     "type": "energy",
        #     "tags": ["device", "id"],
        #     "metrics": [{"name": "power",
        #                  "description": "Total energy consumed (in kWh)",
        #                  "type": "counter",
        #                  "unit": "kWh"}]
        # }
        required_keys = {'type': six.string_types,
                         'metrics': list,
                         'tags': list}
        metrics_keys = {'name': six.string_types,
                        'description': six.string_types,
                        'type': six.string_types,
                        'unit': six.string_types}
        expected_plugins = []
        for plugin, plugin_definitions in six.iteritems(definitions):
            log = self._plugin_controller.get_logger(plugin)
            for definition in plugin_definitions:
                definition_ok = True
                for key, key_type in required_keys.items():
                    if key not in definition:
                        log('Definitions should contain keys: {0}'.format(', '.join(list(required_keys.keys()))))
                        definition_ok = False
                        break
                    if not isinstance(definition[key], key_type):
                        log('Definitions key {0} should be of type {1}'.format(key, key_type))
                        definition_ok = False
                        break
                    if key == 'metrics':
                        for metric_definition in definition[key]:
                            if definition_ok is False:
                                break
                            if not isinstance(metric_definition, dict):
                                log('Metric definitions should be dictionaries')
                                definition_ok = False
                                break
                            for mkey, mkey_type in metrics_keys.items():
                                if mkey not in metric_definition:
                                    log('Metric definitions should contain keys: {0}'.format(', '.join(list(metrics_keys.keys()))))
                                    definition_ok = False
                                    break
                                if not isinstance(metric_definition[mkey], mkey_type):
                                    log('Metric definitions key {0} should be of type {1}'.format(mkey, mkey_type))
                                    definition_ok = False
                                    break
                    if definition_ok is False:
                        break
                if definition_ok is True:
                    expected_plugins.append(plugin)
                    self.definitions.setdefault(plugin, {})[definition['type']] = definition
                    settings = MetricsController._parse_definition(definition)
                    self._persist_counters.setdefault(plugin, {})[definition['type']] = settings['persist']
                    self._buffer_counters.setdefault(plugin, {})[definition['type']] = settings['buffer']
        for source in self.definitions.keys():
            # Remove plugins from the self.definitions dict that are not found anymore
            if source != 'OpenMotics' and source not in expected_plugins:
                self.definitions.pop(source, None)
                self._persist_counters.pop(source, None)
                self._buffer_counters.pop(source, None)
        self._definition_filters['source'] = {}
        self._definition_filters['metric_type'] = {}

    def _load_cloud_buffer(self):
        oldest_queue_timestamp = min([time.time()] + [metric[0]['timestamp'] for metric in self._cloud_queue])
        self._cloud_buffer = [[metric] for metric in self._metrics_cache_controller.load_buffer(before=oldest_queue_timestamp)]
        self._cloud_buffer_length = len(self._cloud_buffer)

    @staticmethod
    def _parse_definition(definition):
        settings = {'persist': {},
                    'buffer': {}}
        for metric in definition['metrics']:
            if metric['type'] == 'counter':
                for policy in metric.get('policies', []):
                    setting = True
                    if isinstance(policy, dict):
                        setting = {'key': policy['key'],
                                   'matches': policy['matches']}
                        policy = policy['policy']

                    # Backwards compatibility
                    if policy == 'buffered':
                        policy = 'buffer'
                    if policy == 'persistent':
                        policy = 'persist'

                    settings[policy][metric['name']] = setting
        return settings

    def _needs_upload_to_cloud(self, metric):
        metric_type = metric['type']
        metric_source = metric['source']

        # get definition for metric source and type, getting the definitions for a metric_source is case sensitive!
        definition = self.definitions.get(metric_source, {}).get(metric_type)
        if definition is None:
            return False

        if Config.get_entry('cloud_enabled', False) is False:
            return False

        if metric_source == 'OpenMotics':
            config_key = 'cloud_metrics_enabled|{0}'.format(metric_type)
            if Config.get_entry(config_key, True) is False:
                return False

            # filter openmotics metrics that are not listed in cloud_metrics_types
            metric_types = Config.get_entry('cloud_metrics_types', [])
            if metric_type not in metric_types:
                return False

        else:
            # filter 3rd party (plugin) metrics that are not listed in cloud_metrics_sources
            metric_sources = Config.get_entry('cloud_metrics_sources', [])
            # make sure to get the lowercase metric_source
            if metric_source.lower() not in metric_sources:
                return False

        return True

    def receiver(self, metric):
        # type: (Dict[str,Any]) -> None
        """
        Collects all metrics made available by the MetricsCollector and the plugins. These metrics
        are cached locally for configurable (and optional) pushing metrics to the Cloud.
        > example_definition = {"type": "energy",
        >                       "tags": ["device", "id"],
        >                       "metrics": [{"name": "power",
        >                                    "description": "Total energy consumed (in kWh)",
        >                                    "type": "counter",
        >                                    "unit": "kWh"}]}
        > example_metric = {"source": "OpenMotics",
        >                   "type": "energy",
        >                   "timestamp": 1497677091,
        >                   "tags": {"device": "OpenMotics energy ID1",
        >                            "id": "E7.3"},
        >                   "values": {"power": 1234}}
        """
        metric_type = metric['type']
        metric_source = metric['source']

        if not self._needs_upload_to_cloud(metric):
            return

        if metric_source == 'OpenMotics':
            # round off timestamps for openmotics metrics
            modulo_interval = Config.get_entry('cloud_metrics_interval|{0}'.format(metric_type), 900)
            timestamp = int(metric['timestamp'] - metric['timestamp'] % modulo_interval)
        else:
            timestamp = int(metric['timestamp'])

        cloud_batch_size = Config.get_entry('cloud_metrics_batch_size', 0)
        cloud_min_interval = Config.get_entry('cloud_metrics_min_interval', None)  # type: Optional[int]
        if cloud_min_interval is not None:
            self._cloud_retry_interval = cloud_min_interval

        counters_to_buffer = self._buffer_counters.get(metric_source, {}).get(metric_type, {})
        definition = self.definitions.get(metric_source, {}).get(metric_type)
        identifier = '|'.join(['{0}={1}'.format(tag, metric['tags'][tag]) for tag in sorted(definition['tags'])])

        # Check if the metric needs to be send
        entry = self._cloud_cache.setdefault(metric_source, {}).setdefault(metric_type, {}).setdefault(identifier, {})
        include_this_metric = False
        if 'timestamp' not in entry:
            include_this_metric = True
        else:
            old_timestamp = entry['timestamp']
            if old_timestamp < timestamp:
                include_this_metric = True

        # Add metrics to the send queue if they need to be send
        if include_this_metric is True:
            entry['timestamp'] = timestamp
            self._cloud_queue.append([metric])
            self._cloud_queue = self._cloud_queue[-5000:]  # 5k metrics buffer

        # Check timings/rates
        now = time.time()
        time_ago_send = int(now - self._cloud_last_send)
        time_ago_try = int(now - self._cloud_last_try)
        outstanding_data_length = len(self._cloud_buffer) + len(self._cloud_queue)

        send = False
        if outstanding_data_length > 0:  # There must be outstanding data
            # Last send was successful, but the buffer length > batch size
            send |= outstanding_data_length >= cloud_batch_size and time_ago_send == time_ago_try
            if cloud_min_interval is not None:
                # Last send was successful, but it has been too long ago
                send |= time_ago_send > cloud_min_interval and time_ago_send == time_ago_try
            if self._cloud_retry_interval is not None:
                # Last send was unsuccessful, and it has been a while
                send |= time_ago_send > time_ago_try > self._cloud_retry_interval

        self.cloud_stats['queue'] = len(self._cloud_queue)
        self.cloud_stats['buffer'] = self._cloud_buffer_length
        self.cloud_stats['time_ago_send'] = time_ago_send
        self.cloud_stats['time_ago_try'] = time_ago_try

        if send is True:
            self._cloud_last_try = now
            try:
                # Try to send the metrics
                self._cloud_api_client.send_metrics(self._cloud_buffer + self._cloud_queue)
                # If successful; clear buffers
                if self._metrics_cache_controller.clear_buffer(metric['timestamp']) > 0:
                    self._load_cloud_buffer()
                self._cloud_queue = []
                self._cloud_last_send = now
                self._cloud_retry_interval = cloud_min_interval
                if self._throttled_down:
                    self._refresh_cloud_interval()
            except Exception as ex:
                logger.exception('Error uploading metrics to cloud: {0}'.format(ex))
                if time_ago_send > 60 * 60:
                    # Decrease metrics rate, but at least every 2 hours
                    # Decrease cloud try interval, but at least every hour
                    if time_ago_send < 6 * 60 * 60:
                        self._cloud_retry_interval = 15 * 60
                        new_interval = 30 * 60
                    elif time_ago_send < 24 * 60 * 60:
                        self._cloud_retry_interval = 30 * 60
                        new_interval = 60 * 60
                    else:
                        self._cloud_retry_interval = 60 * 60
                        new_interval = 2 * 60 * 60
                    self._throttled_down = True
                    metric_types = Config.get_entry('cloud_metrics_types', [])  # type: List[str]
                    for mtype in metric_types:
                        self.set_cloud_interval(mtype, new_interval, save=False)

        # Buffer metrics if appropriate
        time_ago_send = int(now - self._cloud_last_send)
        time_ago_try = int(now - self._cloud_last_try)
        if time_ago_send > time_ago_try and include_this_metric is True and len(counters_to_buffer) > 0:
            cache_data = {}
            for counter, match_setting in six.iteritems(counters_to_buffer):
                if match_setting is not True:
                    if metric['tags'][match_setting['key']] not in match_setting['matches']:
                        continue
                cache_data[counter] = metric['values'][counter]
            if self._metrics_cache_controller.buffer_counter(metric_source, metric_type, metric['tags'], cache_data, metric['timestamp']):
                self._cloud_buffer_length += 1
            if self._metrics_cache_controller.clear_buffer(time.time() - 365 * 24 * 60 * 60) > 0:
                self._load_cloud_buffer()

    def _put(self, metric):
        rate_key = '{0}.{1}'.format(metric['source'].lower(), metric['type'].lower())
        if rate_key not in self.inbound_rates:
            self.inbound_rates[rate_key] = 0
        self.inbound_rates[rate_key] += 1
        self.inbound_rates['total'] += 1
        self._transform_counters(metric)  # Convert counters to "ever increasing counters"
        # No need to make a deep copy; openmotics doesn't alter the object, and for the plugins the metric gets (de)serialized
        self.metrics_queue_plugins.appendleft(metric)
        self.metrics_queue_openmotics.appendleft(metric)

    def _transform_counters(self, metric):
        # TODO: The 'persist' policy should be a part of the PulseCounterController

        source = metric['source']
        mtype = metric['type']
        for counter, match_setting in six.iteritems(self._persist_counters.get(source, {}).get(mtype, {})):
            if counter not in metric['values']:
                continue
            if match_setting is not True:
                if metric['tags'][match_setting['key']] not in match_setting['matches']:
                    continue
            counter_type = type(metric['values'][counter])
            counter_value = self._metrics_cache_controller.process_counter(source=source,
                                                                           mtype=mtype,
                                                                           tags=metric['tags'],
                                                                           name=counter,
                                                                           value=metric['values'][counter],
                                                                           timestamp=metric['timestamp'])
            metric['values'][counter] = counter_type(counter_value)

    def _collect_plugins(self):
        """
        > example_definition = {"type": "energy",
        >                       "tags": ["device", "id"],
        >                       "metrics": [{"name": "power",
        >                                    "description": "Total energy consumed (in kWh)",
        >                                    "type": "counter",
        >                                    "unit": "kWh"}]}
        > example_metric = {"source": "OpenMotics",
        >                   "type": "energy",
        >                   "timestamp": 1497677091,
        >                   "tags": {"device": "OpenMotics energy ID1",
        >                            "id": 0},
        >                   "values": {"power": 1234}}
        """
        start = time.time()
        for metric in self._plugin_controller.collect_metrics():
            # Validation, part 1
            source = metric['source']
            log = self._plugin_controller.get_logger(source)
            required_keys = {'type': six.string_types,
                             'timestamp': (float, int),
                             'values': dict,
                             'tags': dict}
            metric_ok = True
            for key, key_type in required_keys.items():
                if key not in metric:
                    log('Metric should contain keys {0}'.format(', '.join(list(required_keys.keys()))))
                    metric_ok = False
                    break
                if not isinstance(metric[key], key_type):
                    log('Metric key {0} should be of type {1}'.format(key, key_type))
                    metric_ok = False
                    break
            if metric_ok is False:
                continue
            # Get metric definition
            definition = self.definitions.get(metric['source'], {}).get(metric['type'])
            if definition is None:
                log('No metric definitions for source {0} and type {1}'.format(metric['source'], metric['type']))
                continue
            # Validate metric based on definition
            if len(metric['tags']) == 0:
                log('At least one metric tag should be defined')
                metric_ok = False
            else:
                for tag_name, tag_value in six.iteritems(metric['tags']):  # tags are optional but should be in the definition
                    if tag_name not in definition['tags']:
                        log('Metric tag {0} should be defined'.format(tag_name))
                        metric_ok = False
                    if tag_value is None:
                        log('Metric tag {0} should not be None'.format(tag_name))
                        metric_ok = False
            metric_values = set(metric['values'].keys())
            if len(metric_values) == 0:
                log('Metric should have at least one value')
                metric_ok = False
            unknown_metrics = metric_values - set([mdef['name'] for mdef in definition['metrics']])
            if len(unknown_metrics) > 0:
                log('Metric contains unknown values: {0}'.format(', '.join(unknown_metrics)))
                metric_ok = False
            if metric_ok is False:
                continue
            self._put(metric)

    def _collect_openmotics(self):
        # type: () -> None
        start = time.time()
        for metric in self._metrics_collector.collect_metrics():
            self._put(metric)

    def _distribute_plugins(self):
        try:
            metrics = []
            try:
                while len(metrics) < 250:
                    metrics.append(self.metrics_queue_plugins.pop())
            except IndexError:
                pass
            if metrics:
                rates = self._plugin_controller.distribute_metrics(metrics)
                for key, rate in six.iteritems(rates):
                    if key not in self.outbound_rates:
                        self.outbound_rates[key] = 0
                    self.outbound_rates[key] += rate
            else:
                raise DaemonThreadWait()
        except DaemonThreadWait:
            raise
        except Exception as ex:
            raise MetricsDistributeFailed('Error distributing metrics to plugins: {0}'.format(ex))

    def _distribute_openmotics(self):
        # type: () -> None
        try:
            metric = self.metrics_queue_openmotics.pop()
            for receiver in self._openmotics_receivers:
                try:
                    receiver(metric)
                except Exception as ex:
                    logger.exception('error distributing metrics')
                    raise MetricsDistributeFailed('Error distributing metrics to internal receivers: {0}'.format(ex))
                rate_key = '{0}.{1}'.format(metric['source'].lower(), metric['type'].lower())
                if rate_key not in self.outbound_rates:
                    self.outbound_rates[rate_key] = 0
                self.outbound_rates[rate_key] += 1
                self.outbound_rates['total'] += 1
        except IndexError:
            raise DaemonThreadWait()

    def event_receiver(self, event, payload):
        if event == OMBusEvents.METRICS_INTERVAL_CHANGE:
            for metric_type, interval in six.iteritems(payload):
                self.set_cloud_interval(metric_type, interval)
