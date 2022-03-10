# Copyright (C) 2021 OpenMotics BV
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
import xmlrunner
import mock
import logging
from datetime import datetime
from gateway.events import GatewayEvent
from gateway.enums import EnergyEnums, ModuleType
from gateway.pubsub import PubSub
from gateway.dto import ModuleDTO, EnergyModuleDTO, RealtimeEnergyDTO, TotalEnergyDTO
from gateway.energy_module_controller import EnergyModuleController
from gateway.models import Module, EnergyModule, EnergyCT, Base, Database
from gateway.energy.energy_api import EnergyAPI, NIGHT
from gateway.energy.energy_communicator import EnergyCommunicator
from ioc import SetTestMode, SetUpTestInjections
from sqlalchemy import create_engine, select
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool
from serial_utils import RS485
from serial_test import SerialMock, sin, sout
from enums import HardwareType
from logs import Logs

MODELS = [Module, EnergyModule, EnergyCT]


class EnergyModuleControllerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super(EnergyModuleControllerTest, cls).setUpClass()
        SetTestMode()
        Logs.set_loglevel(logging.DEBUG, namespace='gateway.energy_module_controller')
        Logs.set_loglevel(logging.DEBUG, namespace='sqlalchemy.engine')

    @classmethod
    def tearDownClass(cls):
        super(EnergyModuleControllerTest, cls).tearDownClass()

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=True, bind=engine)

        self.session = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()
        self.addCleanup(session_mock.stop)

        self.pubsub = PubSub()  # triggering manually
        SetUpTestInjections(pubsub=self.pubsub,
                            master_controller=None,
                            maintenance_controller=None,
                            energy_module_updater=None)
        self.energy_data = []  # type: list
        self.serial = RS485(SerialMock(self.energy_data))
        SetUpTestInjections(energy_serial=self.serial)
        SetUpTestInjections(energy_communicator=EnergyCommunicator())
        self.controller = EnergyModuleController()

    def tearDown(self):
        self.serial.stop()

    def _setup_module(self, version=EnergyEnums.Version.ENERGY_MODULE, address='1', number=1):
        with self.session as db:
            module = Module(address=address,
                            source=ModuleDTO.Source.GATEWAY,
                            module_type={EnergyEnums.Version.POWER_MODULE: ModuleType.POWER,
                                         EnergyEnums.Version.ENERGY_MODULE: ModuleType.ENERGY,
                                         EnergyEnums.Version.P1_CONCENTRATOR: ModuleType.P1_CONCENTRATOR}[version],
                            hardware_type=HardwareType.PHYSICAL)
            db.add(module)
            energy_module = EnergyModule(version=version,
                                         number=number,
                                         module=module)
            db.add(energy_module)

            cts = []
            for i in range(EnergyEnums.NUMBER_OF_PORTS[version]):
                ct = EnergyCT(number=i,
                              sensor_type=2,
                              times='',
                              energy_module=energy_module)
                cts.append(ct)
            db.add_all(cts)
            db.commit()

    def test_time_sync(self):
        times = "00:10,00:20,00:30,00:40,00:50,01:00,01:10,01:20,01:30,01:40,01:50,02:00,02:10,02:20"

        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 4, 0, 0, 0)))  # Monday 00:00
        self.assertTrue(EnergyModuleController._is_day_time(times, datetime(2013, 3, 4, 0, 10, 0)))  # Monday 00:10
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 4, 0, 20, 0)))  # Monday 00:20
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 4, 12, 0, 0)))  # Monday 12:00

        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 5, 0, 0, 0)))  # Tuesday 00:00
        self.assertTrue(EnergyModuleController._is_day_time(times, datetime(2013, 3, 5, 0, 30, 0)))  # Tuesday 00:30
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 5, 0, 40, 0)))  # Tuesday 00:40
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 5, 12, 0, 0)))  # Tuesday 12:00

        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 6, 0, 0, 0)))  # Wednesday 00:00
        self.assertTrue(EnergyModuleController._is_day_time(times, datetime(2013, 3, 6, 0, 50, 0)))  # Wednesday 00:50
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 6, 1, 00, 0)))  # Wednesday 01:00
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 6, 12, 0, 0)))  # Wednesday 12:00

        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 7, 0, 0, 0)))  # Thursday 00:00
        self.assertTrue(EnergyModuleController._is_day_time(times, datetime(2013, 3, 7, 1, 10, 0)))  # Thursday 01:10
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 7, 1, 20, 0)))  # Thursday 01:20
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 7, 12, 0, 0)))  # Thursday 12:00

        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 8, 0, 0, 0)))  # Friday 00:00
        self.assertTrue(EnergyModuleController._is_day_time(times, datetime(2013, 3, 8, 1, 30, 0)))  # Friday 01:30
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 8, 1, 40, 0)))  # Friday 01:40
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 8, 12, 0, 0)))  # Friday 12:00

        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 9, 0, 0, 0)))  # Saturday 00:00
        self.assertTrue(EnergyModuleController._is_day_time(times, datetime(2013, 3, 9, 1, 50, 0)))  # Saturday 01:50
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 9, 2, 0, 0)))  # Saturday 02:00
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 9, 12, 0, 0)))  # Saturday 12:00

        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 10, 0, 0, 0)))  # Sunday 00:00
        self.assertTrue(EnergyModuleController._is_day_time(times, datetime(2013, 3, 10, 2, 10, 0)))  # Sunday 02:10
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 10, 2, 20, 0)))  # Sunday 02:20
        self.assertFalse(EnergyModuleController._is_day_time(times, datetime(2013, 3, 10, 12, 0, 0)))  # Sunday 12:00

        self.assertFalse(EnergyModuleController._is_day_time(None, datetime(2013, 3, 10, 0, 0, 0)))  # Sunday 00:00
        self.assertFalse(EnergyModuleController._is_day_time(None, datetime(2013, 3, 10, 6, 10, 0)))  # Sunday 06:00
        self.assertFalse(EnergyModuleController._is_day_time(None, datetime(2013, 3, 10, 12, 20, 0)))  # Sunday 12:00
        self.assertFalse(EnergyModuleController._is_day_time(None, datetime(2013, 3, 10, 18, 0, 0)))  # Sunday 18:00

    def test_time_sync_calls(self):
        self._setup_module(version=EnergyEnums.Version.POWER_MODULE)

        time_action = EnergyAPI.set_day_night(EnergyEnums.Version.POWER_MODULE)
        times = [NIGHT for _ in range(8)]
        action = EnergyAPI.get_voltage(EnergyEnums.Version.POWER_MODULE)

        self.energy_data.extend([
            sin(time_action.create_input(1, 1, *times)),
            sout(time_action.create_output(1, 1)),
            sin(action.create_input(1, 2)),
            sout(action.create_output(1, 2, 243))
        ])
        self.serial.start()

        self.controller._sync_time()
        self.assertEqual((243, ), self.controller._energy_communicator.do_command(1, action))

    def test_config_event(self):
        events = []

        def handle_events(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_events)

        self.controller._discovery_stopped()
        self.pubsub._publish_all_events(blocking=False)

        assert GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'powermodule'}) in events
        assert len(events) == 1

    def test_get_energy_modules(self):
        self._setup_module(version=EnergyEnums.Version.POWER_MODULE, address='11', number=1)
        self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address='21', number=2)
        result = self.controller.load_modules()
        default_kwargs = {}
        for field, default in {'input{0}': '', 'sensor{0}': 2, 'times{0}': '', 'inverted{0}': False}.items():
            for i in range(8):
                default_kwargs[field.format(i)] = default
        self.assertEqual([EnergyModuleDTO(id=1, address=11, name='', version=8, **default_kwargs),
                          EnergyModuleDTO(id=2, address=21, name='', version=1, **default_kwargs)], result)

    def test_get_realtime_power(self):
        self._setup_module(version=EnergyEnums.Version.POWER_MODULE, address='11', number=10)
        with mock.patch.object(self.controller._power_module_helper, '_get_currents', return_value=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]), \
                mock.patch.object(self.controller._power_module_helper, '_get_frequencies', return_value=[1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1]), \
                mock.patch.object(self.controller._power_module_helper, '_get_powers', return_value=[1.2, 2.2, 3.2, 4.2, 5.2, 6.2, 7.2, 8.2]), \
                mock.patch.object(self.controller._power_module_helper, '_get_voltages', return_value=[1.3, 2.3, 3.3, 4.3, 5.3, 6.3, 7.3, 8.3]):
            result = self.controller.get_realtime_energy()
            self.assertEqual({'10': [RealtimeEnergyDTO(voltage=i + 0.3, frequency=i + 0.1, current=i + 0.0, power=i + 0.2)
                                     for i in range(1, 9)]}, result)

    def test_get_realtime_energy(self):
        self._setup_module(version=EnergyEnums.Version.ENERGY_MODULE, address='11', number=10)
        with mock.patch.object(self.controller._energy_module_helper, '_get_currents', return_value=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]), \
                mock.patch.object(self.controller._energy_module_helper, '_get_frequencies', return_value=[1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1, 9.1, 10.1, 11.1, 12.1]), \
                mock.patch.object(self.controller._energy_module_helper, '_get_powers', return_value=[1.2, 2.2, 3.2, 4.2, 5.2, 6.2, 7.2, 8.2, 9.2, 10.2, 11.2, 12.2]), \
                mock.patch.object(self.controller._energy_module_helper, '_get_voltages', return_value=[1.3, 2.3, 3.3, 4.3, 5.3, 6.3, 7.3, 8.3, 9.3, 10.3, 11.3, 12.3]):
            result = self.controller.get_realtime_energy()
            self.assertEqual({'10': [RealtimeEnergyDTO(voltage=i + 0.3, frequency=i + 0.1, current=i + 0.0, power=i + 0.2)
                                     for i in range(1, 13)]}, result)

    def test_get_realtime_energy_p1(self):
        self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address='11', number=10)
        statuses = [True, True, False, True, False, False, False, False]
        with mock.patch.object(self.controller._p1c_helper, '_get_statuses', return_value=statuses), \
                mock.patch.object(self.controller._p1c_helper, '_get_phase_currents', return_value=[{'phase1': 1.1, 'phase2': 0.2, 'phase3': 0.3},
                                                                                                    {'phase1': 2.1, 'phase2': 0.2, 'phase3': 0.3},
                                                                                                    {'phase1': 3.1, 'phase2': 0.2, 'phase3': 0.3},
                                                                                                    {'phase1': 4.1, 'phase2': 0.2, 'phase3': 0.3},
                                                                                                    {'phase1': 5.1, 'phase2': 0.2, 'phase3': 0.3},
                                                                                                    {'phase1': 6.1, 'phase2': 0.2, 'phase3': 0.3},
                                                                                                    {'phase1': 7.1, 'phase2': 0.2, 'phase3': 0.3},
                                                                                                    {'phase1': 8.1, 'phase2': 0.2, 'phase3': 0.3}]), \
                mock.patch.object(self.controller._p1c_helper, '_get_frequencies', return_value=[1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1]), \
                mock.patch.object(self.controller._p1c_helper, '_get_delivered_powers', return_value=[1.2, 2.2, 3.2, 4.2, 5.2, 6.2, 7.2, 8.2]), \
                mock.patch.object(self.controller._p1c_helper, '_get_received_powers', return_value=[0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]), \
                mock.patch.object(self.controller._p1c_helper, '_get_phase_voltages', return_value=[{'phase1': 1.1, 'phase2': 0.1, 'phase3': 0.1},
                                                                                                    {'phase1': 2.1, 'phase2': 0.1, 'phase3': 0.1},
                                                                                                    {'phase1': 3.1, 'phase2': 0.1, 'phase3': 0.1},
                                                                                                    {'phase1': 4.1, 'phase2': 0.1, 'phase3': 0.1},
                                                                                                    {'phase1': 5.1, 'phase2': 0.1, 'phase3': 0.1},
                                                                                                    {'phase1': 6.1, 'phase2': 0.1, 'phase3': 0.1},
                                                                                                    {'phase1': 7.1, 'phase2': 0.1, 'phase3': 0.1},
                                                                                                    {'phase1': 8.1, 'phase2': 0.1, 'phase3': 0.1}]):
            result = self.controller.get_realtime_energy()
            self.assertEqual({'10': [RealtimeEnergyDTO(voltage=i + 0.1, frequency=i + 0.1, current=i + 0.6, power=i * 1000) if statuses[i - 1] else
                                     RealtimeEnergyDTO(voltage=0.0, frequency=0.0, current=0.0, power=0.0)
                                     for i in range(1, 9)]}, result)

    def test_get_realtime_energy_p1_partial(self):
        self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address='11', number=10)
        statuses = [True, True, False, True, False, False, False, False]
        with mock.patch.object(self.controller._p1c_helper, '_get_statuses', return_value=statuses), \
                mock.patch.object(self.controller._p1c_helper, '_get_phase_currents', return_value=[{'phase1': 1.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 2.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 3.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 4.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 5.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 6.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 7.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 8.1, 'phase2': None, 'phase3': None}]), \
                mock.patch.object(self.controller._p1c_helper, '_get_frequencies', return_value=[1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1]), \
                mock.patch.object(self.controller._p1c_helper, '_get_delivered_powers', return_value=[1.2, 2.2, 3.2, 4.2, 5.2, 6.2, 7.2, 8.2]), \
                mock.patch.object(self.controller._p1c_helper, '_get_received_powers', return_value=[None, None, None, None, None, None, None, None]), \
                mock.patch.object(self.controller._p1c_helper, '_get_phase_voltages', return_value=[{'phase1': 1.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 2.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 3.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 4.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 5.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 6.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 7.1, 'phase2': None, 'phase3': None},
                                                                                                    {'phase1': 8.1, 'phase2': None, 'phase3': None}]):
            result = self.controller.get_realtime_energy()
            self.assertEqual({'10': [RealtimeEnergyDTO(voltage=i + 0.1, frequency=i + 0.1, current=i + 0.1, power=(i + 0.2) * 1000) if statuses[i - 1] else
                                     RealtimeEnergyDTO(voltage=0.0, frequency=0.0, current=0.0, power=0.0)
                                     for i in range(1, 9)]}, result)

    def test_get_total_energy(self):
        self._setup_module(version=EnergyEnums.Version.POWER_MODULE, address='11', number=10)
        with mock.patch.object(self.controller._power_module_helper, 'get_day_counters', return_value=[1, 2, 3, 4, 5, 6, 7, 8]), \
                mock.patch.object(self.controller._power_module_helper, 'get_night_counters', return_value=[2, 3, 4, 5, 6, 7, 8, 9]):
            result = self.controller.get_total_energy()
            self.assertEqual({'10': [TotalEnergyDTO(night=i + 1, day=i)
                                     for i in range(1, 9)]}, result)

    def test_get_total_energy_p1(self):
        self._setup_module(version=EnergyEnums.Version.P1_CONCENTRATOR, address='11', number=10)
        statuses = [True, True, False, True, False, False, False, False]
        with mock.patch.object(self.controller._p1c_helper, '_get_statuses', return_value=statuses), \
                mock.patch.object(self.controller._p1c_helper, 'get_day_counters', return_value=[1, 2, 3, 4, 5, 6, 7, 8]), \
                mock.patch.object(self.controller._p1c_helper, 'get_night_counters', return_value=[2, 3, 4, 5, 6, 7, 8, 9]):
            result = self.controller.get_total_energy()
            self.assertEqual({'10': [TotalEnergyDTO(night=i + 1, day=i)
                                     for i in range(1, 9)]}, result)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
