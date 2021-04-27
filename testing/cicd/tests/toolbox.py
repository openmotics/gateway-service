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
from requests.exceptions import ConnectionError, RequestException, Timeout

from tests.hardware_layout import INPUT_MODULE_LAYOUT, OUTPUT_MODULE_LAYOUT, \
    TEMPERATURE_MODULE_LAYOUT, TEST_PLATFORM, Input, Module, Output, \
    TestPlatform

logger = logging.getLogger('openmotics')

if False:  # MYPY
    from typing import Any, Dict, List, Optional, Tuple


class Client(object):
    def __init__(self, id, host, auth=None):
        # type: (str, str, List[str]) -> None
        self._id = id
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
        return self._request(requests.get, path, params=params,
                             success=success, use_token=use_token, timeout=timeout)

    def post(self, path, data=None, files=None, success=True, use_token=True, timeout=30):
        # type: (str, Dict[str,Any], Dict[str,Any], bool, bool, float) -> Any
        return self._request(requests.post, path, data=data, files=files,
                             success=success, use_token=use_token, timeout=timeout)

    def _request(self, f, path, params=None, data=None, files=None, success=True, use_token=True, timeout=30):
        # type: (Any, str, Dict[str,Any], Dict[str,Any], Dict[str,Any], bool, bool, float) -> Any
        params = params or {}
        headers = requests.utils.default_headers()
        uri = 'https://{}{}'.format(self._host, path)
        if use_token:
            headers['Authorization'] = 'Bearer {}'.format(self.token)
            logger.debug('GET {} {} {}'.format(self._id, path, params))

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
                response = f(uri, params=params, data=data, files=files,
                             headers=headers, **self._default_kwargs)
                assert response.status_code != 404, 'not found {}'.format(path)
                data = response.json()
                if success and 'success' in data:
                    assert data['success'], 'content={}'.format(response.content.decode())
                return data
            except (ConnectionError, RequestException) as exc:
                logger.debug('Request {} {} failed {}, retrying...'.format(self._id, path, exc))
                time.sleep(16)
                pass
        raise Timeout('Request {} {} failed after {:.2f}s'.format(self._id, path, time.time() - since))


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

    def toggle_output(self, output_id, delay=0.2, inverted=False, is_dimmer=False):
        self.toggle_outputs([output_id], delay=delay, inverted=inverted, is_dimmer=is_dimmer)

    def toggle_outputs(self, output_ids, delay=0.2, inverted=False, is_dimmer=False):
        temporarily_state = not inverted
        for output_id in output_ids:
            payload = {'id': output_id, 'is_on': temporarily_state}
            if is_dimmer and temporarily_state:
                payload['dimmer'] = 100
            self.get('/set_output', payload)
        time.sleep(delay)
        for output_id in output_ids:
            payload = {'id': output_id, 'is_on': not temporarily_state}
            if is_dimmer and not temporarily_state:
                payload['dimmer'] = 100
            self.get('/set_output', payload)

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

    def receive_output_event(self, output, output_status, between):
        # type: (Output, bool, Tuple[float, float]) -> bool
        cooldown, deadline = between
        timeout = deadline - cooldown
        if cooldown > 0:
            logger.debug('Waiting {:.2f}s before event'.format(cooldown))
            self.reset()
            time.sleep(cooldown)
        since = time.time()
        while since > time.time() - timeout:
            if output.output_id in self._outputs and output_status == self._outputs[output.output_id]:
                logger.debug('Received event {} status={} after {:.2f}s'.format(output, self._outputs[output.output_id], time.time() - since))
                return True
            if self.update_events():
                continue
            time.sleep(0.2)
        logger.error('Did not receive event {} status={} after {:.2f}s'.format(output, output_status, time.time() - since))
        self.log_events()
        return False


