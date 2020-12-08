import mock
import os
import requests
import subprocess
import time
import ujson as json
from unittest import TestCase

import fakesleep
from bus.om_bus_client import MessageClient
from bus.om_bus_events import OMBusEvents
from gateway.models import Config
from ioc import SetTestMode, SetUpTestInjections
from vpn_service import VpnController, TaskExecutor, Cloud, \
    DataCollector, HeartbeatService, DebugDumpDataCollector, \
    REBOOT_TIMEOUT, CHECK_CONNECTIVITY_TIMEOUT, DEFAULT_SLEEP_TIME


class VPNServiceTest(TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_openvpn_connectivity(self):
        controller = VpnController()
        self.assertFalse(controller.vpn_connected)

        ip_r_output = ''
        with mock.patch.object(subprocess, 'check_output', return_value=ip_r_output):
            controller._vpn_connected()
            self.assertFalse(controller.vpn_connected)

        ip_r_output = '10.0.128.0/24 via 10.37.0.9 dev tun0\n' + \
                      '10.0.129.0/24 via 10.37.0.9 dev tun0\n' + \
                      '10.37.0.1 via 10.37.0.9 dev tun0'
        with mock.patch.object(subprocess, 'check_output', return_value=ip_r_output):
            with mock.patch.object(TaskExecutor, '_ping', return_value=True) as ping:
                controller._vpn_connected()
                self.assertTrue(controller.vpn_connected)
                ping.assert_called_once_with('10.37.0.1', verbose=False)
            with mock.patch.object(TaskExecutor, '_ping', return_value=False) as ping:
                controller._vpn_connected()
                self.assertFalse(controller.vpn_connected)
                ping.assert_called_once_with('10.37.0.1', verbose=False)

        ip_r_output = 'foobar'
        with mock.patch.object(subprocess, 'check_output', return_value=ip_r_output):
            controller._vpn_connected()
            self.assertFalse(controller.vpn_connected)

    def test_cloud_call_home(self):
        url = 'https://foobar'
        cloud = Cloud(url=url)
        for payload, response in [({'foo': 'bar'}, {}),
                                  ({'sleep_time': 0}, {'sleep_time': 0}),
                                  ({key: i for i, key in enumerate(['sleep_time', 'open_vpn', 'configuration', 'intervals'])},
                                   {key: i for i, key in enumerate(['sleep_time', 'open_vpn', 'configuration', 'intervals'])}),
                                  ({'sleep_time': 0, 'foo': 'bar'}, {'sleep_time': 0})]:
            with mock.patch.object(requests, 'post', return_value=type('Response', (), {'text': json.dumps(response)})) as post:
                cloud_response = cloud.call_home(payload)
                post.assert_called_once_with(url, data={'extra_data': json.dumps(payload, sort_keys=True)}, timeout=10.0)
                expected_response = response
                expected_response['success'] = True
                self.assertEqual(expected_response, cloud_response)
            with mock.patch.object(requests, 'post', side_effect=RuntimeError):
                cloud_response = cloud.call_home(payload)
                self.assertEqual({'success': False}, cloud_response)

    def test_data_collectors(self):
        callback_data = {'data': None}

        def _callback():
            return callback_data['data']

        collector = DataCollector(name='foo', collector=_callback, interval=60)
        self.assertIsNone(collector.data)
        callback_data['data'] = 1
        collector._collect()
        self.assertEqual(1, collector.data)
        self.assertIsNone(collector.data)
        callback_data['data'] = 2
        collector._collect()
        self.assertEqual(2, collector.data)
        self.assertIsNone(collector.data)

    def test_debug_collector(self):
        collector = DebugDumpDataCollector()

        for include_dumps in [True, False]:
            with mock.patch.object(Config, 'get_entry', return_value=include_dumps):
                collector._collect()
                self.assertEqual(({'dump_info': {}, 'dumps': {}}, []), collector.data)
                self.assertIsNone(collector.data)

                for file_info in [[{'info': 0}],
                                  [{'info': 0}, {'info': 1}]]:
                    files = {}
                    try:
                        expected_data = {'dump_info': {}, 'dumps': {}}
                        expected_references = []
                        for index, content in enumerate(file_info):
                            filename = '/tmp/debug_{0}.json'.format(index)
                            with open(filename, 'w') as file_:
                                json.dump(content, file_)
                            timestamp = os.path.getmtime(filename)
                            files[filename] = timestamp
                            expected_data['dump_info'][timestamp] = content['info']
                            if include_dumps:
                                expected_data['dumps'][timestamp] = content
                            expected_references.append(timestamp)
                            time.sleep(0.01)
                        collector._collect()
                        collector_data = collector.data
                        self.assertEqual((expected_data, sorted(expected_references)), (collector_data[0], sorted(collector_data[1])))
                        self.assertIsNone(collector.data)
                        collector._collect()
                        collector_data = collector.data
                        self.assertEqual((expected_data, sorted(expected_references)),
                                         (collector_data[0], sorted(collector_data[1])))
                        self.assertIsNone(collector.data)
                        collector.clear(collector_data[1])
                        collector._collect()
                        self.assertEqual(({'dump_info': {}, 'dumps': {}}, []), collector.data)
                        self.assertIsNone(collector.data)
                    finally:
                        for filename in files.keys():
                            try:
                                os.remove(filename)
                            except Exception:
                                pass

    def test_task_executor_execution(self):
        events = []
        executor = VPNServiceTest._get_task_executor(events)
        with ExecutorPatch(executor) as (pcd, pid, ov, cc):
            self.assertFalse(executor._executor._tick.is_set())
            executor._execute_tasks()
            self.assertFalse(executor._executor._tick.is_set())
            executor.set_new_tasks({})
            self.assertTrue(executor._executor._tick.is_set())
            executor._execute_tasks()
            pcd.assert_not_called()
            pid.assert_not_called()
            ov.assert_not_called()
            cc.assert_not_called()

        parts = ['configuration', 'intervals', 'open_vpn', 'connectivity']
        for index, part in enumerate(parts):
            with ExecutorPatch(executor) as (pcd, pid, ov, cc):
                executor.set_new_tasks({part: index})
                executor._execute_tasks()
                mapping = {'configuration': pcd,
                           'intervals': pid,
                           'open_vpn': ov,
                           'connectivity': cc}
                for executor_part, executor_patch in mapping.items():
                    if executor_part != part:
                        executor_patch.assert_not_called()
                    else:
                        executor_patch.assert_called_once_with(index)

        with ExecutorPatch(executor) as (pcd, pid, ov, cc):
            executor.set_new_tasks({part: index for index, part in enumerate(parts)})
            executor._execute_tasks()
            pcd.assert_called_once_with(0)
            pid.assert_called_once_with(1)
            ov.assert_called_once_with(2)
            cc.assert_called_once_with(3)

        executor.set_new_tasks({'events': [('foo', 1), ('bar', 2)]})
        self.assertEqual([], events)
        executor._execute_tasks()
        self.assertEqual([('foo', 1), ('bar', 2)], events)

    def test_executor_has_connectivity(self):
        events = []
        executor = VPNServiceTest._get_task_executor(events)

        def _ping(target):
            return target in responding_targets

        TaskExecutor._ping = staticmethod(_ping)
        with mock.patch.object(TaskExecutor, '_get_default_gateway', return_value='192.168.0.1'):
            for expected_result, targets in [(True, ['cloud.openmotics.com']),
                                             (True, ['example.com']),
                                             (False, ['8.8.8.8']),
                                             (True, ['192.168.0.1']),
                                             (False, [])]:
                responding_targets = targets
                self.assertEqual(expected_result, executor._has_connectivity())

    def test_executor_check_connectivity(self):
        events = []
        executor = VPNServiceTest._get_task_executor(events)

        with mock.patch.object(subprocess, 'call') as process:
            executor._check_connectivity(time.time())
            self.assertEqual([(OMBusEvents.CONNECTIVITY, True)], events)
            process.assert_not_called()

        events.pop(0)
        with mock.patch.object(subprocess, 'call') as process, \
                mock.patch.object(TaskExecutor, '_has_connectivity', return_value=True):
            executor = TaskExecutor()
            executor._check_connectivity(time.time() - REBOOT_TIMEOUT - 5)
            self.assertEqual([(OMBusEvents.CONNECTIVITY, True)], events)
            process.assert_not_called()

        events.pop(0)
        with mock.patch.object(subprocess, 'call') as process, \
                mock.patch.object(TaskExecutor, '_has_connectivity', return_value=False):
            executor = TaskExecutor()
            executor._check_connectivity(time.time() - CHECK_CONNECTIVITY_TIMEOUT - 5)
            self.assertEqual([(OMBusEvents.CONNECTIVITY, False)], events)
            process.assert_not_called()

        events.pop(0)
        with mock.patch.object(subprocess, 'call') as process, \
                mock.patch.object(TaskExecutor, '_has_connectivity', return_value=False):
            executor = TaskExecutor()
            executor._check_connectivity(time.time() - REBOOT_TIMEOUT - 5)
            self.assertEqual([(OMBusEvents.CONNECTIVITY, False)], events)
            process.assert_called_once_with('sync && reboot', shell=True)

    def test_executor_open_vpn(self):
        events = [None]
        executor = VPNServiceTest._get_task_executor(events)

        for should_open, is_running, is_open in [(True, True, True),
                                                 (True, False, True),
                                                 (True, False, False),
                                                 (False, False, False),
                                                 (False, True, True),
                                                 (False, True, False)]:
            with VpnControllerPatch(executor, is_running=is_running) as (cv, sa, so):
                events.pop(0)
                executor._vpn_controller.vpn_connected = is_open
                executor._open_vpn(should_open)
                self.assertEquals(is_running and is_open, executor.vpn_open)
                cv.assert_called()
                self.assertEqual(2, cv.call_count)
                if should_open and not is_running:
                    sa.assert_called_once()
                else:
                    sa.assert_not_called()
                if not should_open and is_running:
                    so.assert_called_once()
                else:
                    so.assert_not_called()
                self.assertEquals([(OMBusEvents.VPN_OPEN, is_running and is_open)], events)

    def test_executor_process_configuration_data(self):
        events = []
        executor = VPNServiceTest._get_task_executor(events)

        with mock.patch.object(Config, 'set_entry') as config_set:
            payload = {'foo': 0}
            executor._process_configuration_data(payload)
            config_set.assert_called_with('foo', 0)
            self.assertEqual(payload, executor._configuration)

        with mock.patch.object(Config, 'set_entry') as config_set:
            executor._process_configuration_data(payload)
            config_set.assert_not_called()
            self.assertEqual(payload, executor._configuration)

        with mock.patch.object(Config, 'set_entry') as config_set:
            payload = {'foo': 1}
            executor._process_configuration_data(payload)
            config_set.assert_called_with('foo', 1)
            self.assertEqual(payload, executor._configuration)

    def test_executor_process_interval_data(self):
        events = []
        executor = VPNServiceTest._get_task_executor(events)

        payload = {'foo': 0}
        executor._process_interval_data(payload)
        self.assertEqual([(OMBusEvents.METRICS_INTERVAL_CHANGE, payload)], events)
        self.assertEqual(payload, executor._intervals)

        events.pop(0)
        executor._process_interval_data(payload)
        self.assertEqual([], events)
        self.assertEqual(payload, executor._intervals)

        payload = {'foo': 1}
        executor._process_interval_data(payload)
        self.assertEqual([(OMBusEvents.METRICS_INTERVAL_CHANGE, payload)], events)
        self.assertEqual(payload, executor._intervals)

    def test_heartbeat(self):
        events = []
        VPNServiceTest._get_task_executor(events)

        heartbeat = HeartbeatService(url='https://foobar')

        with mock.patch.object(Config, 'get_entry', return_value=False):
            heartbeat._beat()
            tasks = heartbeat._task_executor._tasks.pop()
            self.assertEqual({'events': [(OMBusEvents.VPN_OPEN, False), (OMBusEvents.CLOUD_REACHABLE, False)],
                              'open_vpn': False}, tasks)
            self.assertEqual(DEFAULT_SLEEP_TIME, heartbeat._sleep_time)

        with mock.patch.object(Config, 'get_entry', return_value=True):
            try:
                fakesleep.monkey_patch()
                now = time.time()

                response = {'success': False}
                with mock.patch.object(requests, 'post', return_value=VPNServiceTest._fake_response(response)):
                    heartbeat._beat()
                    tasks = heartbeat._task_executor._tasks.pop()
                    self.assertEqual({'connectivity': now,
                                      'events': [(OMBusEvents.CLOUD_REACHABLE, True)],
                                      'open_vpn': True}, tasks)
                    self.assertEqual(DEFAULT_SLEEP_TIME, heartbeat._sleep_time)
                    self.assertEqual(now, heartbeat._last_successful_heartbeat)

                time.sleep(5)
                now += 5
                response = {'success': True}
                with mock.patch.object(requests, 'post', return_value=VPNServiceTest._fake_response(response)):
                    heartbeat._beat()
                    tasks = heartbeat._task_executor._tasks.pop()
                    self.assertEqual({'connectivity': now,
                                      'events': [(OMBusEvents.CLOUD_REACHABLE, True)],
                                      'open_vpn': True}, tasks)
                    self.assertEqual(DEFAULT_SLEEP_TIME, heartbeat._sleep_time)
                    self.assertEqual(now, heartbeat._last_successful_heartbeat)

                time.sleep(5)
                now += 5

                for collector in heartbeat._collectors.values():
                    collector._data = collector._collector_thread._name
                debug_collector = mock.Mock(DebugDumpDataCollector)
                debug_collector.data = {}, [123]
                heartbeat._debug_collector = debug_collector

                response = {'success': True,
                            'sleep_time': 2,
                            'intervals': {'foo': 0},
                            'configuration': {'foo': 1}}
                with mock.patch.object(requests, 'post', return_value=VPNServiceTest._fake_response(response)) as post:
                    heartbeat._beat()
                    tasks = heartbeat._task_executor._tasks.pop()
                    self.assertEqual({'connectivity': now,
                                      'events': [(OMBusEvents.CLOUD_REACHABLE, True)],
                                      'intervals': {'foo': 0},
                                      'configuration': {'foo': 1},
                                      'open_vpn': True}, tasks)
                    self.assertEqual(2, heartbeat._sleep_time)
                    self.assertEqual(now, heartbeat._last_successful_heartbeat)
                    post.assert_called_once_with('https://foobar',
                                                 data={'extra_data': json.dumps({'inputs': 'inputscoll',
                                                                                 'errors': 'errorscoll',
                                                                                 'local_ip': 'ip addresscoll',
                                                                                 'thermostats': 'thermostatscoll',
                                                                                 'shutters': 'shutterscoll',
                                                                                 'debug': {}},
                                                                                sort_keys=True)},
                                                 timeout=10.0)
                    debug_collector.clear.assert_called_once_with([123])

            finally:
                fakesleep.monkey_restore()

    @staticmethod
    def _fake_response(response):
        return type('Response', (), {'text': json.dumps(response)})

    @staticmethod
    def _get_task_executor(events):
        def _send_event(*args):
            events.append(args)

        message_client = mock.Mock(MessageClient)
        message_client.send_event = _send_event
        SetUpTestInjections(message_client=message_client)
        return TaskExecutor()


class VpnControllerPatch(object):
    def __init__(self, executor, is_running):
        self._controller = executor._vpn_controller
        self._is_running = is_running
        self._patches = []

    def __enter__(self):
        self._patches = [mock.patch.object(VpnController, 'check_vpn', return_value=self._is_running).__enter__(),
                         mock.patch.object(VpnController, 'start_vpn', return_value=None).__enter__(),
                         mock.patch.object(VpnController, 'stop_vpn', return_value=None).__enter__()]
        return self._patches

    def __exit__(self, *args, **kwargs):
        for patch in self._patches:
            try:
                patch.__exit__(*args, **kwargs)
            except Exception:
                pass


class ExecutorPatch(object):
    def __init__(self, executor):
        self._executor = executor
        self._patches = []

    def __enter__(self):
        self._patches = [mock.patch.object(self._executor, '_process_configuration_data', return_value=None).__enter__(),
                         mock.patch.object(self._executor, '_process_interval_data', return_value=None).__enter__(),
                         mock.patch.object(self._executor, '_open_vpn', return_value=None).__enter__(),
                         mock.patch.object(self._executor, '_check_connectivity', return_value=None).__enter__()]
        return self._patches

    def __exit__(self, *args, **kwargs):
        for patch in self._patches:
            try:
                patch.__exit__(*args, **kwargs)
            except Exception:
                pass
