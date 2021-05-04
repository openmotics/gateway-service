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

from bus.om_bus_client import MessageClient
from gateway.gateway_api import GatewayApi
from gateway.hal.master_controller import MasterController
from gateway.output_controller import OutputController
from ioc import SetTestMode, SetUpTestInjections
from power.power_api import ENERGY_MODULE, P1_CONCENTRATOR, POWER_MODULE, \
    RealtimePower
from power.power_communicator import PowerCommunicator
from power.power_controller import P1Controller, PowerController
from power.power_store import PowerStore


class GatewayApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.output_controller = mock.Mock(OutputController)
        self.power_store = mock.Mock(PowerStore)
        self.power_controller = mock.Mock(PowerController)
        self.p1_controller = mock.Mock(P1Controller)
        SetUpTestInjections(master_controller=mock.Mock(MasterController),
                            message_client=mock.Mock(MessageClient),
                            output_controller=self.output_controller,
                            p1_controller=self.p1_controller,
                            power_communicator=mock.Mock(PowerCommunicator),
                            power_controller=self.power_controller,
                            power_store=self.power_store)
        self.api = GatewayApi()

    def test_get_power_modules(self):
        self.power_store.get_power_modules.return_value = {
            10: {'address': 11, 'name': 'Power', 'version': POWER_MODULE},
            20: {'address': 21, 'name': 'P1', 'version': P1_CONCENTRATOR},
        }
        result = self.api.get_power_modules()
        assert result == [
            {'address': 'E11', 'name': 'Power', 'version': 8},
            {'address': 'C21', 'name': 'P1', 'version': 1}
        ]

    def test_get_realtime_power(self):
        self.power_store.get_power_modules.return_value = {10: {'address': 11, 'version': POWER_MODULE}}
        self.power_controller.get_module_current.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        self.power_controller.get_module_frequency.return_value = [1.0]
        self.power_controller.get_module_power.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        self.power_controller.get_module_voltage.return_value = [1.0]
        result = self.api.get_realtime_power()
        assert result == {
            '10': [
                RealtimePower(1.0, 1.0, 1.0, 1.0),
                RealtimePower(1.0, 1.0, 2.0, 2.0),
                RealtimePower(1.0, 1.0, 3.0, 3.0),
                RealtimePower(1.0, 1.0, 4.0, 4.0),
                RealtimePower(1.0, 1.0, 5.0, 5.0),
                RealtimePower(1.0, 1.0, 6.0, 6.0),
                RealtimePower(1.0, 1.0, 7.0, 7.0),
                RealtimePower(1.0, 1.0, 8.0, 8.0)
            ]
        }

    def test_get_realtime_energy(self):
        self.power_store.get_power_modules.return_value = {10: {'address': 11, 'version': ENERGY_MODULE}}
        self.power_controller.get_module_current.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        self.power_controller.get_module_frequency.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        self.power_controller.get_module_power.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        self.power_controller.get_module_voltage.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        result = self.api.get_realtime_power()
        assert result == {
            '10': [
                RealtimePower(1.0, 1.0, 1.0, 1.0),
                RealtimePower(2.0, 2.0, 2.0, 2.0),
                RealtimePower(3.0, 3.0, 3.0, 3.0),
                RealtimePower(4.0, 4.0, 4.0, 4.0),
                RealtimePower(5.0, 5.0, 5.0, 5.0),
                RealtimePower(6.0, 6.0, 6.0, 6.0),
                RealtimePower(7.0, 7.0, 7.0, 7.0),
                RealtimePower(8.0, 8.0, 8.0, 8.0),
                RealtimePower(9.0, 9.0, 9.0, 9.0),
                RealtimePower(10.0, 10.0, 10.0, 10.0),
                RealtimePower(11.0, 11.0, 11.0, 11.0),
                RealtimePower(12.0, 12.0, 12.0, 12.0),
            ]
        }

    def test_get_realtime_power_p1(self):
        self.power_store.get_power_modules.return_value = {10: {'address': 11, 'version': P1_CONCENTRATOR}}
        self.p1_controller.get_module_status.return_value = [
                True, True, False, True,
                False, False, False, False
        ]
        self.p1_controller.get_module_current.return_value = [
            {'phase1': 1.0, 'phase2': 1.0, 'phase3': 1.0},
            {'phase1': 2.0, 'phase2': 2.0, 'phase3': 2.0},
            {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
            {'phase1': 12.0, 'phase2': 12.0, 'phase3': 12.0},
        ]
        self.p1_controller.get_module_voltage.return_value = [
            {'phase1': 1.0, 'phase2': 1.0, 'phase3': 1.0},
            {'phase1': 2.3, 'phase2': 2.3, 'phase3': 2.3},
            {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
            {'phase1': 12.0, 'phase2': 12.0, 'phase3': 12.0},
        ]
        self.p1_controller.get_module_delivered_power.return_value = [2.0, 3.0, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0]
        self.p1_controller.get_module_received_power.return_value = [1.0, 3.0, 0.0, 12.0, 0.0, 0.0, 0.0, 0.0]
        result = self.api.get_realtime_power()
        assert result == {
            '10': [
                RealtimePower(1.0, 0.0, 3.0, 1000.0),
                RealtimePower(2.3, 0.0, 6.0, 0.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0),
                RealtimePower(12.0, 0.0, 36.0, -2000.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0)
            ]
        }

    def test_get_realtime_power_p1_partial(self):
        self.power_store.get_power_modules.return_value = {10: {'address': 11, 'version': P1_CONCENTRATOR}}
        self.p1_controller.get_module_status.return_value = [
                True, True, False, True,
                False, False, False, False
        ]
        self.p1_controller.get_module_current.return_value = [
            {'phase1': 1.0, 'phase2': None, 'phase3': None},
            {'phase1': 2.0, 'phase2': None, 'phase3': None},
            {'phase1': 0.0, 'phase2': None, 'phase3': None},
            {'phase1': 12.0, 'phase2': None, 'phase3': None},
        ]
        self.p1_controller.get_module_voltage.return_value = [
            {'phase1': 1.0, 'phase2': None, 'phase3': None},
            {'phase1': 2.3, 'phase2': None, 'phase3': None},
            {'phase1': 0.0, 'phase2': None, 'phase3': None},
            {'phase1': 12.0, 'phase2': None, 'phase3': None},
        ]
        self.p1_controller.get_module_delivered_power.return_value = [2.0, 3.0, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0]
        self.p1_controller.get_module_received_power.return_value = [None, None, None, None, None, None, None, None]
        result = self.api.get_realtime_power()
        assert result == {
            '10': [
                RealtimePower(1.0, 0.0, 1.0, 2000.0),
                RealtimePower(2.3, 0.0, 2.0, 3000.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0),
                RealtimePower(12.0, 0.0, 12.0, 10000.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0),
                RealtimePower(0.0, 0.0, 0.0, 0.0)
            ]
        }

    def test_get_total_energy(self):
        self.power_store.get_power_modules.return_value = {10: {'address': 11, 'version': POWER_MODULE}}
        self.power_controller.get_module_day_energy.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        self.power_controller.get_module_night_energy.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        result = self.api.get_total_energy()
        assert result == {
            '10': [[1.0, 1.0],
                  [2.0, 2.0],
                  [3.0, 3.0],
                  [4.0, 4.0],
                  [5.0, 5.0],
                  [6.0, 6.0],
                  [7.0, 7.0],
                  [8.0, 8.0]]
        }

    def test_get_total_energy_p1(self):
        self.power_store.get_power_modules.return_value = {10: {'address': 11, 'version': P1_CONCENTRATOR}}
        self.p1_controller.get_module_status.return_value = [
                True, True, False, True,
                False, False, False, False
        ]
        self.p1_controller.get_module_day_energy.return_value = [0.001, 0.002, 0.0, 0.012, 0.0, 0.0, 0.0, 0.0]
        self.p1_controller.get_module_night_energy.return_value = [0.002, 0.003, 0.0, 0.024, 0.0, 0.0, 0.0, 0.0]
        result = self.api.get_total_energy()
        assert result == {
            '10': [[1, 2],
                  [2, 3],
                  [None, None],
                  [12, 24],
                  [None, None],
                  [None, None],
                  [None, None],
                  [None, None]]
        }
