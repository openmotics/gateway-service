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
from __future__ import absolute_import

import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime

import hypothesis
import requests
import ujson as json
from requests.exceptions import ConnectionError, RequestException

from tests.hardware import INPUT_MODULE_LAYOUT, Input, Output

logger = logging.getLogger('openmotics')

if False:  # MYPY
    from typing import Any, Dict, List, Optional, Tuple


class Client(object):
    def __init__(self, host, auth=None):
        # type: (str, List[str]) -> None
        self._host = host
        self._auth = auth
        self._default_kwargs = {'verify': False}
        self._token = None  # type: Optional[str]

    @property
    def token(self):
        # type: () -> Optional[str]
        if self._token is None:
            self._token = self.login()
        return self._token

    def login(self, success=True, timeout=30):
        # type: (bool, float) -> Optional[str]
        if self._auth:
            self._token = None
            params = {'username': self._auth[0], 'password': self._auth[1], 'accept_terms': True}
            data = self.get('/login', params=params, use_token=False, success=success, timeout=timeout)
            if 'token' in data:
                return data['token']
            else:
                raise Exception('unexpected response {}'.format(data))
        else:
            return None

    def get(self, path, params=None, success=True, use_token=True, timeout=30):
        # type: (str, Dict[str,Any], bool, bool, float) -> Any
        params = params or {}
        headers = requests.utils.default_headers()
        uri = 'https://{}{}'.format(self._host, path)
        if use_token:
            headers['Authorization'] = 'Bearer {}'.format(self.token)
            logger.debug('GET {} {}'.format(path, params))

        job_name = os.getenv('JOB_NAME')
        build_number = os.getenv('BUILD_NUMBER')
        if job_name and build_number:
            headers['User-Agent'] += ' {}/{}'.format(job_name, build_number)
        _, _, current_test = os.getenv('PYTEST_CURRENT_TEST', '').rpartition('::')
        if current_test:
            headers['User-Agent'] += ' pytest/{}'.format(current_test)

        since = time.time()
        while since > time.time() - timeout:
            try:
                response = requests.get(uri, params=params, headers=headers, **self._default_kwargs)
                assert response.status_code != 404, 'not found {}'.format(path)
                data = response.json()
                if success and 'success' in data:
                    assert data['success'], 'content={}'.format(response.content.decode())
                return data
            except (ConnectionError, RequestException) as exc:
                logger.debug('request {} failed {}, retrying...'.format(path, exc))
                time.sleep(16)
                pass
        raise AssertionError('request {} failed after {:.2f}s'.format(path, time.time() - since))


class TesterGateway(object):
    def __init__(self, client):
        # type: (Client) -> None
        self._client = client
        self._last_received_at = 0.0
        self._last_data = {}  # type: Dict[str,Any]
        self._outputs = {}  # type: Dict[int,bool]
        self.update_events()

    def get_last_outputs(self):
        # type: () -> List[str]
        if self._last_data:
            outputs = self._last_data['events'][-1]['outputs']
            return ['?' if x is None else str(x) for x in outputs]
        else:
            return []

    def get(self, path, params=None, success=True, use_token=True):
        # type: (str, Dict[str,Any], bool, bool) -> Any
        return self._client.get(path, params=params, success=success, use_token=use_token)

    def toggle_output(self, output_id, delay=0.2):
        self.get('/set_output', {'id': output_id, 'is_on': True})
        time.sleep(delay)
        self.get('/set_output', {'id': output_id, 'is_on': False})

    def log_events(self):
        # type: () -> None
        for event in (x for x in self._last_data['events'] if 'output_id' in x):
            received_at, output_id, output_status, outputs = (event['received_at'], event['output_id'], event['output_status'], event['outputs'])
            timestamp = datetime.fromtimestamp(received_at).strftime('%y-%m-%d %H:%M:%S,%f')
            state = ' '.join('?' if x is None else str(x) for x in outputs)
            logger.error('{} received event {} -> {}    outputs={}'.format(timestamp, output_id, output_status, state))

    def update_events(self):
        # type: () -> bool
        data = self.get('/plugins/event_observer/events')
        self._last_data = data
        changed = False
        for event in (x for x in self._last_data['events'] if 'output_id' in x):
            received_at, output_id, output_status = (event['received_at'], event['output_id'], event['output_status'])
            if received_at >= self._last_received_at:
                changed = True
                self._last_received_at = received_at
                self._outputs[output_id] = bool(output_status)
        return changed

    def reset(self):
        # type: () -> None
        self._outputs = {}

    def receive_output_event(self, output_id, output_status, between):
        # type: (int, bool, Tuple[float, float]) -> bool
        cooldown, deadline = between
        timeout = deadline - cooldown
        if cooldown > 0:
            logger.debug('waiting {:.2f}s before event'.format(cooldown))
            self.reset()
            time.sleep(cooldown)
        since = time.time()
        while since > time.time() - timeout:
            if output_id in self._outputs and output_status == self._outputs[output_id]:
                logger.debug('received event {} status={} after {:.2f}s'.format(output_id, self._outputs[output_id], time.time() - since))
                return True
            if self.update_events():
                continue
            time.sleep(0.2)
        logger.error('receive event {} status={}, timeout after {:.2f}s'.format(output_id, output_status, time.time() - since))
        self.log_events()
        return False


