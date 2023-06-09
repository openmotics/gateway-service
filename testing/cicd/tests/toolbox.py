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
from datetime import datetime, timedelta
from itertools import groupby

import hypothesis
import requests
import ujson as json
from requests.exceptions import ConnectionError, RequestException, Timeout

from tests.hardware_layout import INPUT_MODULE_LAYOUT, OUTPUT_MODULE_LAYOUT, \
    TEMPERATURE_MODULE_LAYOUT, TEST_PLATFORM, TESTER, Input, Module, Output, \
    TestPlatform, Shutter, SHUTTER_MODULE_LAYOUT, ENERGY_MODULE_LAYOUT

logger = logging.getLogger(__name__)

if False:  # MYPY
    from typing import Any, Dict, List, Optional, Tuple, Union


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
            params = {'username': self._auth[0], 'password': self._auth[1], 'accept_terms': True, 'timeout': timedelta(hours=3).seconds}
            data = self.get('/login', params=params, use_token=False, success=success, timeout=timeout)
            if 'token' in data:
                return data['token']
            else:
                raise Exception('Unexpected response: {}'.format(data))
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
            # logger.debug('GET {} {} {}'.format(self._id, path, params))

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
                assert response.status_code != 404, 'Call `{0}` not found: {1}'.format(path, response.content)
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
        self._inputs = {}  # type: Dict[int,bool]
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
        for event in (x for x in self._last_data['events'] if 'input_id' in x):
            received_at, input_id, input_status = (event['received_at'], event['input_id'], event['input_status'])
            timestamp = datetime.fromtimestamp(received_at).strftime('%y-%m-%d %H:%M:%S,%f')
            logger.error('{} received event {} -> {}'.format(timestamp, input_id, input_status))

    def update_events(self):
        # type: () -> bool
        data = self.get('/plugins/event_observer/events')
        self._last_data = data
        changed = False
        for event in (x for x in self._last_data['events'] if 'input_id' in x):
            received_at, input_id, input_status = (event['received_at'], event['input_id'], event['input_status'])
            if received_at >= self._last_received_at:
                changed = True
                self._last_received_at = received_at
                self._inputs[input_id] = bool(input_status)
        return changed

    def reset(self):
        # type: () -> None
        self._inputs = {}

    def receive_input_event(self, entity, input_id, input_status, between):
        # type: (Union[Output, Shutter], int, bool, Tuple[float, float]) -> bool
        cooldown, deadline = between
        timeout = deadline - cooldown
        if input_id is None:
            raise ValueError('Invalid {} for events, is not connected to a tester input'.format(entity))
        if cooldown > 0:
            logger.debug('Waiting {:.2f}s before event'.format(cooldown))
            self.reset()
            time.sleep(cooldown)
        since = time.time()
        while since > time.time() - timeout:
            if input_id in self._inputs and input_status == self._inputs[input_id]:
                logger.debug('Received event {} status={} after {:.2f}s'.format(entity, self._inputs[input_id], time.time() - since))
                return True
            if self.update_events():
                continue
            time.sleep(0.2)
        logger.error('Did not receive event {} status={} after {:.2f}s'.format(entity, input_status, time.time() - since))
        self.log_events()
        return False

    def wait_for_input_status(self, entity, input_id, input_status, timeout):
        # type: (Union[Output, Shutter], int, bool, Optional[float]) -> bool
        since = time.time()
        current_status = None
        while timeout is None or since > time.time() - timeout:
            data = self.get('/get_input_status')
            current_status = {s['id']: s['status'] == 1 for s in data['status']}.get(input_id, None)
            if input_status == current_status:
                logger.debug('Get status {} status={}, after {:.2f}s'.format(entity, input_status, time.time() - since))
                return True
            if timeout is None:
                break  # Immediate check
            time.sleep(max(0.2, timeout / 10.0))
        logger.error('Get status {} status={} != expected {}, timeout after {:.2f}s'.format(entity, current_status, input_status, time.time() - since))
        return False


