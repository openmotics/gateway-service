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
from gateway.dto import SensorDTO, SensorStatusDTO, RealtimeEnergyDTO, EnergyModuleDTO, TotalEnergyDTO
from gateway.metrics_collector import MetricsCollector
from gateway.sensor_controller import SensorController
from ioc import Scope, SetTestMode, SetUpTestInjections


class MetricsCollectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    @Scope
    def setUp(self):
        dto_kwargs = {}
        for i in range(8):
            dto_kwargs.update({'input{0}'.format(i): '',
                               'sensor{0}'.format(i): 2,
                               'times{0}'.format(i): '',
                               'inverted{0}'.format(i): False})
        dto_kwargs.update({'input0': 'foo',
                           'input1': 'bar',
                           'input2': 'baz'})
        self.em_controller = mock.Mock()
        self.em_controller.load_modules.return_value = [
            EnergyModuleDTO(id=10, address=11, version=1, name='foo',
                            **dto_kwargs)
        ]
        self.em_controller.get_realtime_energy.return_value = {}
        self.em_controller.get_realtime_p1.return_value = {}
        self.em_controller.get_total_energy.return_value = {}
        self.sensor_controller = mock.Mock(SensorController)
        SetUpTestInjections(energy_module_controller=self.em_controller,
                            pulse_counter_controller=mock.Mock(),
                            thermostat_controller=mock.Mock(),
                            output_controller=mock.Mock(),
                            input_controller=mock.Mock(),
                            sensor_controller=self.sensor_controller,
                            module_controller=mock.Mock())
        self.controller = MetricsCollector()

    def test_sensor_metrics(self):
        sensor_dto = SensorDTO(id=42, source='master', external_id='0', physical_quantity='temperature', unit='celcius', name='foo')
        self.controller._environment_sensors = {42: sensor_dto}
        self.sensor_controller.get_sensors_status.return_value = [SensorStatusDTO(id=42, value=21.0)]
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._process_sensors('sensor')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='sensor',
                                      tags={'id': 42, 'unit': 'celcius', 'name': 'foo'},
                                      values={'temperature': 21.0})
            assert enqueue.call_args_list == [expected_call]

    def test_realtime_energy_metrics(self):
        self.em_controller.get_realtime_energy.return_value = {'10': [RealtimeEnergyDTO(voltage=10.0,
                                                                                        frequency=2.1,
                                                                                        current=5.0,
                                                                                        power=3.6)]}
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._process_energy_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy',
                                      tags={'type': 'openmotics', 'id': '11.0', 'name': 'foo'},
                                      values={'current': 5.0, 'frequency': 2.1, 'power': 3.6, 'voltage': 10.0})
            self.assertEqual([expected_call], enqueue.call_args_list)

    def test_realtime_p1_electricity_metrics(self):
        self.em_controller.get_realtime_p1.return_value = [
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
            self.controller._process_energy_metrics('energy')
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
        self.em_controller.get_realtime_p1.return_value = [
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
            self.controller._process_energy_metrics('energy')
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
        self.em_controller.get_realtime_p1.return_value = [
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
            self.controller._process_energy_metrics('energy')
            assert enqueue.call_args_list == []

    def test_realtime_p1_gas_metrics(self):
        self.em_controller.get_realtime_p1.return_value = [
            {'electricity': {'ean': ''},
             'gas': {'ean': '2222222222222222222222222222',
                     'consumption': 2.3},
             'device_id': '11.0',
             'module_id': 10,
             'port_id': 0,
             'timestamp': 190527083152.0},
        ]
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._process_energy_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy_p1',
                                      tags={'type': 'openmotics', 'id': '11.0',
                                            'ean': '2222222222222222222222222222'},
                                      values={'gas_consumption': 2.3})
            assert enqueue.call_args_list == [expected_call]

    def test_realtime_p1_gas_no_metrics(self):
        self.em_controller.get_realtime_p1.return_value = [
            {'electricity': {'ean': ''},
             'gas': {'ean': '2222222222222222222222222222',
                     'consumption': None},
             'device_id': '11.0',
             'module_id': 10,
             'port_id': 0,
             'timestamp': 190527083152.0},
        ]
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._process_energy_metrics('energy')
            assert enqueue.call_args_list == []

    def test_total_energy_metrics(self):
        self.em_controller.get_total_energy.return_value = {'10': [TotalEnergyDTO(day=10, night=2)]}
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._process_energy_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy',
                                      tags={'type': 'openmotics', 'id': '11.0', 'name': 'foo'},
                                      values={'counter_day': 10, 'counter_night': 2, 'counter': 12})
            self.assertEqual([expected_call], enqueue.call_args_list)
