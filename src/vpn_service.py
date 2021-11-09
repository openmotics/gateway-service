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
The vpn_service sends a regular heartbeat with some basic information to the cloud. In return, it
is instructed to open a VPN tunnel or not, and will receive some configration info.
"""

from __future__ import absolute_import

from platform_utils import System, Hardware
System.import_libs()

import tempfile
import glob
import logging
import logging.handlers
import os
import signal
import subprocess
import time
import traceback
import shutil
from datetime import datetime, timedelta
from collections import deque
from threading import Lock

import requests
import six
from requests import ConnectionError
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
import ujson as json
from six.moves.configparser import ConfigParser, NoOptionError
from six.moves.urllib.parse import urlparse, urlunparse

import constants
from bus.om_bus_client import MessageClient
from bus.om_bus_events import OMBusEvents
from gateway.daemon_thread import DaemonThread
from gateway.initialize import setup_minimal_vpn_platform
from gateway.models import Config
from ioc import INJECTED, Inject
from logs import Logs

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple

REBOOT_TIMEOUT = 900
CHECK_CONNECTIVITY_TIMEOUT = 60
DEFAULT_SLEEP_TIME = 30.0

logger = logging.getLogger('openmotics')


class VpnController(object):
    """ Contains methods to check the vpn status, start and stop the vpn. """
    config = ConfigParser()
    config.read(constants.get_config_file())
    vpn_supervisor = config.get('OpenMotics', 'vpn_supervisor') == 'True' if config.has_option('OpenMotics', 'vpn_supervisor') else True
    if System.get_operating_system().get('ID') == System.OS.BUILDROOT or not vpn_supervisor:
        vpn_binary = 'openvpn'
        config_location = '/etc/openvpn/client/'
        start_cmd = 'cd {} ; {} --suppress-timestamps --nobind --config vpn.conf > /dev/null'.format(config_location, vpn_binary)
        stop_cmd = 'killall {} > /dev/null'.format(vpn_binary)
        check_cmd = 'ps -a | grep {} | grep -v "grep" > /dev/null'.format(vpn_binary)
    else:
        vpn_service = System.get_vpn_service()
        start_cmd = 'systemctl start {0} > /dev/null'.format(vpn_service)
        stop_cmd = 'systemctl stop {0} > /dev/null'.format(vpn_service)
        check_cmd = 'systemctl is-active {0} > /dev/null'.format(vpn_service)

    def __init__(self):
        self.connected = False
        self._vpn_tester = DaemonThread(name='vpnctl',
                                        target=self._vpn_connected,
                                        interval=5)

    def start(self):
        self._vpn_tester.start()

    @staticmethod
    def start_vpn():
        """ Start openvpn """
        logger.info('Starting VPN')
        return subprocess.call(VpnController.start_cmd, shell=True) == 0

    @staticmethod
    def stop_vpn():
        """ Stop openvpn """
        logger.info('Stopping VPN')
        return subprocess.call(VpnController.stop_cmd, shell=True) == 0

    @staticmethod
    def check_vpn():
        """ Check if openvpn is running """
        return subprocess.call(VpnController.check_cmd, shell=True) == 0

    def _vpn_connected(self):
        """ Checks if the VPN tunnel is connected """
        try:
            routes = subprocess.check_output('ip r | grep tun | grep via || true', shell=True).strip()
            # example output:
            # 10.0.0.0/24 via 10.37.0.5 dev tun0\n
            # 10.37.0.1 via 10.37.0.5 dev tun0
            result = False
            if routes:
                if not isinstance(routes, str):  # to ensure python 2 and 3 compatibility
                    routes = routes.decode()

                vpn_servers = [route.split(' ')[0] for route in routes.split('\n') if '/' not in route]
                for vpn_server in vpn_servers:
                    if TaskExecutor._ping(vpn_server, verbose=False):
                        result = True
                        break
            self.connected = result
        except Exception as ex:
            logger.info('Exception occured during vpn connectivity test: {0}'.format(ex))
            self.connected = False


class Cloud(object):
    """ Connects to the cloud """
    request_kwargs = {
        'timeout': 10.0,
        'verify': System.get_operating_system().get('ID') != System.OS.ANGSTROM
    }

    def __init__(self, url=None, uuid=None):
        self._session = requests.Session()
        self._url = url
        self._uuid = uuid
        self._auth_retries = 0
        self._refresh_timeout = 0.0
        if url is None:
            config = ConfigParser()
            config.read(constants.get_config_file())
            try:
                self._uuid = config.get('OpenMotics', 'uuid')
                url = config.get('OpenMotics', 'vpn_check_url')
                if '%' in url:
                    url = url % self._uuid
            except NoOptionError:
                pass
        if url:
            self._url = urlparse(url)

    def _build_url(self, path, query=None):
        return urlunparse((self._url.scheme, self._url.netloc, path, '', query, ''))

    def authenticate(self, key_path=None, raise_exception=False):
        if System.get_operating_system().get('ID') == System.OS.ANGSTROM:
            return
        try:
            import jwt
            payload = {'iss': 'OM',
                       'sub': 'gateway',
                       'aud': self._url.hostname,
                       'exp': int(time.time() + 60),
                       'registration_key': self._uuid}
            key_path = key_path or CertificateFiles.cert_path(CertificateFiles.CURRENT, 'client.key')
            with open(key_path, 'rb') as fd:
                client_key = fd.read()
            token = jwt.encode(payload, client_key, algorithm='RS256')
            data = {'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                    'assertion': token.decode(),
                    'scope': 'device'}
            response = requests.post(self._build_url('/api/v1/authentication/oauth2/token'), data=data)
            response.raise_for_status()
            data = response.json()
            logger.info('Authenticated until %s', datetime.now() + timedelta(seconds=data['expires_in']))
            self._session.headers.update({'Authorization': 'JWT {0}'.format(data['access_token'])})
            self._auth_retries = 0
            self._refresh_timeout = time.time() + data['expires_in']
        except Exception as exc:
            backoff = 4 ** self._auth_retries
            self._auth_retries += 1
            self._refresh_timeout = time.time() + backoff
            if isinstance(exc, HTTPError):
                logger.error('retrying (%s) authentication failure in %ss: %s', self._auth_retries, backoff, exc.response.text)
            else:
                logger.error('retrying (%s) authentication error in %ss: %s', self._auth_retries, backoff, exc)
            if raise_exception:
                raise

    def _request(self, method, path, **kwargs):
        try:
            if self._session.headers.get('Authorization'):
                url = self._build_url(path)
            else:
                query = 'uuid={0}'.format(self._uuid)
                url = self._build_url(path, query=self._url.query or query)
            logger.debug('Request %s %s',  method.__name__.upper(), path)
            response = method(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            if exc.response.status_code == 403:
                logger.error('Authentication error: %s', exc.response.text)
                self._session = requests.Session()
            elif exc.response.status_code not in (404,):
                logger.error('API error: %s', exc.response.text)
            raise

    def _get(self, path):
        return self._request(self._session.get, path, **self.request_kwargs)

    def _post(self, path, data):
        return self._request(self._session.post, path, json=data, **self.request_kwargs)

    def confirm_client_certs(self, key_path=None):
        self.authenticate(key_path=key_path)
        try:
            data = self._get('/api/gateway/client-certs')
            return data['confirmed']
        except Exception:
            return False

    def issue_client_certs(self):
        return self._post('/api/gateway/client-certs', {})

    def call_home(self, extra_data):
        """ Call home reporting our state, and optionally get new settings or other stuff """
        if self._url is None:
            logger.debug('Cloud not configured, skipping call home')
        try:
            if self._refresh_timeout < time.time():
                self.authenticate()
            response = self._post('/api/gateway/heartbeat', extra_data)
            data = {'success': True}
            data.update({k: v for k, v in response.items() if k in
                         ('sleep_time', 'open_vpn', 'update_certs', 'configuration', 'intervals')})
            return data
        except Exception:
            logger.exception('Exception occured during call home')
            return {'success': False}


class Gateway(object):
    """ Class to get the current status of the gateway. """

    def __init__(self, host="127.0.0.1"):
        self._host = host
        config = ConfigParser()
        config.read(constants.get_config_file())
        if config.has_option('OpenMotics', 'http_port'):
            self._port = config.get('OpenMotics', 'http_port')
        else:
            self._port = 80

    def do_call(self, uri):
        """ Do a call to the webservice, returns a dict parsed from the json returned by the webserver. """
        try:
            request = requests.get('http://{0}:{1}/{2}'.format(self._host, self._port, uri), timeout=10.0)
            return json.loads(request.text)
        except Exception as ex:
            message = str(ex)
            if 'Connection refused' in message:
                logger.warning('Cannot connect to the OpenMotics service')
            else:
                logger.error('Exception during Gateway call {0}: {1}'.format(uri, message))
            return

    def get_errors(self):
        """ Get the errors on the gateway. """
        data = self.do_call('get_errors?token=None')
        if data is None:
            return None
        if data['errors'] is not None:
            master_errors = sum([error[1] for error in data['errors']])
        else:
            master_errors = 0
        return {'master_errors': master_errors,
                'master_last_success': data['master_last_success'],
                'power_last_success': data['power_last_success']}


class CertificateFiles(object):
    CURRENT = 'current'
    PREVIOUS = 'previous'
    VPN = 'vpn'

    FILES = {'ca': 'ca.crt',
             'certificate': 'client.crt',
             'private_key': 'client.key'}

    def __init__(self):
        self.current = self.cert_path(CertificateFiles.CURRENT)
        self.previous = self.cert_path(CertificateFiles.PREVIOUS)
        self.vpn = self.cert_path(CertificateFiles.VPN)

    @staticmethod
    def cert_path(*args, prefix=constants.OPENMOTICS_PREFIX):
        return os.path.join(prefix, 'versions', 'certificates', *args)

    @staticmethod
    def get_versions():
        versions = set(x.split(os.path.sep)[-1] for x in glob.glob(CertificateFiles.cert_path('*')))
        versions -= set([CertificateFiles.CURRENT, CertificateFiles.PREVIOUS, CertificateFiles.VPN])
        return versions

    def activate_vpn(self, rollback=False):
        if rollback:
            try:
                vpn_target = os.readlink(self.vpn).split(os.path.sep)[-1]
                logger.info('Marking certificates %s as failed', vpn_target)
                marker = self.cert_path(vpn_target, '.failure')
                if not os.path.exists(marker):
                    with open(marker, 'w') as fd:
                        pass
            except Exception:
                vpn_target = None

            versions = self.get_versions()
            try:
                current_target = os.readlink(self.current).split(os.path.sep)[-1]
            except Exception:
                current_target = None
            target = None
            if os.path.exists(self.cert_path(current_target, '.failure')):
                for version in sorted(versions, reverse=True):
                    if not os.path.exists(self.cert_path(version, '.failure')):
                        target = version
                        break
            else:
                target = current_target
            if target is None:
                target = current_target
            if target != vpn_target:
                logger.info('Rolling back vpn certificates %s -> %s', vpn_target, target)
                temp_link = tempfile.mktemp(dir=self.cert_path())
                os.symlink(target, temp_link)
                os.replace(temp_link, self.vpn)
                return True
        else:
            try:
                target = os.readlink(self.current).split(os.path.sep)[-1]
            except Exception:
                target = None
            try:
                vpn_target = os.readlink(self.current).split(os.path.sep)[-1]
            except Exception:
                vpn_target = None

            if target and target != vpn_target:
                logger.info('Activating vpn certificates %s', target)
                temp_link = tempfile.mktemp(dir=self.cert_path())
                os.symlink(target, temp_link)
                os.replace(temp_link, self.vpn)
                return True
        return False


    def setup_links(self):
        if all(os.path.exists(x) for x in (self.current, self.vpn)):
            return

        certificates = self.cert_path()
        if not os.path.exists(certificates):
            os.makedirs(certificates)

        versions = self.get_versions()
        latest = None
        for version in sorted(versions, reverse=True):
            if os.path.exists(self.cert_path(version, 'client.key')):
                latest = version
                break

        for link in (self.current, self.vpn):
            if not os.path.exists(link):
                if latest:
                    temp_link = tempfile.mktemp(dir=self.cert_path())
                    os.symlink(latest, temp_link)
                    os.replace(temp_link, link)
                else:
                    logger.warning('No certificates available')

    def cleanup_versions(self):
        try:
            versions = self.get_versions()
            versions -= set(list(sorted(versions, reverse=True))[:3])
            for link in (self.previous, self.current):
                try:
                    link_target = os.readlink(link).split(os.path.sep)[-1]
                    if link_target in versions:
                        logger.info('Keeping certificates %s', link_target)
                        versions -= set([link_target])
                except Exception:
                    pass
            for version in versions:
                logger.info('Removing certificates %s', version)
                shutil.rmtree(self.cert_path(version))
        except Exception as exc:
            logger.error('Failed to cleanup versions: %s', exc)

    def setup_certs(self, target, data):
        logger.info('Saving %s', data['data'].get('serial_number'))
        version = self.cert_path(target)
        if not os.path.exists(version):
            os.makedirs(version)
        for key, file in self.FILES.items():
            with open(os.path.join(version, file), 'w') as fd:
                fd.write(data['data'][key])

    def activate(self, target):
        logger.info('Activating certificates %s', target)
        temp_link = tempfile.mktemp(dir=self.cert_path())
        try:
            previous_target = os.readlink(self.current).split(os.path.sep)[-1]
        except Exception:
            previous_target = None
        os.symlink(target, temp_link)
        os.replace(temp_link, self.current)
        if previous_target:
            os.symlink(previous_target, temp_link)
            os.replace(temp_link, self.previous)

    def rollback(self):
        previous_target = os.readlink(self.previous).split(os.path.sep)[-1]
        logger.info('Rolling back certificates %s', previous_target)
        temp_link = tempfile.mktemp(dir=self.cert_path())
        os.symlink(previous_target, temp_link)
        os.replace(temp_link, self.current)
        os.unlink(self.previous)


class DataCollector(object):
    def __init__(self, name, collector, interval=5):
        self._data = None
        self._data_lock = Lock()
        self._interval = interval
        self._collector_function = collector
        self._collector_thread = DaemonThread(name='{0}coll'.format(name),
                                              target=self._collect,
                                              interval=interval)

    def start(self):
        self._collector_thread.start()

    def _collect(self):
        data = self._collector_function()
        with self._data_lock:
            self._data = data

    @property
    def data(self):
        with self._data_lock:
            data = self._data
            self._data = None
        return data


class DebugDumpDataCollector(DataCollector):
    def __init__(self):
        super(DebugDumpDataCollector, self).__init__(name='debug dumps',
                                                     collector=self._collect_debug_dumps,
                                                     interval=60)
        self._timestamps_to_clear = []  # type: List[float]

    def clear(self, references):  # type: (Optional[List[float]]) -> None
        if references is not None:
            self._timestamps_to_clear = references

    def _collect_debug_dumps(self):  # type: () -> Tuple[Dict[str, Dict[float, Dict]], List[float]]
        raw_dumps = self._get_debug_dumps()
        data = {'dumps': {},
                'dump_info': {k: v.get('info', {})
                              for k, v in raw_dumps.items()}}  # type: Dict[str, Dict[float, Dict]]
        if Config.get_entry('cloud_support', False):
            # Include full dumps when support is enabled
            data['dumps'] = raw_dumps
        return data, list(raw_dumps.keys())

    def _get_debug_dumps(self):  # type: () -> Dict[float, Dict]
        debug_data = {}
        for filename in glob.glob('/tmp/debug_*.json'):
            timestamp = os.path.getmtime(filename)
            if timestamp in self._timestamps_to_clear:
                # Remove if requested
                try:
                    os.remove(filename)
                except Exception as ex:
                    logger.error('Could not remove debug file {0}: {1}'.format(filename, ex))
            elif timestamp not in debug_data:
                # Load if not yet loaded
                with open(filename, 'r') as debug_file:
                    try:
                        debug_data[timestamp] = json.load(debug_file)
                    except ValueError as ex:
                        logger.warning('Error parsing crash dump: {0}'.format(ex))
        return debug_data


class TaskExecutor(object):
    @Inject
    def __init__(self, cloud=None, message_client=INJECTED):
        self._configuration = {}
        self._intervals = {}
        self._online = False
        self._vpn_open = False
        self._vpn_retries = 0
        self._cloud = cloud
        self._message_client = message_client
        self._vpn_controller = VpnController()
        self._tasks = deque()
        self._previous_amount_of_tasks = 0
        self._executor = DaemonThread(name='taskexecutor',
                                      target=self.execute_tasks,
                                      interval=300)

    def start(self):
        self._vpn_controller.start()
        self._executor.start()

    def set_new_tasks(self, task_data):
        self._tasks.appendleft(task_data)
        self._executor.request_single_run()

    @property
    def vpn_open(self):
        return self._vpn_open

    def execute_tasks(self):
        while True:
            try:
                task_data = self._tasks.pop()
            except IndexError:
                return

            amount_of_tasks = len(task_data)
            if self._previous_amount_of_tasks != amount_of_tasks:
                logger.info('Processing {0} tasks...'.format(amount_of_tasks))

            if 'configuration' in task_data:
                self._process_configuration_data(task_data['configuration'])
            if 'intervals' in task_data:
                self._process_interval_data(task_data['intervals'])
            if 'connectivity' in task_data:
                self._check_connectivity(task_data['connectivity'])
            if self._online:
                if 'open_vpn' in task_data:
                    self._open_vpn(task_data['open_vpn'])
                if 'update_certs' in task_data:
                    self._rotate_client_certificates(task_data['update_certs'])
            if 'events' in task_data and self._message_client is not None:
                for event in task_data['events']:
                    try:
                        self._message_client.send_event(event[0], event[1])
                    except Exception as ex:
                        logger.error('Could not send event {0}({1}): {2}'.format(event[0], event[1], ex))

            if self._previous_amount_of_tasks != amount_of_tasks:
                logger.info('Processing {0} tasks... Done'.format(amount_of_tasks))
                self._previous_amount_of_tasks = amount_of_tasks

    def _process_configuration_data(self, configuration):
        try:
            configuration_changed = self._configuration != configuration
            if configuration_changed:
                for setting, value in configuration.items():
                    Config.set_entry(setting, value)
                logger.info('Configuration changed: {0}'.format(configuration))
            self._configuration = configuration
        except Exception:
            logger.exception('Unexpected exception processing configuration data')

    def _process_interval_data(self, intervals):
        try:
            intervals_changed = self._intervals != intervals
            if intervals_changed and self._message_client is not None:
                self._message_client.send_event(OMBusEvents.METRICS_INTERVAL_CHANGE, intervals)
                logger.info('Intervals changed: {0}'.format(intervals))
            self._intervals = intervals
        except Exception:
            logger.exception('Unexpected exception processing interval data')

    def _open_vpn(self, should_open):
        try:
            is_running = VpnController.check_vpn()
            if should_open:
                rollback = False
                if self._vpn_controller.connected:
                    self._vpn_retries = 0
                elif self._vpn_retries < 5:
                    logger.info('Waiting for VPN connection...')
                    self._vpn_retries += 1
                else:
                    rollback = True
                    self._vpn_retries += 1

                files = CertificateFiles()
                changed = files.activate_vpn(rollback=rollback)
                if changed:
                    self._vpn_retries = 0
                    VpnController.stop_vpn()
                    VpnController.start_vpn()

            if should_open and not is_running:
                logger.info('Opening vpn...')
                VpnController.start_vpn()
                logger.info('Opening vpn... Done')
            elif not should_open and is_running:
                logger.info('Closing vpn...')
                VpnController.stop_vpn()
                logger.info('Closing vpn... Done')
            is_running = VpnController.check_vpn()

            self._vpn_open = is_running and self._vpn_controller.connected
            if self._message_client is not None:
                self._message_client.send_event(OMBusEvents.VPN_OPEN, self._vpn_open)
        except Exception:
            logger.exception('Unexpected exception opening/closing VPN')

    def _rotate_client_certificates(self, should_update):
        try:
            if should_update:
                logger.info('Rotating client certificates...')

                if self._cloud.confirm_client_certs():
                    logger.info('Confirmed existing client certificates')
                    return

                files = CertificateFiles()
                files.setup_links()
                files.cleanup_versions()
                data = self._cloud.issue_client_certs()
                target = datetime.now().strftime('%Y%m%d%H%M')
                files.setup_certs(target, data)

                logger.info('Validating client certificates...')
                confirmed = self._cloud.confirm_client_certs(key_path=files.cert_path(target, 'client.key'))
                try:
                    if confirmed:
                        files.activate(target)
                        self._cloud.authenticate(raise_exception=True)
                except Exception:
                    files.rollback()
                    self._cloud.authenticate(raise_exception=True)

                logger.info('Rotating client certificates... done')
        except Exception:
            logger.exception('Unexpected exception rotating certificates')

    def _check_connectivity(self, last_successful_heartbeat):
        # type: (Optional[float]) -> None
        try:
            if last_successful_heartbeat is not None and last_successful_heartbeat > time.time() - CHECK_CONNECTIVITY_TIMEOUT:
                if not self._online:
                    logger.info('Connectivity changed: heartbeat=ok')
                    self._online = True
                if self._message_client is not None:
                    self._message_client.send_event(OMBusEvents.CONNECTIVITY, True)
            else:
                connectivity = TaskExecutor._has_connectivity()
                if connectivity != self._online:
                    logger.info('Connectivity changed: connectivity=%s', connectivity)
                    self._online = False
                if self._message_client is not None:
                    self._message_client.send_event(OMBusEvents.CONNECTIVITY, connectivity)
                if not connectivity and last_successful_heartbeat is not None and last_successful_heartbeat < time.time() - REBOOT_TIMEOUT:
                    subprocess.call('sync && reboot', shell=True)
        except Exception:
            logger.exception('Unexpected exception checking connectivity')

    @staticmethod
    def _ping(target, verbose=True):
        """ Check if the target can be pinged. Returns True if at least 1/4 pings was successful. """
        if target is None:
            return False

        # The popen_timeout has been added as a workaround for the hanging subprocess
        # If NTP date changes the time during a execution of a sub process this hangs forever.
        def popen_timeout(command, timeout):
            ping_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            for _ in range(timeout):
                time.sleep(1)
                if ping_process.poll() is not None:
                    stdout_data, stderr_data = ping_process.communicate()
                    if ping_process.returncode == 0:
                        return True
                    raise Exception('Non-zero exit code. Stdout: {0}, stderr: {1}'.format(stdout_data, stderr_data))
            logger.warning('Got timeout during ping to {0}. Killing'.format(target))
            ping_process.kill()
            del ping_process  # Make sure to clean up everything (or make it cleanable by the GC)
            logger.info('Ping to {0} killed'.format(target))
            return False

        if verbose is True:
            logger.info('Testing ping to {0}'.format(target))
        try:
            # Ping returns status code 0 if at least 1 ping is successful
            return popen_timeout(['ping', '-c', '3', target], 10)
        except Exception as ex:
            logger.error('Error during ping: {0}'.format(ex))
            return False

    @staticmethod
    def _has_connectivity():
        # Check connectivity by using ping to recover from a messed up network stack on the BeagleBone
        # Prefer using OpenMotics infrastructure first

        if TaskExecutor._ping('cloud.openmotics.com'):
            # OpenMotics infrastructure can be pinged
            # > Connectivity
            return True
        can_ping_internet_by_fqdn = TaskExecutor._ping('example.com') or TaskExecutor._ping('google.com')
        if can_ping_internet_by_fqdn:
            # Public internet servers can be pinged by FQDN
            # > Assume maintenance on OpenMotics infrastructure. Sufficient connectivity
            return True
        can_ping_internet_by_ip = TaskExecutor._ping('8.8.8.8') or TaskExecutor._ping('1.1.1.1')
        if can_ping_internet_by_ip:
            # Public internet servers can be pinged by IP, but not by FQDN
            # > Assume DNS resolving issues. Insufficient connectivity
            return False
        # Public internet servers cannot be pinged by IP, nor by FQDN
        can_ping_default_gateway = TaskExecutor._ping(TaskExecutor._get_default_gateway())
        if can_ping_default_gateway:
            # > Assume ISP outage. Sufficient connectivity
            return True
        # > Assume broken TCP stack. No connectivity
        return False

    @staticmethod
    def _get_default_gateway():
        """ Get the default gateway. """
        try:
            return subprocess.check_output("ip r | grep '^default via' | awk '{ print $3; }'", shell=True)
        except Exception as ex:
            logger.error('Error during get_gateway: {0}'.format(ex))
            return


class HeartbeatService(object):
    @Inject
    def __init__(self, url=None, uuid=None, message_client=INJECTED):
        # type: (Optional[str], Optional[str], MessageClient) -> None
        config = ConfigParser()
        config.read(constants.get_config_file())

        self._message_client = message_client
        if self._message_client is not None:
            self._message_client.set_state_handler(self._check_state)
            self._message_client.add_event_handler(self._handle_event)

        self._last_successful_heartbeat = None  # type: Optional[float]
        self._last_cycle = 0.0
        self._cloud_enabled = True
        self._sleep_time = 0.0
        self._previous_sleep_time = 0.0
        self._gateway = Gateway()
        self._cloud = Cloud(url=url, uuid=uuid)
        self._task_executor = TaskExecutor(self._cloud)

        # Obsolete keys (do not use them, as they are still processed for legacy gateways):
        # `outputs`, `update`, `energy`, `pulse_totals`, `'thermostats`, `inputs`, `shutters`
        self._collectors = {'errors': DataCollector('errors', self._gateway.get_errors, 600),
                            'local_ip': DataCollector('ip address', System.get_ip_address, 1800)}
        self._debug_collector = DebugDumpDataCollector()

    @staticmethod
    def _handle_signal_alarm(signum, frame):
        logger.error('Signal alarm ({0}) triggered:\n{1}'.format(signum, (''.join(traceback.format_stack(frame))).strip()))
        logger.error('Exit(1)')
        os._exit(1)

    def _check_state(self):
        return {'cloud_disabled': not self._cloud_enabled,
                'cloud_last_connect': None if not self._cloud_enabled else self._last_successful_heartbeat,
                'sleep_time': self._sleep_time,
                'vpn_open': self._task_executor.vpn_open,
                'last_cycle': self._last_cycle}

    def _handle_event(self, event, payload):
        _ = self, payload
        if event == OMBusEvents.TIME_CHANGED:
            time.tzset()  # Refresh timezone
            logger.info('Timezone changed to {0}'.format(time.tzname[0]))

    def start(self):
        # type: () -> None
        self._task_executor.start()
        self._debug_collector.start()
        for collector in self._collectors.values():
            collector.start()

    def run(self):
        # type: () -> None
        signal.signal(signal.SIGALRM, HeartbeatService._handle_signal_alarm)
        while True:
            self._last_cycle = time.time()
            try:
                signal.alarm(600)  # 10 minutes
                start_time = time.time()
                call_home_duration = self.heartbeat()
                beat_time = time.time() - start_time
                if beat_time > 2:
                    logger.warning('Heartbeat took {0:.2f}s to complete, of which the call home took {1:.2f}s'.format(beat_time, call_home_duration))
                if self._previous_sleep_time != self._sleep_time:
                    logger.info('Set sleep interval to {0}s'.format(self._sleep_time))
                    self._previous_sleep_time = self._sleep_time
                signal.alarm(0)
                time.sleep(self._sleep_time)
            except Exception as ex:
                logger.error("Error during vpn check loop: {0}".format(ex))
                time.sleep(5)

    def heartbeat(self):  # type: () -> float
        # Check whether connection to the Cloud is enabled/disabled
        self._cloud_enabled = Config.get_entry('cloud_enabled', False)
        if self._cloud_enabled is False:
            self._sleep_time = DEFAULT_SLEEP_TIME
            task_data = {'open_vpn': False,
                         'update_certs': False,
                         'events': [(OMBusEvents.VPN_OPEN, False),
                                    (OMBusEvents.CLOUD_REACHABLE, False)]}
            self._task_executor.set_new_tasks(task_data=task_data)
            return 0.0

        # Load collected data from async collectors
        call_data = {}  # type: Dict[str, Dict[str, Any]]
        for collector_key in self._collectors:
            collector = self._collectors[collector_key]
            data = collector.data
            if data is not None:
                call_data[collector_key] = data

        # Load debug data
        debug_data = self._debug_collector.data
        debug_references = None  # type: Optional[List[float]]
        if debug_data is not None:
            call_data['debug'], debug_references = debug_data

        # Send data to the cloud and load response
        call_home_start = time.time()
        response = self._cloud.call_home(call_data)
        call_home_duration = time.time() - call_home_start
        call_home_successful = response.get('success', False)
        self._sleep_time = response.get('sleep_time', DEFAULT_SLEEP_TIME)

        if call_home_successful:
            self._last_successful_heartbeat = time.time()
            self._debug_collector.clear(debug_references)

        # Gather tasks to be executed
        task_data = {'events': [(OMBusEvents.CLOUD_REACHABLE, call_home_successful)],
                     'open_vpn': response.get('open_vpn', True),
                     'update_certs': response.get('update_certs', False),
                     'connectivity': self._last_successful_heartbeat}
        for entry in ['configuration', 'intervals']:
            if entry in response:
                task_data[entry] = response[entry]
        self._task_executor.set_new_tasks(task_data=task_data)
        return call_home_duration


def main():
    Logs.setup_logger()
    setup_minimal_vpn_platform(message_client_name='vpn_service')

    logger.info('Starting VPN service')
    heartbeat_service = HeartbeatService()
    heartbeat_service.start()
    heartbeat_service.run()


if __name__ == '__main__':
    main()