class Toolbox(object):
    def __init__(self):
        # type: () -> None
        self._tester = None  # type: Optional[TesterGateway]
        self._dut = None  # type: Optional[Client]
        self.dirty_shutters = []  # type: List[Shutter]

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

        expected_modules = {Module.HardwareType.VIRTUAL: {},
                            Module.HardwareType.PHYSICAL: {},
                            Module.HardwareType.EMULATED: {},
                            Module.HardwareType.INTERNAL: {}}
        for module in (OUTPUT_MODULE_LAYOUT + INPUT_MODULE_LAYOUT + TEMPERATURE_MODULE_LAYOUT +
                       SHUTTER_MODULE_LAYOUT + ENERGY_MODULE_LAYOUT):
            hardware_type = module.hardware_type
            if module.module_type not in expected_modules[hardware_type]:
                expected_modules[hardware_type][module.module_type] = 0
            expected_modules[hardware_type][module.module_type] += 1
        logger.info('Expected modules: {0}'.format(expected_modules))

        missing_modules = set()
        missing_emulated_modules = set()
        modules = self.count_modules()
        logger.info('Initial modules: {0}'.format(modules))
        for hardware_type in [Module.HardwareType.PHYSICAL, Module.HardwareType.EMULATED]:
            for module_type, expected_amount in expected_modules[hardware_type].items():
                if modules[hardware_type].get(module_type, 0) == 0:
                    if hardware_type == Module.HardwareType.PHYSICAL:
                        missing_modules.add(module_type)
                    else:
                        missing_emulated_modules.add(module_type)
        if missing_modules or missing_emulated_modules:
            logger.info('Discovering modules...')
            self.discover_modules(output_modules={Module.HardwareType.PHYSICAL: 'output' in missing_modules},
                                  input_modules={Module.HardwareType.PHYSICAL: 'input' in missing_modules,
                                                 Module.HardwareType.EMULATED: 'input' in missing_emulated_modules},
                                  shutter_modules={Module.HardwareType.PHYSICAL: 'shutter' in missing_modules},
                                  dimmer_modules={Module.HardwareType.PHYSICAL: 'dim_control' in missing_modules},
                                  sensor_modules={Module.HardwareType.PHYSICAL: 'sensor' in missing_modules,
                                                  Module.HardwareType.EMULATED: 'sensor' in missing_emulated_modules},
                                  can_controls={Module.HardwareType.PHYSICAL: 'can_control' in missing_modules},
                                  energy_modules={Module.HardwareType.PHYSICAL: 'energy' in missing_modules})

        modules = self.count_modules()
        logger.info('Post-discovery modules: {0}'.format(modules))
        for hardware_type in [Module.HardwareType.PHYSICAL, Module.HardwareType.INTERNAL, Module.HardwareType.EMULATED]:
            for module_type in set(list(expected_modules[hardware_type].keys())):
                expected_amount = (expected_modules[hardware_type].get(module_type, 0))
                actual_amount = (modules[hardware_type].get(module_type, 0))
                assert actual_amount >= expected_amount, 'Expected {0} {1} {2} modules'.format(expected_amount, hardware_type, module_type)

        try:
            for module_type, expected_amount in expected_modules[Module.HardwareType.VIRTUAL].items():
                assert modules[Module.HardwareType.VIRTUAL].get(module_type, 0) >= expected_amount
        except Exception:
            logger.info('Adding virtual modules...')
            for module_type, expected_amount in expected_modules[Module.HardwareType.VIRTUAL].items():
                extra_needed_amount = expected_amount - modules.get(module_type, 0)
                assert extra_needed_amount > 0
                self.add_virtual_modules(module_amounts={module_type: extra_needed_amount})

        modules = self.count_modules()
        logger.info('Post add virtual modules: {0}'.format(modules))
        for module_type, expected_amount in expected_modules[Module.HardwareType.VIRTUAL].items():
            assert modules[Module.HardwareType.VIRTUAL].get(module_type, 0) >= expected_amount

        # TODO ensure discovery synchonization finished.
        for module in OUTPUT_MODULE_LAYOUT:
            if module.outputs:
                self.ensure_output_exists(module.outputs[-1], timeout=300)
        for module in INPUT_MODULE_LAYOUT:
            if module.inputs:
                self.ensure_input_exists(module.inputs[-1], timeout=300)
        for module in SHUTTER_MODULE_LAYOUT:
            if module.shutters:
                self.ensure_shutter_exists(module.shutters[-1], timeout=300)

        # Make sure the eeprom cache of the gateway is filled
        def _call(call):
            try:
                self.dut.get(call)
            except Exception:
                time.sleep(3)
                self.dut.get(call)

        _call('/get_cooling_configurations')
        _call('/get_input_configurations')
        _call('/get_output_configurations')
        _call('/get_shutter_configurations')
        _call('/get_shutter_group_configurations')
        _call('/get_ventilation_configurations')
        _call('/get_scheduled_action_configurations')
        _call('/get_group_action_configurations')
        _call('/get_sensor_configurations')
        _call('/get_thermostat_configurations')

        time.sleep(20)  # Give the master some additional rest before testing begins

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
        params = {'username': self.dut._auth[0], 'password': self.dut._auth[1], 'confirm': confirm, 'can': False}
        return self.dut.get('/factory_reset', params=params, success=confirm)

    def count_modules(self):
        modules = self.dut.get('/get_modules_information')['modules']
        counts = {Module.HardwareType.VIRTUAL: {},
                  Module.HardwareType.PHYSICAL: {},
                  Module.HardwareType.INTERNAL: {},
                  Module.HardwareType.EMULATED: {}}
        for source in ['master', 'gateway']:
            if source not in modules:
                continue
            for module in modules[source].values():
                hardware_type = module['hardware_type']
                module_type = module['module_type']
                if module_type not in counts[hardware_type]:
                    counts[hardware_type][module_type] = 0
                counts[hardware_type][module_type] += 1
        return counts

    def authorized_mode_start(self):
        # type: () -> None
        logger.debug('start authorized mode')
        self.tester.toggle_outputs(TESTER.Buttons.dut, delay=15)

    def authorized_mode_stop(self):
        # type: () -> None
        self.tester.toggle_outputs(TESTER.Buttons.dut)

    def create_or_update_user(self, success=True):
        # type: (bool) -> None
        logger.info('create or update test user')
        assert self.dut._auth
        user_data = {'username': self.dut._auth[0], 'password': self.dut._auth[1]}
        self.dut.get('/create_user', params=user_data, use_token=False, success=success)
        # For easier debugging, always create an admin/admin user as well
        user_data = {'username': 'admin', 'password': 'admin'}
        self.dut.get('/create_user', params=user_data, use_token=False, success=success)

    def get_gateway_version(self):
        # type: () -> str
        return self.dut.get('/get_version')['gateway']

    def get_firmware_versions(self):
        # type: () -> Dict[str,str]
        modules = self.dut.get('/get_modules_information?refresh=True')['modules']['master']
        versions = {'M': self.dut.get('/get_status')['version']}
        for data in (x for x in modules.values() if 'firmware' in x):
            module = 'C' if data.get('is_can', False) else data['type']
            versions[module] = data['firmware']
        return versions

    def module_discover_start(self):
        # type: () -> None
        logger.debug('start module discover')
        master_discovery_active = False
        self.dut.get('/module_discover_start')
        for _ in range(10):
            data = self.dut.get('/module_discover_status')
            if data['running']:
                master_discovery_active = True
                break
            time.sleep(0.2)
        energy_discovery_active = False
        self.dut.get('/start_power_address_mode')
        for _ in range(10):
            data = self.dut.get('/in_power_address_mode')
            if data['address_mode']:
                energy_discovery_active = True
                break
            time.sleep(0.2)
        assert master_discovery_active and energy_discovery_active, 'Could not start discovery'

    def module_discover_stop(self):
        # type: () -> None
        logger.debug('stop module discover')
        self.dut.get('/module_discover_stop')
        self.dut.get('/stop_power_address_mode')

    def discover_modules(self, output_modules, input_modules, shutter_modules, dimmer_modules, sensor_modules, can_controls, energy_modules, timeout=120):
        logger.info('Discovering modules')
        since = time.time()
        expected_emulated_modules = {}
        if input_modules[Module.HardwareType.EMULATED] or sensor_modules[Module.HardwareType.EMULATED]:
            ucan_inputs = []
            for module in INPUT_MODULE_LAYOUT:
                if module.is_can:
                    ucan_inputs += module.inputs
                    if module.module_type not in expected_emulated_modules:
                        expected_emulated_modules[module.module_type] = 0
                    expected_emulated_modules[module.module_type] += 1
            for module in TEMPERATURE_MODULE_LAYOUT:
                if module.is_can:
                    if module.module_type not in expected_emulated_modules:
                        expected_emulated_modules[module.module_type] = 0
                    expected_emulated_modules[module.module_type] += 1
            if ucan_inputs:
                logger.info('* Toggle uCAN inputs for discovery: %s', ucan_inputs)
                for ucan_input in ucan_inputs:
                    self.tester.toggle_output(ucan_input.tester_output_id, delay=0.5)
                    time.sleep(0.5)
                time.sleep(5)  # Give a brief moment for the CC to settle

        def _press_discover_button(button):
            self.tester.toggle_output(button, delay=0.5)
            time.sleep(1)
            self.tester.toggle_output(button, delay=0.5)

        need_energy_module = False
        new_modules = []
        self.clear_module_discovery_log()
        self.module_discover_start()
        try:
            addresses = []
            if output_modules[Module.HardwareType.PHYSICAL]:
                logger.info('* Discover output module')
                _press_discover_button(TESTER.Button.output)
                new_modules += self.watch_module_discovery_log(module_amounts={'O': 1}, addresses=addresses)
            if shutter_modules[Module.HardwareType.PHYSICAL]:
                logger.info('* Discover shutter module')
                _press_discover_button(TESTER.Button.shutter)
                new_modules += self.watch_module_discovery_log(module_amounts={'R': 1}, addresses=addresses)
            if input_modules[Module.HardwareType.PHYSICAL]:
                logger.info('* Discover input module')
                _press_discover_button(TESTER.Button.input)
                new_modules += self.watch_module_discovery_log(module_amounts={'I': 1}, addresses=addresses)
            if dimmer_modules[Module.HardwareType.PHYSICAL]:
                logger.info('* Discover dim control module')
                _press_discover_button(TESTER.Button.dimmer)
                new_modules += self.watch_module_discovery_log(module_amounts={'D': 1}, addresses=addresses)
            if sensor_modules[Module.HardwareType.PHYSICAL]:
                logger.info('* Discover sensor module')
                _press_discover_button(TESTER.Button.temp)
                new_modules += self.watch_module_discovery_log(module_amounts={'T': 1}, addresses=addresses)
            if can_controls[Module.HardwareType.PHYSICAL] or expected_emulated_modules.get('input', 0) or expected_emulated_modules.get('sensor', 0):
                logger.info('* Discover can control')
                _press_discover_button(TESTER.Button.can)
                module_amounts = {'C': 1,  # TODO: Fix these hardcoded values
                                  'T': expected_emulated_modules.get('sensor', 0),
                                  'I': expected_emulated_modules.get('input', 0)}
                new_modules += self.watch_module_discovery_log(module_amounts=module_amounts, addresses=addresses, timeout=30)
            new_module_addresses = set(module['address'] for module in new_modules)
            if energy_modules[Module.HardwareType.PHYSICAL]:
                need_energy_module = True
                logger.info('* Discover energy module')
                _press_discover_button(TESTER.Button.energy)
                time.sleep(3)
        finally:
            self.module_discover_stop()
            time.sleep(30)  # Give time for the master to clear the eeprom cache

        master_modules_found = False
        energy_module_found = not need_energy_module
        data = None
        while (master_modules_found is False or energy_module_found is False) and since > time.time() - timeout:
            data = self.dut.get('/get_modules_information')
            if need_energy_module:
                energy_module_found = len(data['modules'].get('gateway', {})) > 0
            synced_addresses = set(data['modules'].get('master', {}).keys())
            if new_module_addresses.issubset(synced_addresses):
                master_modules_found = True
        if master_modules_found is False or energy_module_found is False:
            raise AssertionError('Discovered modules did not correctly sync: {0}'.format(data))
        return True

    def add_virtual_modules(self, module_amounts, timeout=120):
        since = time.time()
        desired_new_outputs = module_amounts.get('output', 0)
        desired_new_inputs = module_amounts.get('input', 0)

        def _get_current_virtual_modules():
            virtual_modules = {}
            data = self.dut.get('/get_modules_information')
            for entry in data['modules'].get('master', {}).values():
                if entry['hardware_type'] == 'virtual':
                    virtual_modules.setdefault(entry['module_type'], set()).add(entry['address'])
            return virtual_modules
        previous_virtual_modules = _get_current_virtual_modules()

        for _ in range(desired_new_outputs):
            logger.info('* Adding virtual output module')
            self.dut.get('/add_virtual_output_module')
            time.sleep(2)
        for _ in range(desired_new_inputs):
            logger.info('* Adding virtual input module')
            self.dut.get('/add_virtual_input_module')
            time.sleep(2)

        # TODO: We should/could use the module discover log as well, but adding virtual modules isn't generate events

        new_outputs, new_inputs = (0, 0)
        while since > time.time() - timeout:
            current_virtual_modules = _get_current_virtual_modules()
            new_outputs = len(current_virtual_modules.get('output', set()) - previous_virtual_modules.get('output', set()))
            new_inputs = len(current_virtual_modules.get('input', set()) - previous_virtual_modules.get('input', set()))
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
        required_module_amounts = {module_type: amount
                                   for module_type, amount in module_amounts.items()
                                   if amount > 0}
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
                if module_type not in required_module_amounts:
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
            if found_module_amounts == required_module_amounts:
                logger.debug('Discovered required modules: {}'.format(format_module_amounts(found_module_amounts)))
                return desired_entries
            time.sleep(2)
        raise AssertionError('Did not discover required modules: {}. Raw log: {}'.format(
            format_module_amounts(required_module_amounts), all_entries
        ))

    def discover_energy_module(self):
        # type: () -> None
        self.tester.get('/set_output', {'id': TESTER.Power.bus2, 'is_on': True})
        time.sleep(5)
        try:
            logger.debug('discover Energy module')
            self.dut.get('/start_power_address_mode')
            self.tester.toggle_output(TESTER.Button.energy, 1.0)
            self.assert_energy_modules(1, timeout=60)
        finally:
            self.dut.get('/stop_power_address_mode')

    def assert_energy_modules(self, count, timeout=30):
        # type: (int, float) -> List[List[str]]
        since = time.time()
        modules = []
        while since > time.time() - timeout:
            modules += self.dut.get('/get_modules_information')['modules']
            if len(modules) >= count:
                logger.debug('discovered {} modules, done'.format(count))
                return modules
            time.sleep(2)
        raise AssertionError('expected {} modules in {}'.format(count, modules))

    def power_off(self):
        # type: () -> None
        logger.debug('power off')
        self.tester.get('/set_output', {'id': TESTER.Power.dut, 'is_on': False})
        time.sleep(2)

    def ensure_power_on(self):
        # type: () -> None
        if not self.health_check(timeout=0.2, skip_assert=True):
            return
        logger.info('power on')
        if TEST_PLATFORM == TestPlatform.CORE_PLUS:
            timeout = 600  # After a potential factory reset, the Core+ has to wipe a lot more EEPROM and is therefore slower
        else:
            timeout = 300
        self.tester.get('/set_output', {'id': TESTER.Power.dut, 'is_on': True})
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
        # type: (float, bool) -> List[str]
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
        if not skip_assert:
            assert pending == []
        return pending

    def wait_for_completed_update(self, timeout=600):
        # type: (float) -> None
        def _log_status_detail(logger_, status_detail):
            logger_('Update status overview:')
            for key, value in groupby(status_detail, key=lambda d: d['firmware_type']):
                logger_('* {0}'.format(key))
                for entry in list(value):
                    address = '{0}: '.format(entry['module_address']) if 'module_address' in entry else ''
                    if entry['state'] == 'OK':
                        logger_('  * {0}{1} (OK)'.format(address, entry['current_version']))
                    else:
                        logger_('  * {0}{1} -> {2} ({3})'.format(address,
                                                                 entry['current_version'],
                                                                 entry['target_version'],
                                                                 entry['state']))

        since = time.time()
        updates_status = {}
        failure = False
        while since > time.time() - timeout:
            try:
                data = self.dut.get('/get_system_status', use_token=True, success=False, timeout=5)
                if not data.get('success', False):
                    if data.get('msg', 'unknown') == 'invalid_token':
                        self.dut.login()
                        continue
                updates_status = data['updates']
                if updates_status['status'] == 'OK':
                    logger.info('Update completed')
                    _log_status_detail(logger.info, updates_status.get('status_detail', []))
                    return
                if updates_status['status'] == 'ERROR':
                    failure = True
                    break
                logger.debug('Waiting for update completion')
            except Exception:
                pass
            time.sleep(10)
        logger.error('Update failed' if failure else 'Update timed out')
        _log_status_detail(logger.error, updates_status.get('status_detail', []))
        assert False

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
        hypothesis.note('ensure output {} is {}'.format(output, status))
        logger.debug('ensure output {} is {}'.format(output, status))
        time.sleep(0.2)
        self.set_output(output, status)
        time.sleep(0.2)
        self.tester.reset()

    def set_output(self, output, status):
        # type: (Output, int) -> None
        logger.debug('set output {} -> {}'.format(output, status))
        self.dut.get('/set_output', {'id': output.output_id, 'is_on': status})

    def configure_shutter(self, shutter, config):
        # type: (Shutter, Dict[str, Any]) -> None
        config_data = {'id': shutter.shutter_id}
        config_data.update(**config)
        logger.debug('configure shutter {} with {}'.format(shutter, config))
        self.dut.get('/set_shutter_configuration', {'config': json.dumps(config_data)})

    def set_shutter(self, shutter, direction):
        # type: (Shutter, str) -> None
        self.dut.get('/do_shutter_{}'.format(direction), {'id': shutter.shutter_id})

    def lock_shutter(self, shutter, locked):
        # type: (Shutter, bool) -> None
        self.dut.get('/do_basic_action', {'action_type': 113, 'action_number': 1 if locked else 0})

    def press_input(self, _input):
        # type: (Input) -> None
        self.tester.get('/set_output', {'id': _input.tester_output_id, 'is_on': False})  # ensure start status
        time.sleep(0.2)
        self.tester.reset()
        hypothesis.note('After input {} pressed'.format(_input))
        self.tester.toggle_output(_input.tester_output_id, is_dimmer=_input.is_dimmer)
        # time.sleep(0.5)
        logger.debug('Toggled {} -> True -> False'.format(_input))

    def assert_shutter_changed(self, shutter, from_status, to_status, timeout=5, inverted=False):
        # type: (Shutter, str, str, float) -> None
        hypothesis.note('assert {} status changed {} -> {}'.format(shutter, from_status, to_status))
        input_id_up = shutter.tester_input_id_down if inverted else shutter.tester_input_id_up
        input_id_down = shutter.tester_input_id_up if inverted else shutter.tester_input_id_down
        start = time.time()
        self.assert_shutter_status(shutter=shutter,
                                   status=to_status,
                                   timeout=timeout,
                                   inverted=inverted)
        if from_status != to_status:
            up_ok = True
            if (from_status == 'going_up') != (to_status == 'going_up'):
                up_ok = self.tester.receive_input_event(entity=shutter,
                                                        input_id=input_id_up,
                                                        input_status=to_status == 'going_up',
                                                        between=(0, Toolbox._remaining_timeout(timeout, start)))
            down_ok = True
            if (from_status == 'going_down') != (to_status == 'going_down'):
                down_ok = self.tester.receive_input_event(entity=shutter,
                                                          input_id=input_id_down,
                                                          input_status=to_status == 'going_down',
                                                          between=(0, Toolbox._remaining_timeout(timeout, start)))
            if not up_ok or not down_ok:
                raise AssertionError('expected events {} status={}, up_ok={}, down_ok={}'.format(shutter, to_status, up_ok, down_ok))

    def assert_output_changed(self, output, status, between=(0, 5)):
        # type: (Output, bool, Tuple[float,float]) -> None
        hypothesis.note('assert {} status changed {} -> {}'.format(output, not status, status))
        if self.tester.receive_input_event(entity=output,
                                           input_id=output.tester_input_id,
                                           input_status=status,
                                           between=between):
            return

        raise AssertionError('expected event {} status={}'.format(output, status))

    def assert_output_status(self, output, status, timeout=5):
        # type: (Output, bool, float) -> None
        hypothesis.note('assert output {} status is {}'.format(output, status))
        if self.tester.wait_for_input_status(entity=output,
                                             input_id=output.tester_input_id,
                                             input_status=status,
                                             timeout=timeout):
            return
        raise AssertionError('Expected {} status={}'.format(output, status))

    def assert_shutter_status(self, shutter, status, timeout=5, inverted=False):
        # type: (Shutter, str, float) -> None
        input_id_up = shutter.tester_input_id_down if inverted else shutter.tester_input_id_up
        input_id_down = shutter.tester_input_id_up if inverted else shutter.tester_input_id_down
        start = time.time()
        up_ok = self.tester.wait_for_input_status(entity=shutter,
                                                  input_id=input_id_up,
                                                  input_status=status == 'going_up',
                                                  timeout=Toolbox._remaining_timeout(timeout, start))
        down_ok = self.tester.wait_for_input_status(entity=shutter,
                                                    input_id=input_id_down,
                                                    input_status=status == 'going_down',
                                                    timeout=Toolbox._remaining_timeout(timeout, start))
        if not up_ok or not down_ok:
            raise AssertionError('Expected {} status={}, up_ok={}, down_ok={}'.format(shutter, status, up_ok, down_ok))

    def ensure_output_exists(self, output, timeout=30):
        # type: (Output, float) -> None
        since = time.time()
        while since > time.time() - timeout:
            data = self.dut.get('/get_output_status')
            try:
                next(x for x in data['status'] if x['id'] == output.output_id)
                logger.debug('output {} with status discovered, after {:.2f}s'.format(output, time.time() - since))
                return
            except StopIteration:
                pass
            time.sleep(2)
        raise AssertionError('output {} status missing, timeout after {:.2f}s'.format(output, time.time() - since))

    def ensure_shutter_exists(self, _shutter, timeout=30):
        # type: (Shutter, float) -> None
        since = time.time()
        while since > time.time() - timeout:
            data = self.dut.get('/get_shutter_status')
            if str(_shutter.shutter_id) in data['detail']:
                logger.debug('shutter {} with status discovered, after {:.2f}s'.format(_shutter, time.time() - since))
                return
            time.sleep(2)
        raise AssertionError('shutter {} status missing, timeout after {:.2f}s'.format(_shutter, time.time() - since))

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

    @staticmethod
    def _remaining_timeout(timeout, start):
        return timeout - time.time() + start
