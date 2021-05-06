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

import unittest

import mock

from gateway.metrics_collector import MetricsCollector
from ioc import Scope, SetTestMode, SetUpTestInjections
from power.power_api import RealtimePower


class MetricsCollectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    @Scope
    def setUp(self):
        self.gateway_api = mock.Mock()
        self.gateway_api.get_power_modules.return_value = [
            {'id': 10, 'address': 11, 'version': 1,
             'input0': 'foo', 'input1': 'bar', 'input2': 'baz',
             'input3': '', 'input4': '', 'input5': '', 'input6': '',
             'input7': ''}
        ]
        self.gateway_api.get_realtime_power.return_value = {}
        self.gateway_api.get_realtime_p1.return_value = {}
        self.gateway_api.get_total_energy.return_value = {}
        SetUpTestInjections(gateway_api=self.gateway_api,
                            pulse_counter_controller=mock.Mock(),
                            thermostat_controller=mock.Mock(),
                            output_controller=mock.Mock(),
                            input_controller=mock.Mock(),
                            sensor_controller=mock.Mock(),
                            module_controller=mock.Mock())
        self.controller = MetricsCollector()

    def test_realtime_power_metrics(self):
        self.gateway_api.get_realtime_power.return_value = {'10': [RealtimePower(10.0, 2.1, 5.0, 3.6)]}
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._run_power_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy',
                                      tags={'type': 'openmotics', 'id': '11.0', 'name': 'foo'},
                                      values={'current': 5.0, 'frequency': 2.1, 'power': 3.6, 'voltage': 10.0})
            assert enqueue.call_args_list == [expected_call]

    def test_realtime_p1_electricity_metrics(self):
        self.gateway_api.get_realtime_p1.return_value = [
            {'electricity': {'current': {'phase1': 1.1, 'phase2': 1.2, 'phase3': 1.3},
                             'ean': '1111111111111111111111111111',
                             'tariff_indicator': 2.0,
                             'consumption_tariff1': 0.022,
                             'consumption_tariff2': 0.01,
                             'injection_tariff1': 0.023,
                             'injection_tariff2': 0.020,
                             'voltage': {'phase1': 1.0, 'phase2': 2.0, 'phase3': 3.0}},
             'gas': {'ean': ''},
             'device_id': '11.0',
             'module_id': 10,
             'port_id': 0,
             'timestamp': 190527083152.0},
        ]
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._run_power_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy_p1',
                                      tags={'type': 'openmotics', 'id': '11.0',
                                            'ean': '1111111111111111111111111111'},
                                      values={'electricity_consumption_tariff1': 22,
                                              'electricity_consumption_tariff2': 10,
                                              'electricity_injection_tariff1': 23,
                                              'electricity_injection_tariff2': 20,
                                              'electricity_tariff_indicator': 2.0,
                                              'electricity_voltage_phase1': 1.0,
                                              'electricity_voltage_phase2': 2.0,
                                              'electricity_voltage_phase3': 3.0,
                                              'electricity_current_phase1': 1.1,
                                              'electricity_current_phase2': 1.2,
                                              'electricity_current_phase3': 1.3})
            assert enqueue.call_args_list == [expected_call]

    def test_realtime_p1_electricity_partial_metrics(self):
        self.gateway_api.get_realtime_p1.return_value = [
            {'electricity': {'current': {'phase1': 1.1, 'phase2': None, 'phase3': None},
                             'ean': '1111111111111111111111111111',
                             'tariff_indicator': None,
                             'consumption_tariff1': None,
                             'consumption_tariff2': 0.023,
                             'injection_tariff1': None,
                             'injection_tariff2': 0.02,
                             'voltage': {'phase1': 1.0, 'phase2': None, 'phase3': None}},
             'gas': {'ean': ''},
             'device_id': '11.0',
             'module_id': 10,
             'port_id': 0,
             'timestamp': 190527083152.0},
        ]
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._run_power_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy_p1',
                                      tags={'type': 'openmotics', 'id': '11.0',
                                            'ean': '1111111111111111111111111111'},
                                      values={'electricity_consumption_tariff2': 23.0,
                                              'electricity_injection_tariff2': 20.0,
                                              'electricity_voltage_phase1': 1.0,
                                              'electricity_current_phase1': 1.1})
            assert enqueue.call_args_list == [expected_call]

    def test_realtime_p1_electricity_no_metrics(self):
        self.gateway_api.get_realtime_p1.return_value = [
            {'electricity': {'current': {'phase1': None, 'phase2': None, 'phase3': None},
                             'ean': '1111111111111111111111111111',
                             'tariff_indicator': None,
                             'consumption_tariff1': None,
                             'consumption_tariff2': None,
                             'injection_tariff1': None,
                             'injection_tariff2': None,
                             'voltage': {'phase1': None, 'phase2': None, 'phase3': None}},
             'gas': {'ean': ''},
             'device_id': '11.0',
             'module_id': 10,
             'port_id': 0,
             'timestamp': 190527083152.0},
        ]
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._run_power_metrics('energy')
            assert enqueue.call_args_list == []

    def test_realtime_p1_gas_metrics(self):
        self.gateway_api.get_realtime_p1.return_value = [
            {'electricity': {'ean': ''},
             'gas': {'ean': '2222222222222222222222222222',
                     'consumption': 2.3},
             'device_id': '11.0',
             'module_id': 10,
             'port_id': 0,
             'timestamp': 190527083152.0},
        ]
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._run_power_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy_p1',
                                      tags={'type': 'openmotics', 'id': '11.0',
                                            'ean': '2222222222222222222222222222'},
                                      values={'gas_consumption': 2.3})
            assert enqueue.call_args_list == [expected_call]

    def test_realtime_p1_gas_no_metrics(self):
        self.gateway_api.get_realtime_p1.return_value = [
            {'electricity': {'ean': ''},
             'gas': {'ean': '2222222222222222222222222222',
                     'consumption': None},
             'device_id': '11.0',
             'module_id': 10,
             'port_id': 0,
             'timestamp': 190527083152.0},
        ]
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._run_power_metrics('energy')
            assert enqueue.call_args_list == []

    def test_total_power_metrics(self):
        self.gateway_api.get_total_energy.return_value = {'10': [[10.0, 2.1]]}
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._run_power_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy',
                                      tags={'type': 'openmotics', 'id': '11.0', 'name': 'foo'},
                                      values={'counter_day': 10.0, 'counter_night': 2.1, 'counter': 12.1})
            assert enqueue.call_args_list == [expected_call]
