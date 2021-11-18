import os
import subprocess
import time
from unittest import TestCase

import mock
import requests
import ujson as json
from requests import Session

import fakesleep
from bus.om_bus_client import MessageClient
from bus.om_bus_events import OMBusEvents
from gateway.models import Config
from ioc import SetTestMode, SetUpTestInjections
from vpn_service import CHECK_CONNECTIVITY_TIMEOUT, DEFAULT_SLEEP_TIME, \
    REBOOT_TIMEOUT, CertificateFiles, Cloud, ConfigurationTask, \
    ConnectivityTask, DataCollector, DebugDumpDataCollector, EventsTask, \
    HeartbeatService, OpenVPNTask, RebootTask, TaskExecutor, UpdateCertsTask, \
    Util


class VPNServiceTest(TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.events = []
        def _send(event):
            self.events.append(event)

        message_client = mock.Mock(MessageClient)
        message_client.send_event = _send
        SetUpTestInjections(message_client=message_client)

    def test_cloud_call_home(self):
        cloud = Cloud(url='https://example.org', uuid='foo')
        cloud._refresh_timeout = time.time() + 600  # skip authentication
        for payload, data in [({'foo': 'bar'}, {}),
                              ({'sleep_time': 0}, {'sleep_time': 0}),
                              ({key: i for i, key in enumerate(['sleep_time', 'open_vpn', 'configuration', 'intervals'])},
                               {key: i for i, key in enumerate(['sleep_time', 'open_vpn', 'configuration', 'intervals'])}),
                              ({'sleep_time': 0, 'foo': 'bar'}, {'sleep_time': 0})]:
            response = mock.Mock(requests.Response)
            response.json.return_value = data
            with mock.patch.object(Session, 'post', return_value=response) as post:
                cloud_response = cloud.call_home(payload)
                post.assert_called_once_with('https://example.org/api/gateway/heartbeat?uuid=foo',
                                             json=payload,
                                             timeout=10.0,
                                             verify=True)
                expected_data = {'success': True}
                expected_data.update(data)
                self.assertEqual(expected_data, cloud_response)
            with mock.patch.object(Session, 'post', side_effect=Exception):
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

    def test_heartbeat(self):
        service = HeartbeatService(url='https://example.org', uuid='foo')
        service._cloud._refresh_timeout = time.time() + 600  # skip authentication
        with mock.patch.object(Config, 'get_entry', return_value=False):
            service.heartbeat()
            tasks = service._executor._queue.pop()
            self.assertEqual({'events': [(OMBusEvents.VPN_OPEN, False), (OMBusEvents.CLOUD_REACHABLE, False)],
                              'cloud_enabled': False,
                              'open_vpn': False,
                              'update_certs': False}, tasks)
            self.assertEqual(DEFAULT_SLEEP_TIME, service._sleep_time)

        with mock.patch.object(Config, 'get_entry', return_value=True):
            try:
                fakesleep.monkey_patch()
                now = time.time()

                token_response = VPNServiceTest._fake_response({}, status_code=400)
                response = return_value=VPNServiceTest._fake_response({'success': True})
                with mock.patch.object(requests, 'post', return_value=token_response), \
                     mock.patch.object(Session, 'post', return_value=response):
                    service.heartbeat()
                    tasks = service._executor._queue.pop()
                    self.assertEqual({'events': [(OMBusEvents.CLOUD_REACHABLE, True)],
                                      'cloud_enabled': True,
                                      'heartbeat_success': True}, tasks)
                    self.assertEqual(DEFAULT_SLEEP_TIME, service._sleep_time)
                    self.assertEqual(now, service._last_successful_heartbeat)

                time.sleep(5)
                now += 5
                token_response = VPNServiceTest._fake_response({'access_token': 'TOKEN', 'expires_in': 300})
                response = return_value=VPNServiceTest._fake_response({'success': True})
                with mock.patch.object(requests, 'post', return_value=token_response), \
                     mock.patch.object(Session, 'post', return_value=response):
                    service.heartbeat()
                    tasks = service._executor._queue.pop()
                    self.assertEqual({'events': [(OMBusEvents.CLOUD_REACHABLE, True)],
                                      'cloud_enabled': True,
                                      'heartbeat_success': True}, tasks)
                    self.assertEqual(DEFAULT_SLEEP_TIME, service._sleep_time)
                    self.assertEqual(now, service._last_successful_heartbeat)

                time.sleep(5)
                now += 5

                for collector in service._collectors.values():
                    collector._data = collector._collector_thread._name
                debug_collector = mock.Mock(DebugDumpDataCollector)
                debug_collector.data = {}, [123]
                service._debug_collector = debug_collector

                response = VPNServiceTest._fake_response({'success': True,
                                                          'sleep_time': 2,
                                                          'open_vpn': True,
                                                          'update_certs': True,
                                                          'intervals': {'foo': 0},
                                                          'configuration': {'foo': 1}})
                with mock.patch.object(service._cloud, 'authenticate'), \
                     mock.patch.object(Session, 'post', return_value=response) as post:
                    service._cloud._session.headers.update({'Authorization': 'JWT token'})
                    service.heartbeat()
                    tasks = service._executor._queue.pop()
                    self.assertEqual({'events': [(OMBusEvents.CLOUD_REACHABLE, True)],
                                      'cloud_enabled': True,
                                      'heartbeat_success': True,
                                      'open_vpn': True,
                                      'update_certs': True,
                                      'intervals': {'foo': 0},
                                      'configuration': {'foo': 1}}, tasks)
                    self.assertEqual(2, service._sleep_time)
                    self.assertEqual(now, service._last_successful_heartbeat)
                    post.assert_called_once_with('https://example.org/api/gateway/heartbeat',
                                                 json={'errors': 'errorscoll',
                                                       'local_ip': 'ip addresscoll',
                                                       'debug': {}},
                                                 timeout=10.0,
                                                 verify=True)
                    debug_collector.clear.assert_called_once_with([123])

            finally:
                fakesleep.monkey_restore()

    def test_task_configuration(self):
        task = ConfigurationTask()
        with mock.patch.object(Config, 'set_entry') as config_set:
            context = {'configuration': {'foo': 0}}
            self.assertIsNone(task.run(context))
            config_set.assert_called_with('foo', 0)
            self.assertIsNone(task.run(context))
            config_set.assert_called_once()
            context.update({'configuration': {'foo': 1}})
            self.assertIsNone(task.run(context))
            config_set.assert_called_with('foo', 1)

    def test_task_events(self):
        task = EventsTask()
        context = {'events': [('FOO', 0)], 'intervals': {'metrics': 300}}
        expected_events = [
            ('FOO', 0),
            ('METRICS_INTERVAL_CHANGE', {'metrics': 300})
        ]
        self.assertEqual(list(task.run(context)), expected_events)
        context.update({'events': []})
        self.assertEqual(list(task.run(context)), [])
        context.update({'intervals': {'metrics': 60}})
        expected_events = [
            ('METRICS_INTERVAL_CHANGE', {'metrics': 60})
        ]
        self.assertEqual(list(task.run(context)), expected_events)

    def test_task_connectivity(self):
        task = ConnectivityTask()
        with mock.patch.object(Util, 'ping', return_value=True) as ping:
            context = {'cloud_enabled': True, 'heartbeat_success': True}
            self.assertEqual(list(task.run(context)), [('CONNECTIVITY', True)])
            self.assertTrue(context.get('connectivity_success'))
            context.update({'heartbeat_success': False})
            self.assertEqual(list(task.run(context)), [('CONNECTIVITY', True)])
            self.assertTrue(context.get('connectivity_success'))
            ping.assert_not_called()

    def test_task_connectivity_ping_timeout(self):
        task = ConnectivityTask()
        task.last_heartbeat = time.time() - 300
        with mock.patch.object(Util, 'ping', return_value=True) as ping:
            context = {'cloud_enabled': True, 'heartbeat_success': False}
            self.assertEqual(list(task.run(context)), [('CONNECTIVITY', True)])
            self.assertTrue(context['connectivity_success'])
            ping.assert_called_with('cloud.openmotics.com')
        with mock.patch.object(Util, 'default_gateway', return_value='10.0.0.1'), \
             mock.patch.object(Util, 'ping', return_value=False) as ping:
            context = {'cloud_enabled': True, 'heartbeat_success': False}
            self.assertEqual(list(task.run(context)), [('CONNECTIVITY', False)])
            self.assertFalse(context['connectivity_success'])
            self.assertFalse(context.get('perform_reboot'))
            self.assertIn(mock.call('example.org'), ping.call_args_list)
            self.assertIn(mock.call('8.8.8.8'), ping.call_args_list)
            self.assertIn(mock.call('10.0.0.1'), ping.call_args_list)

    def test_task_connectivity_reboot_timeout(self):
        task = ConnectivityTask()
        task.last_heartbeat = time.time() - 3600
        with mock.patch.object(Util, 'ping', return_value=False) as ping:
            context = {'cloud_enabled': False, 'heartbeat_success': False}
            self.assertEqual(list(task.run(context)), [('CONNECTIVITY', False)])
            self.assertFalse(context['connectivity_success'])
            self.assertFalse(context.get('perform_reboot'))
            context.update({'cloud_enabled': True})
            self.assertEqual(list(task.run(context)), [('CONNECTIVITY', False)])
            self.assertFalse(context['connectivity_success'])
            self.assertTrue(context['perform_reboot'])

    def test_task_reboot(self):
        task = RebootTask()
        with mock.patch.object(subprocess, 'call', return_value=None) as call:
            context = {}
            self.assertIsNone(task.run(context))
            call.assert_not_called()
            context.update({'perform_reboot': True})
            self.assertIsNone(task.run(context))

    def test_openvpn_task(self):
        task = OpenVPNTask()
        with mock.patch.object(CertificateFiles, 'activate_vpn', return_value=False) as activate, \
             mock.patch.object(Util, 'ping', return_value=False), \
             mock.patch.object(Util, 'check_vpn', return_value=False), \
             mock.patch.object(Util, 'start_vpn') as start_vpn, \
             mock.patch.object(Util, 'stop_vpn') as stop_vpn:
            # VPN disabled
            context = {'cloud_enabled': True, 'heartbeat_success': True, 'connectivity_success': True, 'open_vpn': False}
            self.assertEqual(list(task.run(context)), [('VPN_OPEN', False)])
            start_vpn.assert_not_called()
            stop_vpn.assert_not_called()
            activate.assert_not_called()
            # Open without connectivity
            context.update({'heartbeat_success': False, 'connectivity_success': False, 'open_vpn': True})
            self.assertEqual(list(task.run(context)), [])
            start_vpn.assert_not_called()
            stop_vpn.assert_not_called()
            # Start service
            context.update({'connectivity_success': True})
            self.assertEqual(list(task.run(context)), [('VPN_OPEN', False)])
            start_vpn.assert_called()
            stop_vpn.assert_not_called()
            activate.assert_called_with(rollback=False)
        with mock.patch.object(CertificateFiles, 'activate_vpn', return_value=False) as activate, \
             mock.patch.object(Util, 'ping', return_value=False), \
             mock.patch.object(Util, 'check_vpn', return_value=True), \
             mock.patch.object(Util, 'start_vpn') as start_vpn, \
             mock.patch.object(Util, 'stop_vpn') as stop_vpn:
            # Stop service
            context.update({'open_vpn': False})
            self.assertEqual(list(task.run(context)), [('VPN_OPEN', True)])
            start_vpn.assert_not_called()
            stop_vpn.assert_called()
            activate.assert_not_called()

    def test_openvpn_task_rollback(self):
        task = OpenVPNTask()
        with mock.patch.object(CertificateFiles, 'activate_vpn', return_value=True) as activate, \
             mock.patch.object(Util, 'ping', return_value=False), \
             mock.patch.object(Util, 'check_vpn', return_value=True), \
             mock.patch.object(Util, 'start_vpn') as start_vpn, \
             mock.patch.object(Util, 'stop_vpn') as stop_vpn:
            # Attempt rollback
            context = {'cloud_enabled': True, 'heartbeat_success': True, 'connectivity_success': True, 'open_vpn': True}
            task.connect_retries = 10
            self.assertEqual(list(task.run(context)), [('VPN_OPEN', True)])
            activate.assert_called_with(rollback=True)

    def test_openvpn_task_activate(self):
        task = OpenVPNTask()
        with mock.patch.object(CertificateFiles, 'activate_vpn', return_value=True) as activate, \
             mock.patch.object(Util, 'ping', return_value=True), \
             mock.patch.object(Util, 'check_vpn', return_value=True), \
             mock.patch.object(Util, 'start_vpn') as start_vpn, \
             mock.patch.object(Util, 'stop_vpn') as stop_vpn:
            # Restart after activation
            context = {'cloud_enabled': True, 'heartbeat_success': True, 'connectivity_success': True, 'open_vpn': True}
            self.assertEqual(list(task.run(context)), [('VPN_OPEN', True)])
            start_vpn.assert_called()
            stop_vpn.assert_called()
            activate.assert_called_with(rollback=False)

    def test_openvpn_check_status(self):
        task = OpenVPNTask()
        with mock.patch.object(subprocess, 'check_output', return_value=''):
            self.assertTrue(task._check_status())

        ip_r_output = '10.0.128.0/24 via 10.37.0.9 dev tun0\n' + \
                      '10.0.129.0/24 via 10.37.0.9 dev tun0\n' + \
                      '10.37.0.1 via 10.37.0.9 dev tun0'
        with mock.patch.object(subprocess, 'check_output', return_value=ip_r_output):
            self.assertTrue(task._check_status())


    def test_update_certs_task(self):
        cloud = mock.Mock(Cloud)
        task = UpdateCertsTask(cloud)
        files = mock.Mock(CertificateFiles)
        files.cert_path.side_effect = lambda *args: os.path.join('/certs', *args)
        with mock.patch.object(subprocess, 'check_output', return_value=''), \
             mock.patch.object(cloud, 'confirm_client_certs', side_effect=(False, True)), \
             mock.patch.object(cloud, 'issue_client_certs', return_value={'data': {}}) as issue, \
             mock.patch.object(task, 'new_version', return_value='foo'), \
             mock.patch.object(task, 'get_cert_files', return_value=files):
            context = {'heartbeat_success': True, 'update_certs': False}
            self.assertEqual(list(task.run(context)), [('CLIENT_CERTS_CHANGED', False)])
            cloud.issue_client_certs.assert_not_called()
            context.update({'update_certs': True})
            self.assertEqual(list(task.run(context)), [('CLIENT_CERTS_CHANGED', True)])
            cloud.issue_client_certs.assert_called()
            files.setup_certs.assert_called_with('foo', {'data': {}})
            cloud.confirm_client_certs.assert_called_with(key_path='/certs/foo/client.key')
            files.activate.assert_called_with('foo')
            files.rollback.assert_not_called()
            cloud.authenticate.assert_called_with(raise_exception=True)

    def test_update_certs_task_rollback(self):
        cloud = mock.Mock(Cloud)
        task = UpdateCertsTask(cloud)
        files = mock.Mock(CertificateFiles)
        files.cert_path.side_effect = lambda *args: os.path.join('/certs', *args)
        with mock.patch.object(subprocess, 'check_output', return_value=''), \
             mock.patch.object(cloud, 'authenticate', side_effect=Exception('Invalid certificate')), \
             mock.patch.object(cloud, 'confirm_client_certs', side_effect=(False, True)), \
             mock.patch.object(cloud, 'issue_client_certs', return_value={'data': {}}) as issue, \
             mock.patch.object(task, 'new_version', return_value='foo'), \
             mock.patch.object(task, 'get_cert_files', return_value=files):
            context = {'heartbeat_success': True, 'update_certs': True}
            self.assertEqual(list(task.run(context)), [('CLIENT_CERTS_CHANGED', False)])
            files.activate.assert_called_with('foo')
            files.rollback.assert_called()

    def test_update_certs_task_failure(self):
        cloud = mock.Mock(Cloud)
        task = UpdateCertsTask(cloud)
        files = mock.Mock(CertificateFiles)
        files.cert_path.side_effect = lambda *args: os.path.join('/certs', *args)
        with mock.patch.object(subprocess, 'check_output', return_value=''), \
             mock.patch.object(cloud, 'confirm_client_certs',
                               side_effect=(False, False,
                                            False, Exception('Invalid certificate'))), \
             mock.patch.object(cloud, 'issue_client_certs', return_value={'data': {}}) as issue, \
             mock.patch.object(task, 'new_version', return_value='foo'), \
             mock.patch.object(task, 'get_cert_files', return_value=files):
            context = {'heartbeat_success': True, 'update_certs': True}
            self.assertEqual(list(task.run(context)), [('CLIENT_CERTS_CHANGED', False)])
            self.assertEqual(list(task.run(context)), [('CLIENT_CERTS_CHANGED', False)])
            files.activate.assert_not_called()
            files.rollback.assert_not_called()

    @staticmethod
    def _fake_response(data, status_code=200):
        response = mock.Mock(requests.Response)
        response.status_code = status_code
        if status_code == 200:
            response.raise_for_status.return_value = None
        else:
            response.raise_for_status.side_effect = Exception('Mocked server error')
        response.text = 'MOCK'
        response.json.return_value = data
        return response