class Toolbox(object):
    DEBIAN_AUTHORIZED_MODE = 13  # tester_output_1.output_5
    DEBIAN_DISCOVER_INPUT = 14  # tester_output_1.output_6
    DEBIAN_DISCOVER_OUTPUT = 15  # tester_output_1.output_7
    DEBIAN_DISCOVER_CAN_CONTROL = 22  # tester_output2.output_6
    DEBIAN_DISCOVER_DIMMER = 20  # tester_output2.output_4
    DEBIAN_DISCOVER_TEMP = 21  # tester_output2.output_5
    DEBIAN_DISCOVER_ENERGY = 23  # tester_output2.output_7
    DEBIAN_POWER_OUTPUT = 8  # tester_output_1.output_0
    POWER_ENERGY_MODULE = 11  # tester_output_1.output_3
    CORE_PLUS_SETUP_BUTTON = 19  # tester_output_2.output_3
    CORE_PLUS_ACTION_BUTTON = 16  # tester_output_2.output_0
    CORE_PLUS_POWER_OUTPUT = 10  # tester_output_1.output_2

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
            self._tester = TesterGateway(Client('tester', tester_host, auth=tester_auth))
        return self._tester

    @property
    def dut(self):
        # type: () -> Client
        if self._dut is None:
            dut_auth = os.environ['OPENMOTICS_DUT_AUTH'].split(':')
            dut_host = os.environ['OPENMOTICS_DUT_HOST']
            self._dut = Client('dut', dut_host, auth=dut_auth)
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

        # For now, while some code knows the difference between emulated, physical, virtual, ..., the code will mainly work
        # using the i, O, s, ... letters instead (so virtual and non-virtual).
        # TODO: Change this in the future, as it needs a new API call on the GW.

        expected_modules = {Module.HardwareType.VIRTUAL: {},
                            Module.HardwareType.PHYSICAL: {}}  # Limit it to physical and virtual for now
        for module in OUTPUT_MODULE_LAYOUT + INPUT_MODULE_LAYOUT + TEMPERATURE_MODULE_LAYOUT:
            hardware_type = Module.HardwareType.VIRTUAL if module.hardware_type == Module.HardwareType.VIRTUAL else Module.HardwareType.PHYSICAL
            if module.mtype not in expected_modules[hardware_type]:
                expected_modules[hardware_type][module.mtype] = 0
            expected_modules[hardware_type][module.mtype] += 1
        logger.info('Expected modules: {0}'.format(expected_modules))

        missing_modules = set()
        modules = self.count_modules('master')
        logger.info('Current modules: {0}'.format(modules))
        for mtype, expected_amount in expected_modules[Module.HardwareType.PHYSICAL].items():
            if modules.get(mtype, 0) == 0:
                missing_modules.add(mtype)
        modules_info = self.list_modules()['master'].values()
        if not any(v['type'] == 'C' for v in modules_info):
            missing_modules.add('C')
        if not any(v['type'] == 'I' and v['is_can'] for v in modules_info):
            missing_modules.add('C')
        if missing_modules:
            logger.info('Discovering modules...')
            self.discover_modules(output_modules='O' in missing_modules,
                                  input_modules='I' in missing_modules,
                                  can_controls='C' in missing_modules,
                                  dimmer_modules='D' in missing_modules,
                                  temp_modules='T' in missing_modules,
                                  ucans='C' in missing_modules)

        modules = self.count_modules('master')
        logger.info('Discovered modules: {0}'.format(modules))
        for mtype, expected_amount in expected_modules[Module.HardwareType.PHYSICAL].items():
            assert modules.get(mtype, 0) == expected_amount

        # TODO ensure discovery synchonization finished.
        for module in INPUT_MODULE_LAYOUT:
            self.ensure_input_exists(module.inputs[-1], timeout=300)

        try:
            for mtype, expected_amount in expected_modules[Module.HardwareType.VIRTUAL].items():
                assert modules.get(mtype, 0) >= expected_amount
        except Exception:
            logger.info('Adding virtual modules...')
            for mtype, expected_amount in expected_modules[Module.HardwareType.VIRTUAL].items():
                extra_needed_amount = expected_amount - modules.get(mtype, 0)
                assert extra_needed_amount > 0
                self.add_virtual_modules(module_amounts={mtype: extra_needed_amount})

        modules = self.count_modules('master')
        logger.info('Virtual modules: {0}'.format(modules))
        for mtype, expected_amount in expected_modules[Module.HardwareType.VIRTUAL].items():
            assert modules.get(mtype, 0) >= expected_amount

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

    def list_modules(self):
        # type: () -> Dict[str, Any]
        return self.dut.get('/get_modules_information')['modules']

    def count_modules(self, category):
        modules = {}
        for address, info in self.list_modules()[category].items():
            if info['type'] not in modules:
                modules[info['type']] = 0
            modules[info['type']] += 1
        return modules

    def assert_modules(self, module_type, min_modules=1):
        # type: (str, int) -> List[Dict[str, Any]]
        data = self.list_modules()
        modules = []
        for address, info in data['master'].items():
            if info['type'] != module_type:
                continue
            modules.append(info)
        assert len(modules) >= min_modules, 'Not enough modules of type \'{}\' available in {}'.format(module_type, data)
        return modules

    def list_energy_modules(self, module_type, min_modules=1):
        # type: (str, int) -> List[Dict[str, Any]]
        data = self.list_modules()
        modules = []
        for address, info in data['energy'].items():
            if info['type'] != module_type or not info['firmware']:
                continue
            modules.append(info)
        assert len(modules) >= min_modules, 'Not enough energy modules of type \'{}\' available in {}'.format(module_type, data)
        return modules

    def authorized_mode_start(self):
        # type: () -> None
        logger.debug('start authorized mode')
        if TEST_PLATFORM == TestPlatform.CORE_PLUS:
            self.tester.toggle_outputs([self.CORE_PLUS_ACTION_BUTTON,
                                        self.CORE_PLUS_SETUP_BUTTON], delay=15)
        else:
            self.tester.toggle_output(self.DEBIAN_AUTHORIZED_MODE, delay=15)

    def authorized_mode_stop(self):
        # type: () -> None
        if TEST_PLATFORM == TestPlatform.CORE_PLUS:
            self.tester.toggle_outputs([self.CORE_PLUS_ACTION_BUTTON,
                                        self.CORE_PLUS_SETUP_BUTTON])
        else:
            self.tester.toggle_output(self.DEBIAN_AUTHORIZED_MODE)

    def create_or_update_user(self, success=True):
        # type: (bool) -> None
        logger.info('create or update test user')
        assert self.dut._auth
        user_data = {'username': self.dut._auth[0], 'password': self.dut._auth[1]}
        self.dut.get('/create_user', params=user_data, use_token=False, success=success)

    def get_gateway_version(self):
        # type: () -> str
        return self.dut.get('/get_version')['gateway']

    def get_firmware_versions(self):
        # type: () -> Dict[str,str]
        modules = self.dut.get('/get_modules_information')['modules']['master']
        versions = {'M': self.dut.get('/get_status')['version']}
        for data in (x for x in modules.values() if 'firmware' in x):
            module = 'C' if data.get('is_can', False) else data['type']
            versions[module] = data['firmware']
        return versions

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

    def discover_modules(self, output_modules=False, input_modules=False, can_controls=False, ucans=False, dimmer_modules=False, temp_modules=False, timeout=120):
        # TODO: Does not work yet for the Core(+) as they don't have this call implemented.
        logger.debug('Discovering modules')
        since = time.time()
        # [WIP] tried to disable ucan logic for the factory reset test (CAN FX call)
        # but it did not enable us to check the behaviour
        if ucans:
            ucan_inputs = []
            for module in INPUT_MODULE_LAYOUT:
                if module.mtype == 'C':
                    ucan_inputs += module.inputs
            for ucan_input in ucan_inputs:
                self.tester.toggle_output(ucan_input.tester_output_id, delay=0.5)
            time.sleep(0.5)  # Give a brief moment for the CC to settle

        new_modules = []
        self.clear_module_discovery_log()
        self.module_discover_start()
        try:
            addresses = []
            if output_modules:
                self.tester.toggle_output(self.DEBIAN_DISCOVER_OUTPUT, delay=0.5)
                new_modules += self.watch_module_discovery_log(module_amounts={'O': 1}, addresses=addresses)
            if input_modules:
                self.tester.toggle_output(self.DEBIAN_DISCOVER_INPUT, delay=0.5)
                new_modules += self.watch_module_discovery_log(module_amounts={'I': 1}, addresses=addresses)
            if can_controls:
                self.tester.toggle_output(self.DEBIAN_DISCOVER_CAN_CONTROL, delay=0.5)
                module_amounts = {'C': 1}
                if ucans:
                    module_amounts.update({'I': 1, 'T': 1})
                new_modules += self.watch_module_discovery_log(module_amounts=module_amounts, addresses=addresses)
            if dimmer_modules:
                self.tester.toggle_output(self.DEBIAN_DISCOVER_DIMMER, delay=0.5)
                new_modules += self.watch_module_discovery_log(module_amounts={'D': 1}, addresses=addresses)
            if temp_modules:
                self.tester.toggle_output(self.DEBIAN_DISCOVER_TEMP, delay=0.5)
                new_modules += self.watch_module_discovery_log(module_amounts={'T': 1}, addresses=addresses)
            new_module_addresses = set(module['address'] for module in new_modules)
        finally:
            self.module_discover_stop()

        while since > time.time() - timeout:
            data = self.dut.get('/get_modules_information')
            synced_addresses = set(data['modules']['master'].keys())
            if new_module_addresses.issubset(synced_addresses):
                return True
        raise AssertionError('Did not discover required modules')

    def add_virtual_modules(self, module_amounts, timeout=120):
        since = time.time()
        desired_new_outputs = module_amounts.get('o', 0)
        desired_new_inputs = module_amounts.get('i', 0)

        def _get_current_virtual_modules():
            virtual_modules = {}
            data = self.dut.get('/get_modules_information')
            for entry in data['modules']['master'].values():
                if entry['is_virtual']:
                    virtual_modules.setdefault(entry['type'], set()).add(entry['address'])
            return virtual_modules
        previous_virtual_modules = _get_current_virtual_modules()

        for _ in range(desired_new_outputs):
            self.dut.get('/add_virtual_output_module')
            time.sleep(2)
        for _ in range(desired_new_inputs):
            self.dut.get('/add_virtual_input_module')
            time.sleep(2)
        # TODO: We should/could use the module discover log as well, but adding virtual modules isn't generate events

        new_outputs, new_inputs = (0, 0)
        while since > time.time() - timeout:
            current_virtual_modules = _get_current_virtual_modules()
            new_outputs = len(current_virtual_modules.get('o', set()) - previous_virtual_modules.get('o', set()))
            new_inputs = len(current_virtual_modules.get('i', set()) - previous_virtual_modules.get('i', set()))
            if new_outputs == desired_new_outputs and new_inputs == desired_new_inputs:
                return True
            time.sleep(5)
        raise AssertionError('Did not discover required virtual modules, outputs: %s inputs: %s', new_outputs, new_inputs)

    def clear_module_discovery_log(self):
        self.dut.get('/get_module_log')

    def watch_module_discovery_log(self, module_amounts, timeout=10, addresses=None):
        # type: (Dict[str, int], float, Optional[List[str]]) -> List[Dict[str, Any]]

        def format_module_amounts(amounts):
            return ', '.join('{}={}'.format(mtype, amount) for mtype, amount in amounts.items())

        since = time.time()
        all_entries = []
        desired_entries = []
        found_module_amounts = {}
        if addresses is None:
            addresses = []
        while since > time.time() - timeout:
            log = self.dut.get('/get_module_log')['log']
            # Log format: {'code': '<NEW|EXISTING|DUPLCATE|UNKNOWN>',
            #              'module_nr': <module number in its category>,
            #              'category': '<SHUTTER|INTPUT|OUTPUT>',
            #              'module_type': '<I|O|T|D|i|o|t|d|C>,
            #              'address': '<module address>'}
            all_entries += log
            for entry in log:
                if entry['code'] in ['DUPLICATE', 'UNKNOWN']:
                    continue
                module_type = entry['module_type']
                if module_type not in module_amounts:
                    continue
                address = entry['address']
                if address not in addresses:
                    addresses.append(address)
                    if module_type not in found_module_amounts:
                        found_module_amounts[module_type] = 0
                    found_module_amounts[module_type] += 1
                    desired_entries.append(entry)
                    logger.debug('Discovered {} module: {} ({})'.format(entry['code'],
                                                                        entry['module_type'],
                                                                        entry['address']))
            if found_module_amounts == module_amounts:
                logger.debug('Discovered required modules: {}'.format(format_module_amounts(found_module_amounts)))
                return desired_entries
            time.sleep(2)
        raise AssertionError('Did not discover required modules: {}. Raw log: {}'.format(
            format_module_amounts(module_amounts), all_entries
        ))

    def discover_energy_module(self):
        # type: () -> None
        self.tester.get('/set_output', {'id': self.POWER_ENERGY_MODULE, 'is_on': True})
        time.sleep(5)
        try:
            logger.debug('discover Energy module')
            self.dut.get('/start_power_address_mode')
            self.tester.toggle_output(self.DEBIAN_DISCOVER_ENERGY, 1.0)
            self.assert_energy_modules(1, timeout=60)
        finally:
            self.dut.get('/stop_power_address_mode')

    def assert_energy_modules(self, count, timeout=30):
        # type: (int, float) -> List[List[str]]
        since = time.time()
        modules = []
        while since > time.time() - timeout:
            modules += self.dut.get('/get_power_modules')['modules']
            if len(modules) >= count:
                logger.debug('discovered {} modules, done'.format(count))
                return modules
            time.sleep(2)
        raise AssertionError('expected {} modules in {}'.format(count, modules))

    def power_off(self):
        # type: () -> None
        logger.debug('power off')
        if TEST_PLATFORM == TestPlatform.CORE_PLUS:
            output_id = self.CORE_PLUS_POWER_OUTPUT
        else:
            output_id = self.DEBIAN_POWER_OUTPUT
        self.tester.get('/set_output', {'id': output_id, 'is_on': False})
        time.sleep(2)

    def ensure_power_on(self):
        # type: () -> None
        if not self.health_check(timeout=0.2, skip_assert=True):
            return
        logger.info('power on')
        if TEST_PLATFORM == TestPlatform.CORE_PLUS:
            output_id = self.CORE_PLUS_POWER_OUTPUT
            timeout = 600  # After a potential factory reset, the Core+ has to wipe a lot more EEPROM and is therefore slower
        else:
            output_id = self.DEBIAN_POWER_OUTPUT
            timeout = 300
        self.tester.get('/set_output', {'id': output_id, 'is_on': True})
        logger.info('waiting for gateway api to respond...')
        self.health_check(timeout=timeout)
        logger.info('health check done')

    @contextmanager
    def disabled_self_recovery(self):
        try:
            self.dut.get('/set_self_recovery', {'active': False})
            yield self
        finally:
            self.dut.get('/set_self_recovery', {'active': True})

    def health_check(self, timeout=30, skip_assert=False):
        # type: (float) -> List[str]
        since = time.time()
        pending = ['unknown']
        while since > time.time() - timeout:
            try:
                data = self.dut.get('/health_check', use_token=False, success=False, timeout=5)
                pending = [k for k, v in data['health'].items() if not v['state']]
                if not pending:
                    return pending
                logger.debug('wait for health check, {}'.format(pending))
            except Exception:
                pass
            time.sleep(10)
        if skip_assert:
            return pending
        assert pending == []

    def module_error_check(self):
        # type: () -> None
        data = self.dut.get('/get_errors')
        for module, count in data['errors']:
            # TODO just fail?
            if count != 0:
                logger.warning('master reported errors {} {}'.format(module, count))

    def configure_output(self, output, config):
        # type: (Output, Dict[str,Any]) -> None
        config_data = {'id': output.output_id}
        config_data.update(**config)
        logger.debug('configure output {} with {}'.format(output, config))
        self.dut.get('/set_output_configuration', {'config': json.dumps(config_data)})

    def ensure_output(self, output, status, config=None):
        # type: (Output, int, Optional[Dict[str,Any]]) -> None
        if config:
            self.configure_output(output, config)
        state = ' '.join(self.tester.get_last_outputs())
        hypothesis.note('ensure output {} is {}'.format(output, status))
        logger.debug('ensure output {} is {}    outputs={}'.format(output, status, state))
        time.sleep(0.2)
        self.set_output(output, status)
        time.sleep(0.2)
        self.tester.reset()

    def set_output(self, output, status):
        # type: (Output, int) -> None
        logger.debug('set output {} -> {}'.format(output, status))
        self.dut.get('/set_output', {'id': output.output_id, 'is_on': status})

    def press_input(self, _input):
        # type: (Input) -> None
        self.tester.get('/set_output', {'id': _input.tester_output_id, 'is_on': False})  # ensure start status
        time.sleep(0.2)
        self.tester.reset()
        hypothesis.note('After input {} pressed'.format(_input))
        self.tester.toggle_output(_input.tester_output_id, is_dimmer=_input.is_dimmer)
        logger.debug('Toggled {} -> True -> False'.format(_input))

    def assert_output_changed(self, output, status, between=(0, 5)):
        # type: (Output, bool, Tuple[float,float]) -> None
        hypothesis.note('assert output {} status changed {} -> {}'.format(output, not status, status))
        if self.tester.receive_output_event(output, status, between=between):
            return
        raise AssertionError('expected event {} status={}'.format(output, status))

    def assert_output_status(self, output, status, timeout=5):
        # type: (Output, bool, float) -> None
        hypothesis.note('assert output {} status is {}'.format(output, status))
        since = time.time()
        current_status = None
        while since > time.time() - timeout:
            data = self.dut.get('/get_output_status')
            current_status = data['status'][output.output_id]['status']
            if status == bool(current_status):
                logger.debug('get output {} status={}, after {:.2f}s'.format(output, status, time.time() - since))
                return
            time.sleep(2)
        state = ' '.join(self.tester.get_last_outputs())
        logger.error('get status {} status={} != expected {}, timeout after {:.2f}s    outputs={}'.format(output, bool(current_status), status, time.time() - since, state))
        self.tester.log_events()
        raise AssertionError('get status {} status={} != expected {}, timeout after {:.2f}s'.format(output, bool(current_status), status, time.time() - since))

    def ensure_input_exists(self, _input, timeout=30):
        # type: (Input, float) -> None
        since = time.time()
        while since > time.time() - timeout:
            data = self.dut.get('/get_input_status')
            try:
                next(x for x in data['status'] if x['id'] == _input.input_id)
                logger.debug('input {} with status discovered, after {:.2f}s'.format(_input, time.time() - since))
                return
            except StopIteration:
                pass
            time.sleep(2)
        raise AssertionError('input {} status missing, timeout after {:.2f}s'.format(_input, time.time() - since))
