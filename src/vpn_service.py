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

from platform_utils import System
System.import_libs()

import glob
import logging
import os
import subprocess
import time
import requests
import six
import ujson as json
from collections import deque
from six.moves.configparser import ConfigParser
from threading import Lock

import constants
from bus.om_bus_client import MessageClient
from bus.om_bus_events import OMBusEvents
from gateway.daemon_thread import DaemonThread
from gateway.initialize import initialize
from gateway.models import Config
from ioc import INJECTED, Inject

if False:  # MYPY
    from typing import Any, Dict, Optional, List, Tuple

REBOOT_TIMEOUT = 900
CHECK_CONNECTIVITY_TIMEOUT = 60
DEFAULT_SLEEP_TIME = 30.0

logger = logging.getLogger('openmotics')


def setup_logger():
    """ Setup the OpenMotics logger. """
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


class VpnController(object):
    """ Contains methods to check the vpn status, start and stop the vpn. """

    vpn_service = System.get_vpn_service()
    start_cmd = 'systemctl start {0} > /dev/null'.format(vpn_service)
    stop_cmd = 'systemctl stop {0} > /dev/null'.format(vpn_service)
    check_cmd = 'systemctl is-active {0} > /dev/null'.format(vpn_service)

    def __init__(self):
        self.vpn_connected = False
        self._vpn_tester = DaemonThread(name='vpn controller',
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
                vpn_servers = [route.split(' ')[0] for route in routes.split('\n') if '/' not in route]
                for vpn_server in vpn_servers:
                    if TaskExecutor._ping(vpn_server, verbose=False):
                        result = True
                        break
            self.vpn_connected = result
        except Exception as ex:
            logger.info('Exception occured during vpn connectivity test: {0}'.format(ex))
            self.vpn_connected = False


class Cloud(object):
    """ Connects to the cloud """

    def __init__(self, url=None):
        self._url = url
        if self._url is None:
            config = ConfigParser()
            config.read(constants.get_config_file())
            self._url = config.get('OpenMotics', 'vpn_check_url') % config.get('OpenMotics', 'uuid')

    def call_home(self, extra_data):
        """ Call home reporting our state, and optionally get new settings or other stuff """
        try:
            request = requests.post(self._url,
                                    data={'extra_data': json.dumps(extra_data)},
                                    timeout=10.0)
            response = json.loads(request.text)
            data = {'success': True}
            for entry in ['sleep_time', 'open_vpn', 'configuration', 'intervals']:
                if entry in response:
                    data[entry] = response[entry]
            return data
        except Exception:
            logger.exception('Exception occured during call home')
            return {'success': False}


class Gateway(object):
    """ Class to get the current status of the gateway. """

    def __init__(self, host="127.0.0.1"):
        self._host = host

    def do_call(self, uri):
        """ Do a call to the webservice, returns a dict parsed from the json returned by the webserver. """
        try:
            request = requests.get('http://{0}/{1}'.format(self._host, uri), timeout=5.0)
            return json.loads(request.text)
        except Exception as ex:
            message = str(ex)
            if 'Connection refused' in message:
                logger.warning('Cannot connect to the OpenMotics service')
            else:
                logger.error('Exception during Gateway call {0}: {1}'.format(uri, message))
            return

    def get_outputs_status(self):
        data = self.do_call('get_output_status?token=None')
        if data is None or data['success'] is False:
            return None
        ret = []
        for output in data['status']:
            parsed_data = {}
            for k in output.keys():
                if k in ['id', 'status', 'dimmer', 'locked']:
                    parsed_data[k] = output[k]
            ret.append(parsed_data)
        return ret

    def get_inputs_status(self):
        """ Get the inputs status. """
        data = self.do_call('get_input_status?token=None')
        if data is None or data['success'] is False:
            return None
        return [(inp["id"], inp["status"]) for inp in data['status']]

    def get_shutters_status(self):
        """ Get the shutters status. """
        data = self.do_call('get_shutter_status?token=None')
        if data is None or data['success'] is False:
            return None
        return_data = []
        for shutter_id, details in six.iteritems(data['detail']):
            last_change = details['last_change']
            if last_change == 0.0:
                entry = (int(shutter_id), details['state'].upper())
            else:
                entry = (int(shutter_id), details['state'].upper(), last_change)
            return_data.append(entry)
        return return_data

    def get_thermostats(self):
        """ Fetch the setpoints for the enabled thermostats from the webservice. """
        data = self.do_call('get_thermostat_status?token=None')
        if data is None or data['success'] is False:
            return None
        ret = {'thermostats_on': data['thermostats_on'],
               'automatic': data['automatic'],
               'cooling': data['cooling']}
        thermostats = []
        for thermostat in data['status']:
            to_add = {}
            for field in ['id', 'act', 'csetp', 'mode', 'output0', 'output1', 'outside', 'airco']:
                to_add[field] = thermostat[field]
            thermostats.append(to_add)
        ret['status'] = thermostats
        return ret

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


class DataCollector(object):
    def __init__(self, name, collector, interval=5):
        self._data = None
        self._data_lock = Lock()
        self._interval = interval
        self._collector_function = collector
        self._collector_thread = DaemonThread(name='{0} collector'.format(name),
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
        self._timestamps_to_clear = references if references is not None else []

    def _collect_debug_dumps(self):  # type: () -> Tuple[Dict[str, Dict[float, Dict]], List[float]]
        raw_dumps = self._get_debug_dumps()
        data = {'dumps': {},
                'dump_info': {k: v.get('info', {})
                              for k, v in raw_dumps.items()}}  # type: Dict[str, Dict[float, Dict]]
        if Config.get('cloud_support', False):
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
    def __init__(self, message_client=INJECTED):
        self._configuration = {}
        self._intervals = {}
        self._vpn_open = False
        self._message_client = message_client
        self._vpn_controller = VpnController()
        self._tasks = deque()
        self._executor = DaemonThread(name='task executor',
                                      target=self._execute_tasks,
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

    def _execute_tasks(self):
        while True:
            try:
                task_data = self._tasks.pop()
            except IndexError:
                return

            logger.info('Processing tasks...')
            if 'configuration' in task_data:
                self._process_configuration_data(task_data['configuration'])
            if 'intervals' in task_data:
                self._process_interval_data(task_data['intervals'])
            if 'open_vpn' in task_data:
                self._open_vpn(task_data['open_vpn'])
            if 'events' in task_data and self._message_client is not None:
                for event in task_data['events']:
                    try:
                        self._message_client.send_event(event[0], event[1])
                    except Exception as ex:
                        logger.error('Could not send event {0}({1}): {2}'.format(event[0], event[1], ex))
            if 'connectivity' in task_data:
                self._check_connectivity(task_data['connectivity'])
            logger.info('Processing tasks... Done')

    def _process_configuration_data(self, configuration):
        try:
            configuration_changed = cmp(self._configuration, configuration) != 0
            if configuration_changed:
                for setting, value in configuration.items():
                    Config.set(setting, value)
                logger.info('Configuration changed: {0}'.format(configuration))
            self._configuration = configuration
        except Exception:
            logger.exception('Unexpected exception processing configuration data')

    def _process_interval_data(self, intervals):
        try:
            intervals_changed = cmp(self._intervals, intervals) != 0
            if intervals_changed and self._message_client is not None:
                self._message_client.send_event(OMBusEvents.METRICS_INTERVAL_CHANGE, intervals)
                logger.info('Intervals changed: {0}'.format(intervals))
            self._intervals = intervals
        except Exception:
            logger.exception('Unexpected exception processing interval data')

    def _open_vpn(self, should_open):
        try:
            is_running = VpnController.check_vpn()
            if should_open and not is_running:
                logger.info('Opening vpn...')
                VpnController.start_vpn()
                logger.info('Opening vpn... Done')
            elif not should_open and is_running:
                logger.info('Closing vpn...')
                VpnController.stop_vpn()
                logger.info('Closing vpn... Done')
            is_running = VpnController.check_vpn()
            self._vpn_open = is_running and self._vpn_controller.vpn_connected
            if self._message_client is not None:
                self._message_client.send_event(OMBusEvents.VPN_OPEN, self._vpn_open)
        except Exception:
            logger.exception('Unexpected exception opening/closing VPN')

    def _check_connectivity(self, last_successful_heartbeat):
        try:
            if last_successful_heartbeat > time.time() - CHECK_CONNECTIVITY_TIMEOUT:
                if self._message_client is not None:
                    self._message_client.send_event(OMBusEvents.CONNECTIVITY, True)
            else:
                connectivity = TaskExecutor._has_connectivity()
                if self._message_client is not None:
                    self._message_client.send_event(OMBusEvents.CONNECTIVITY, connectivity)
                if not connectivity and last_successful_heartbeat < time.time() - REBOOT_TIMEOUT:
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
            p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for _ in range(timeout):
                time.sleep(1)
                if p.poll() is not None:
                    stdout_data, stderr_data = p.communicate()
                    if p.returncode == 0:
                        return True
                    raise Exception('Non-zero exit code. Stdout: {0}, stderr: {1}'.format(stdout_data, stderr_data))
            logger.warning('Got timeout during ping to {0}. Killing'.format(target))
            p.kill()
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
    def __init__(self, url=None, message_client=INJECTED):
        # type: (Optional[str], MessageClient) -> None
        config = ConfigParser()
        config.read(constants.get_config_file())

        self._message_client = message_client
        if self._message_client is not None:
            self._message_client.set_state_handler(self._check_state)

        self._last_successful_heartbeat = None  # type: Optional[float]
        self._last_cycle = 0.0
        self._cloud_enabled = True
        self._sleep_time = 0.0
        self._previous_sleep_time = 0.0
        self._gateway = Gateway()
        self._cloud = Cloud(url=url)
        self._task_executor = TaskExecutor()

        # Obsolete keys (do not use them, as they are still processed for legacy gateways):
        # `outputs`, `update`, `energy`, `pulse_totals`
        self._collectors = {'thermostats': DataCollector('thermostats', self._gateway.get_thermostats, 60),
                            'inputs': DataCollector('inputs', self._gateway.get_inputs_status),
                            'outputs_status': DataCollector('outputs_status', self._gateway.get_outputs_status),
                            'shutters': DataCollector('shutters', self._gateway.get_shutters_status),
                            'errors': DataCollector('errors', self._gateway.get_errors, 600),
                            'local_ip': DataCollector('ip address', System.get_ip_address, 1800)}
        self._debug_collector = DebugDumpDataCollector()

    def _check_state(self):
        return {'cloud_disabled': not self._cloud_enabled,
                'cloud_last_connect': None if not self._cloud_enabled else self._last_successful_heartbeat,
                'sleep_time': self._sleep_time,
                'vpn_open': self._task_executor.vpn_open,
                'last_cycle': self._last_cycle}

    def start(self):
        # type: () -> None
        self._task_executor.start()
        self._debug_collector.start()
        for collector in self._collectors.values():
            collector.start()

    def run_heartbeat(self):
        # type: () -> None
        while True:
            self._last_cycle = time.time()
            try:
                start_time = time.time()

                self._beat()

                exec_time = time.time() - start_time
                if exec_time > 2:
                    logger.warning('Heartbeat took more than 2s to complete: {0:.2f}s'.format(exec_time))
                if self._previous_sleep_time != self._sleep_time:
                    logger.info('Set sleep interval to {0}s'.format(self._sleep_time))
                    self._previous_sleep_time = self._sleep_time
                time.sleep(self._sleep_time)
            except Exception as ex:
                logger.error("Error during vpn check loop: {0}".format(ex))
                time.sleep(5)

    def _beat(self):
        # Check whether connection to the Cloud is enabled/disabled
        self._cloud_enabled = Config.get('cloud_enabled')
        if self._cloud_enabled is False:
            self._sleep_time = DEFAULT_SLEEP_TIME
            task_data = {'open_vpn': False,
                         'events': [(OMBusEvents.VPN_OPEN, False),
                                    (OMBusEvents.CLOUD_REACHABLE, False)]}
            self._task_executor.set_new_tasks(task_data=task_data)
            return

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
        response = self._cloud.call_home(call_data)
        call_home_successful = response.get('success', False)
        self._sleep_time = response.get('sleep_time', DEFAULT_SLEEP_TIME)

        if call_home_successful:
            self._last_successful_heartbeat = time.time()
            self._debug_collector.clear(debug_references)

        # Gather tasks to be executed
        task_data = {'events': [(OMBusEvents.CLOUD_REACHABLE, call_home_successful)],
                     'open_vpn': response.get('open_vpn', True),
                     'connectivity': self._last_successful_heartbeat}
        for entry in ['configuration', 'intervals']:
            if entry in response:
                task_data[entry] = response[entry]
        self._task_executor.set_new_tasks(task_data=task_data)


if __name__ == '__main__':
    setup_logger()
    initialize(message_client_name='vpn_service')

    logger.info('Starting VPN service')
    heartbeat_service = HeartbeatService()
    heartbeat_service.start()
    heartbeat_service.run_heartbeat()