class Toolbox(object):
    DEBIAN_AUTHORIZED_MODE = 13  # tester_output_1.output_5
    DEBIAN_DISCOVER_INPUT = 14  # tester_output_1.output_6
    DEBIAN_DISCOVER_OUTPUT = 15  # tester_output_1.output_7
    DEBIAN_DISCOVER_UCAN = 22  # tester_output2.output_6
    DEBIAN_DISCOVER_ENERGY = 23  # tester_output2.output_7
    DEBIAN_POWER_OUTPUT = 8  # tester_output_1.output_0
    POWER_ENERGY_MODULE = 11  # tester_output_1.output_3

    def __init__(self):
        # type: () -> None
        self._tester = None  # type: Optional[TesterGateway]
        self._dut = None  # type: Optional[Client]
        self._dut_energy_cts = None  # type: Optional[List[Tuple[int, int]]]

    @property
    def tester(self):
        # type: () -> TesterGateway
        if self._tester is None:
            tester_auth = os.environ['OPENMOTICS_TESTER_AUTH'].split(':')
            tester_host = os.environ['OPENMOTICS_TESTER_HOST']
            self._tester = TesterGateway(Client(tester_host, auth=tester_auth))
        return self._tester

    @property
    def dut(self):
        # type: () -> Client
        if self._dut is None:
            dut_auth = os.environ['OPENMOTICS_DUT_AUTH'].split(':')
            dut_host = os.environ['OPENMOTICS_DUT_HOST']
            self._dut = Client(dut_host, auth=dut_auth)
        return self._dut

    @property
    def dut_energy_cts(self):
        if self._dut_energy_cts is None:
            cts = []
            energy_modules = self.list_energy_modules(module_type='E')
            for module in energy_modules:
                cts += [(module['id'], input_id) for input_id in range(12)]
            self._dut_energy_cts = cts
        return self._dut_energy_cts

    def initialize(self):
        # type: () -> None
        logger.info('checking prerequisites')
        self.ensure_power_on()
        try:
            self.dut.login(success=False)
        except Exception:
            logger.info('initializing gateway...')
            self.authorized_mode_start()
            self.create_or_update_user()
            self.dut.login()
        try:
            self.list_modules('O')
            self.list_modules('I')
        except Exception:
            logger.info('discovering modules...')
            self.discover_output_module()
            self.discover_input_module()

        # TODO compare with hardware modules instead.
        self.list_modules('O')
        self.list_modules('I')

        try:
            self.get_module('o')
        except Exception:
            logger.info('adding virtual modules...')
            self.dut.get('/add_virtual_output')
            time.sleep(2)
        self.get_module('o')

    def print_logs(self):
        # type: () -> None
        try:
            data = self.tester.get('/plugins/syslog_receiver/logs', success=False)
            for log in data['logs']:
                print(log)
        except Exception:
            print('Failed to retrieve logs')

    def factory_reset(self, confirm=True):
        # type: (bool) -> Dict[str,Any]
        assert self.dut._auth
        logger.debug('factory reset')
        params = {'username': self.dut._auth[0], 'password': self.dut._auth[1], 'confirm': confirm}
        return self.dut.get('/factory_reset', params=params, success=confirm)

    def list_modules(self, module_type, min_modules=1):
        # type: (str, int) -> List[Dict[str,Any]]
        data = self.dut.get('/get_modules_information')
        modules = []
        for address, info in data['modules']['master'].items():
            if info['type'] != module_type or not info['firmware']:
                continue
            info['address'] = address
            modules.append(info)
        assert len(modules) >= min_modules, 'Not enough modules of type \'{}\' available in {}'.format(module_type, data)
        return modules

    def list_energy_modules(self, module_type, min_modules=1):
        # type: (str, int) -> List[Dict[str, Any]]
        data = self.dut.get('/get_modules_information')
        modules = []
        for address, info in data['modules']['energy'].items():
            if info['type'] != module_type or not info['firmware']:
                continue
            modules.append(info)
        assert len(modules) >= min_modules, 'Not enough energy modules of type \'{}\' available in {}'.format(module_type, data)
        return modules

    def get_module(self, module_type):
        # type: (str) -> List[int]
        data = self.dut.get('/get_modules')
        modules = list(enumerate(data['outputs'])) + list(enumerate(data['inputs'])) + list(enumerate(data['can_inputs']))
        for i, v in modules:
            if v == module_type:
                return list(range(8 * i, (8 * i) + 7))
        raise AssertionError('No modules of type \'{}\' available in {}'.format(module_type, data))

    def authorized_mode_start(self):
        # type: () -> None
        logger.debug('start authorized mode')
        self.tester.toggle_output(self.DEBIAN_AUTHORIZED_MODE, delay=15)

    def authorized_mode_stop(self, timeout=240):
        # type: (float) -> None
        self.tester.toggle_output(self.DEBIAN_AUTHORIZED_MODE)

    def create_or_update_user(self, success=True):
        # type: (bool) -> None
        logger.info('create or update test user')
        assert self.dut._auth
        user_data = {'username': self.dut._auth[0], 'password': self.dut._auth[1]}
        self.dut.get('/create_user', params=user_data, use_token=False, success=success)

    def module_discover_start(self):
        # type: () -> None
        logger.debug('start module discover')
        self.dut.get('/module_discover_start')
        for _ in range(10):
            data = self.dut.get('/module_discover_status')
            if data['running']:
                return
            time.sleep(0.2)

    def module_discover_stop(self):
        # type: () -> None
        logger.debug('stop module discover')
        self.dut.get('/module_discover_stop')

    def discover_output_module(self):
        # type: () -> None
        logger.debug('discover output module')
        self.module_discover_start()
        self.tester.toggle_output(self.DEBIAN_DISCOVER_OUTPUT)
        self.assert_modules(1)
        self.module_discover_stop()

    def discover_input_module(self):
        # type: () -> None
        logger.debug('discover input module')
        self.module_discover_start()
        self.tester.toggle_output(self.DEBIAN_DISCOVER_INPUT)
        self.assert_modules(1)
        self.module_discover_stop()

    def discover_can_control(self):
        # type: () -> None
        logger.debug('discover CAN control')
        # TODO: discover CAN inputs
        self.module_discover_start()
        self.tester.toggle_output(self.DEBIAN_DISCOVER_UCAN)
        self.assert_modules(2, timeout=60)
        self.module_discover_stop()

    def assert_modules(self, count, timeout=30):
        # type: (int, float) -> List[List[str]]
        since = time.time()
        modules = []
        while since > time.time() - timeout:
            modules += self.dut.get('/get_module_log')['log']
            if len(modules) >= count:
                logger.debug('discovered {} modules, done'.format(count))
                return modules
            time.sleep(2)
        raise AssertionError('expected {} modules in {}'.format(count, modules))

    def discover_energy_modules(self):
        # type: () -> None
        self.press_input(self.DEBIAN_DISCOVER_ENERGY)

    def power_off(self):
        # type: () -> None
        logger.debug('power off')
        self.tester.get('/set_output', {'id': self.DEBIAN_POWER_OUTPUT, 'is_on': False})
        time.sleep(2)

    def ensure_power_on(self):
        # type: () -> None
        if not self.health_check(timeout=0.2):
            return
        logger.info('power on')
        self.tester.get('/set_output', {'id': self.DEBIAN_POWER_OUTPUT, 'is_on': True})
        logger.info('waiting for gateway api to respond...')
        self.health_check(timeout=300)
        logger.info('health check done')

    def power_cycle_module(self, output_id, delay=2.0):
        # type: (int, float) -> None
        self.tester.get('/set_output', {'id': output_id, 'is_on': False})
        time.sleep(delay)
        self.tester.get('/set_output', {'id': output_id, 'is_on': True})

    @contextmanager
    def disabled_self_recovery(self):
        try:
            self.dut.get('/set_self_recovery', {'active': False})
            yield self
        finally:
            self.dut.get('/set_self_recovery', {'active': True})

    def health_check(self, timeout=30):
        # type: (float) -> List[str]
        since = time.time()
        pending = ['unknown']
        while since > time.time() - timeout:
            try:
                data = self.dut.get('/health_check', use_token=False, timeout=timeout)
                pending = [k for k, v in data['health'].items() if not v['state']]
                if not pending:
                    return pending
                logger.debug('wait for health check, {}'.format(pending))
            except Exception:
                pass
            time.sleep(10)
        return pending

    def configure_output(self, output, config):
        # type: (Output, Dict[str,Any]) -> None
        config_data = {'id': output.output_id}
        config_data.update(**config)
        logger.debug('configure output {}#{} with {}'.format(output.type, output.output_id, config))
        self.dut.get('/set_output_configuration', {'config': json.dumps(config_data)})

    def ensure_output(self, output, status, config=None):
        # type: (Output, int, Optional[Dict[str,Any]]) -> None
        if config:
            self.configure_output(output, config)
        state = ' '.join(self.tester.get_last_outputs())
        hypothesis.note('ensure output {}#{} is {}'.format(output.type, output.output_id, status))
        logger.debug('ensure output {}#{} is {}    outputs={}'.format(output.type, output.output_id, status, state))
        time.sleep(0.2)
        self.set_output(output, status)
        self.tester.reset()

    def set_output(self, output, status):
        # type: (Output, int) -> None
        logger.debug('set output {}#{} -> {}'.format(output.type, output.output_id, status))
        self.dut.get('/set_output', {'id': output.output_id, 'is_on': status})

    def press_input(self, input):
        # type: (Input) -> None
        self.tester.get('/set_output', {'id': input.tester_output_id, 'is_on': False})  # ensure start status
        time.sleep(0.2)
        self.tester.reset()
        hypothesis.note('after input {}#{} pressed'.format(input.type, input.input_id))
        self.tester.toggle_output(input.tester_output_id)
        logger.debug('toggled {}#{} -> True -> False'.format(input.type, input.input_id))

    def assert_output_changed(self, output, status, between=(0, 30)):
        # type: (Output, bool, Tuple[float,float]) -> None
        hypothesis.note('assert output {}#{} status changed {} -> {}'.format(output.type, output.output_id, not status, status))
        if self.tester.receive_output_event(output.output_id, status, between=between):
            return
        raise AssertionError('expected event {}#{} status={}'.format(output.type, output.output_id, status))

    def assert_output_status(self, output, status, timeout=30):
        # type: (Output, bool, float) -> None
        hypothesis.note('assert output {}#{} status is {}'.format(output.type, output.output_id, status))
        since = time.time()
        current_status = None
        while since > time.time() - timeout:
            data = self.dut.get('/get_output_status')
            current_status = data['status'][output.output_id]['status']
            if status == bool(current_status):
                logger.debug('get output {}#{} status={}, after {:.2f}s'.format(output.type, output.output_id, status, time.time() - since))
                return
            time.sleep(2)
        state = ' '.join(self.tester.get_last_outputs())
        logger.error('get status {} status={} != expected {}, timeout after {:.2f}s    outputs={}'.format(output.output_id, bool(current_status), status, time.time() - since, state))
        self.tester.log_events()
        raise AssertionError('get status {} status={} != expected {}, timeout after {:.2f}s'.format(output.output_id, bool(current_status), status, time.time() - since))
