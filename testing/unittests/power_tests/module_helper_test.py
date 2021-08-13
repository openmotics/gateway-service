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
Tests for the energy helpers
"""

from __future__ import absolute_import

import unittest

import mock

from gateway.enums import EnergyEnums, HardwareType
from gateway.pubsub import PubSub
from gateway.models import Module, EnergyModule, EnergyCT
from gateway.dto import ModuleDTO
from ioc import SetTestMode, SetUpTestInjections
from gateway.energy.energy_command import EnergyCommand
from gateway.energy.module_helper_energy import EnergyModuleHelper
from gateway.energy.module_helper_p1c import P1ConcentratorHelper
from peewee import SqliteDatabase

MODELS = [Module, EnergyModule, EnergyCT]


class EnergyModuleHelperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.pubsub = PubSub()
        SetUpTestInjections(pubsub=self.pubsub)
        self.energy_communicator = mock.Mock()
        SetUpTestInjections(energy_communicator=self.energy_communicator)
        self.helper = EnergyModuleHelper()

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def _setup_module(self, version, address):
        module = Module(address=address,
                        source=ModuleDTO.Source.GATEWAY,
                        hardware_type=HardwareType.PHYSICAL)
        module.save()
        energy_module = EnergyModule(version=version,
                                     number=address,
                                     module=module)
        energy_module.save()
        for i in range(8):
            ct = EnergyCT(number=i,
                          sensor_type=2,
                          times='',
                          energy_module=energy_module)
            ct.save()
        return energy_module

    def test_get_currents(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.POWER_MODULE,
                                           address='11')
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            self.helper._get_currents(energy_module)
            self.assertEqual([mock.call(11, EnergyCommand('G', 'CUR', '', '8f', module_type=bytearray(b'E')))],
                             cmd.call_args_list)

    def test_get_frequencies(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.POWER_MODULE,
                                           address='11')
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            self.helper._get_frequencies(energy_module)
            self.assertEqual([mock.call(11, EnergyCommand('G', 'FRE', '', 'f', module_type=bytearray(b'E')))],
                             cmd.call_args_list)
        energy_module = self._setup_module(version=EnergyEnums.Version.ENERGY_MODULE,
                                           address='10')
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            self.helper._get_frequencies(energy_module)
            self.assertEqual([mock.call(10, EnergyCommand('G', 'FRE', '', '12f', module_type=bytearray(b'E')))],
                             cmd.call_args_list)

    def test_get_powers(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.POWER_MODULE,
                                           address='11')
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            self.helper._get_powers(energy_module)
            self.assertEqual([mock.call(11, EnergyCommand('G', 'POW', '', '8f', module_type=bytearray(b'E')))],
                             cmd.call_args_list)

    def test_get_module_voltage(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.POWER_MODULE,
                                           address='11')
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            self.helper._get_voltages(energy_module)
            self.assertEqual([mock.call(11, EnergyCommand('G', 'VOL', '', 'f', module_type=bytearray(b'E')))],
                             cmd.call_args_list)
        energy_module = self._setup_module(version=EnergyEnums.Version.ENERGY_MODULE,
                                           address='10')
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            self.helper._get_voltages(energy_module)
            self.assertEqual([mock.call(10, EnergyCommand('G', 'VOL', '', '12f', module_type=bytearray(b'E')))],
                             cmd.call_args_list)

    def test_get_module_day_energy(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.POWER_MODULE,
                                           address='11')
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            self.helper.get_day_counters(energy_module)
            self.assertEqual([mock.call(11, EnergyCommand('G', 'EDA', '', '8L', module_type=bytearray(b'E')))],
                             cmd.call_args_list)

    def test_get_module_night_energy(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.POWER_MODULE,
                                           address='11')
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            self.helper.get_night_counters(energy_module)
            self.assertEqual([mock.call(11, EnergyCommand('G', 'ENI', '', '8L', module_type=bytearray(b'E')))],
                             cmd.call_args_list)

    def test_configure_cts(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.ENERGY_MODULE,
                                           address='11')
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            ct = energy_module.cts[0]
            ct.sensor_type = 5
            ct.inverted = True
            ct.save()
            self.helper.configure_cts(energy_module=energy_module)
            self.assertEqual([mock.call(11, EnergyCommand('S', 'CCF', '12f', ''), 4.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
                              mock.call(11, EnergyCommand('S', 'SCI', '=12B', ''), 1, 0, 0, 0, 0, 0, 0, 0)],
                             cmd.call_args_list)


class P1ControllerTest(unittest.TestCase):

    # TODO: Use more accurate payloads

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.energy_communicator = mock.Mock()
        SetUpTestInjections(energy_communicator=self.energy_communicator)
        self.helper = P1ConcentratorHelper()

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def _setup_module(self, version, address):
        module = Module(address=address,
                        source=ModuleDTO.Source.GATEWAY,
                        hardware_type=HardwareType.PHYSICAL)
        module.save()
        energy_module = EnergyModule(version=version,
                                     number=1,
                                     module=module)
        energy_module.save()
        for i in range(EnergyEnums.NUMBER_OF_PORTS[version]):
            ct = EnergyCT(number=i,
                          sensor_type=2,
                          times='',
                          energy_module=energy_module)
            ct.save()
        return energy_module

    def test_get_realtime_p1(self):
        with mock.patch.object(self.helper, '_get_statuses',
                               return_value=[
                                   True, True, False, True,
                                   False, False, False, False
                               ]), \
             mock.patch.object(self.helper, '_get_meter',
                               side_effect=([
                                   '1111111111111111111111111111',
                                   '3333333333333333333333333333',
                                   '                            ',
                                   '                            '
                               ], [
                                   '2222222222222222222222222222',
                                   '                            ',
                                   '                            ',
                                   '4444444444444444444444444444'
                               ])), \
             mock.patch.object(self.helper, '_get_timestamp',
                               return_value=[1.0, 2.0, 0.0, 190527083152.0]), \
             mock.patch.object(self.helper, '_get_gas_consumption',
                               return_value=[1.0, 2.3, 0.0, 12.0]), \
             mock.patch.object(self.helper, '_get_consumption_tariff',
                               return_value=[1.0, 2.3, 0.0, 12.0]), \
             mock.patch.object(self.helper, '_get_injection_tariff',
                               return_value=[1.0, 2.3, 0.0, 12.0]), \
             mock.patch.object(self.helper, '_get_tariff_indicator',
                               return_value=[1.0, 2.0, 0.0, 12.0]), \
             mock.patch.object(self.helper, '_get_phase_currents',
                               return_value=[
                                   {'phase1': 1.0, 'phase2': 1.0, 'phase3': 1.0},
                                   {'phase1': 2.0, 'phase2': 2.0, 'phase3': 2.0},
                                   {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                                   {'phase1': 12.0, 'phase2': 12.0, 'phase3': 12.0},
                               ]), \
             mock.patch.object(self.helper, '_get_phase_voltages',
                               return_value=[
                                   {'phase1': 1.0, 'phase2': 1.0, 'phase3': 1.0},
                                   {'phase1': 2.3, 'phase2': 2.3, 'phase3': 2.3},
                                   {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                                   {'phase1': 12.0, 'phase2': 12.0, 'phase3': 12.0},
                               ]), \
             mock.patch.object(self.helper, '_get_delivered_powers',
                               return_value=[2.0, 3.0, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0]), \
             mock.patch.object(self.helper, '_get_received_powers',
                               return_value=[1.0, 3.0, 0.0, 12.0, 0.0, 0.0, 0.0, 0.0]):
            result = self.helper.get_realtime_p1(self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR,
                                                                    address=10))
            self.assertEqual([
                {'electricity': {'current': {'phase1': 1.0, 'phase2': 1.0, 'phase3': 1.0},
                                 'ean': '1111111111111111111111111111',
                                 'tariff_indicator': 1.0,
                                 'consumption_tariff1': 1.0,
                                 'consumption_tariff2': 1.0,
                                 'injection_tariff1': 1.0,
                                 'injection_tariff2': 1.0,
                                 'voltage': {'phase1': 1.0, 'phase2': 1.0, 'phase3': 1.0}},
                 'gas': {'consumption': 1.0, 'ean': '2222222222222222222222222222'},
                 'device_id': '10.0',
                 'module_id': 1,
                 'port_id': 0,
                 'timestamp': 1.0},
                {'electricity': {'current': {'phase1': 2.0, 'phase2': 2.0, 'phase3': 2.0},
                                 'ean': '3333333333333333333333333333',
                                 'tariff_indicator': 2.0,
                                 'consumption_tariff1': 2.3,
                                 'consumption_tariff2': 2.3,
                                 'injection_tariff1': 2.3,
                                 'injection_tariff2': 2.3,
                                 'voltage': {'phase1': 2.3, 'phase2': 2.3, 'phase3': 2.3}},
                 'gas': {'consumption': 2.3, 'ean': ''},
                 'device_id': '10.1',
                 'module_id': 1,
                 'port_id': 1,
                 'timestamp': 2.0},
                {'electricity': {'current': {'phase1': 12.0,
                                             'phase2': 12.0,
                                             'phase3': 12.0},
                                 'ean': '',
                                 'tariff_indicator': 12.0,
                                 'consumption_tariff1': 12.0,
                                 'consumption_tariff2': 12.0,
                                 'injection_tariff1': 12.0,
                                 'injection_tariff2': 12.0,
                                 'voltage': {'phase1': 12.0,
                                             'phase2': 12.0,
                                             'phase3': 12.0}},
                 'gas': {'consumption': 12.0, 'ean': '4444444444444444444444444444'},
                 'device_id': '10.3',
                 'module_id': 1,
                 'port_id': 3,
                 'timestamp': 190527083152.0}
            ], result)

    def test_get_module_status(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = 0b00001011
        with mock.patch.object(self.energy_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            status = self.helper._get_statuses(energy_module)
            self.assertEqual([
                True, True, False, True,
                False, False, False, False
            ], status)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C')))
            ], cmd.call_args_list)

    def test_get_module_meter(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '11111111111111111111111111112222222222222222222222222222                            4444444444444444444444444444'
        with mock.patch.object(self.energy_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            meters = self.helper._get_meter(energy_module, meter_type=1)
            self.assertEqual([
                '1111111111111111111111111111',
                '2222222222222222222222222222',
                '                            ',
                '4444444444444444444444444444',
                '', '', '', '',
            ], meters)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'M1\x00', '', '224s', module_type=bytearray(b'C')))
            ], cmd.call_args_list)

    def test_get_module_timestamp(self):
        # TODO confirm this is correct
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '000000000001S000000000002              000000000012S000000000013S'
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload]]
            meters = self.helper._get_timestamp(energy_module)
            self.assertEqual([1.0, 2.0, None, 12.0, None, None, None, None], meters)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'TS\x00', '', '104s', module_type=bytearray(b'C'))),
            ], cmd.call_args_list)

    def test_get_module_gas(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '000000001*m300002.300*m3            00012.000*m300013.000*m3'
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload]]
            meters = self.helper._get_gas_consumption(energy_module)
            self.assertEqual([1.0, 2.3, None, 12.0, None, None, None, None], meters)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'cG\x00', '', '112s', module_type=bytearray(b'C')))
            ], cmd.call_args_list)

    def test_get_module_consumption_tariff(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '0000000001*kWh000002.300*kWh              000012.000*kWh000013.000*kWh'
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload]]
            meters = self.helper._get_consumption_tariff(energy_module, tariff_type=1)
            self.assertEqual([1.0, 2.3, None, 12.0, None, None, None, None], meters)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'c1\x00', '', '112s', module_type=bytearray(b'C')))
            ], cmd.call_args_list)

    def test_get_module_injection_tariff(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '0000000001*kWh000002.300*kWh              000012.000*kWh000013.000*kWh'
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload]]
            meters = self.helper._get_injection_tariff(energy_module, tariff_type=1)
            self.assertEqual([1.0, 2.3, None, 12.0, None, None, None, None], meters)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'i1\x00', '', '112s', module_type=bytearray(b'C')))
            ], cmd.call_args_list)

    def test_get_module_tariff_indicator(self):
        # TODO confirm this is correct
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '00010002    00120013'
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload]]
            meters = self.helper._get_tariff_indicator(energy_module)
            self.assertEqual([1.0, 2.0, None, 12.0, None, None, None, None], meters)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'ti\x00', '', '32s', module_type=bytearray(b'C')))
            ], cmd.call_args_list)

    def test_get_module_current(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload1 = '001  002  !42  012  013  '
        payload2 = '002  003  !43  013  014  '
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload1],
                               [0b00001011], [payload1],
                               [0b00001011], [payload2]]
            voltages = self.helper._get_phase_currents(energy_module)
            self.assertEqual([
                {'phase1': 1.0, 'phase2': 1.0, 'phase3': 2.0},
                {'phase1': 2.0, 'phase2': 2.0, 'phase3': 3.0},
                {'phase1': None, 'phase2': None, 'phase3': None},
                {'phase1': 12.0, 'phase2': 12.0, 'phase3': 13.0},
                {'phase1': None, 'phase2': None, 'phase3': None},
                {'phase1': None, 'phase2': None, 'phase3': None},
                {'phase1': None, 'phase2': None, 'phase3': None},
                {'phase1': None, 'phase2': None, 'phase3': None}
            ], voltages)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'C1\x00', '', '40s', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'C2\x00', '', '40s', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'C3\x00', '', '40s', module_type=bytearray(b'C')))
            ], cmd.call_args_list)

    def test_get_module_voltage(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload1 = '00001  002.3  !@#42  00012  00013  '
        payload2 = '00002  003.4  !@#43  00013  00014  '
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload1],
                               [0b00001011], [payload1],
                               [0b00001011], [payload2]]
            voltages = self.helper._get_phase_voltages(energy_module)
            self.assertEqual([
                {'phase1': 1.0, 'phase2': 1.0, 'phase3': 2.0},
                {'phase1': 2.3, 'phase2': 2.3, 'phase3': 3.4},
                {'phase1': None, 'phase2': None, 'phase3': None},
                {'phase1': 12.0, 'phase2': 12.0, 'phase3': 13.0},
                {'phase1': None, 'phase2': None, 'phase3': None},
                {'phase1': None, 'phase2': None, 'phase3': None},
                {'phase1': None, 'phase2': None, 'phase3': None},
                {'phase1': None, 'phase2': None, 'phase3': None}
            ], voltages)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'V1\x00', '', '56s', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'V2\x00', '', '56s', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'V3\x00', '', '56s', module_type=bytearray(b'C')))
            ], cmd.call_args_list)

    def test_get_module_delivered_power(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '000001   000002   !@#$42   000012   000013   '
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload]]
            delivered = self.helper._get_delivered_powers(energy_module)
            self.assertEqual([1.0, 2.0, None, 12.0, None, None, None, None], delivered)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'PD\x00', '', '72s', module_type=bytearray(b'C'))),
            ], cmd.call_args_list)

    def test_get_module_received_power(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '000001   000002   !@#$42   000012   000013   '
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload]]
            received = self.helper._get_received_powers(energy_module)
            self.assertEqual([1.0, 2.0, None, 12.0, None, None, None, None], received)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'PR\x00', '', '72s', module_type=bytearray(b'C'))),
            ], cmd.call_args_list)

    def test_get_module_day_energy(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '000000.001    000000.002    !@#$%^&*42    000000.012    000000.013    '
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload]]
            received = self.helper.get_day_counters(energy_module)
            self.assertEqual([1, 2, None, 12, None, None, None, None], received)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'c1\x00', '', '112s', module_type=bytearray(b'C'))),
            ], cmd.call_args_list)

    def test_get_module_night_energy(self):
        energy_module = self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address=11)
        payload = '000000.001    000000.002    !@#$%^&*42    000000.012    000000.013    '
        with mock.patch.object(self.energy_communicator, 'do_command') as cmd:
            cmd.side_effect = [[0b00001011], [payload]]
            received = self.helper.get_night_counters(energy_module)
            self.assertEqual([1, 2, None, 12, None, None, None, None], received)
            self.assertEqual([
                mock.call(11, EnergyCommand('G', 'SP\x00', '', 'B', module_type=bytearray(b'C'))),
                mock.call(11, EnergyCommand('G', 'c2\x00', '', '112s', module_type=bytearray(b'C'))),
            ], cmd.call_args_list)
