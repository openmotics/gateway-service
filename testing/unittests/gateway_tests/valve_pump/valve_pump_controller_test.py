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
import time
import unittest

import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

import fakesleep
from gateway.models import Base, Database, Output, Pump, \
    PumpToValveAssociation, Valve
from gateway.output_controller import OutputController
from gateway.valve_pump.valve_pump_controller import ValvePumpController
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs

MODELS = [Pump, Output, Valve, PumpToValveAssociation]


class PumpValveControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fakesleep.monkey_patch()
        SetTestMode()
        Logs.setup_logger(log_level_override=logging.DEBUG)

    @classmethod
    def tearDownClass(cls):
        fakesleep.monkey_restore()

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        self.session = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()
        self.addCleanup(session_mock.stop)

    def test_open_valves(self):
        with self.session as db:
            db.add_all([
                Valve(name='valve 1', delay=30, output=Output(number=1)),
                Valve(name='valve 2', delay=30, output=Output(number=2)),
                Valve(name='valve 3', delay=30, output=Output(number=3)),
            ])
            db.commit()

        SetUpTestInjections(output_controller=mock.Mock(OutputController))
        controller = ValvePumpController()
        controller.update_from_db()

        self.assertEqual(3, len(controller._valve_drivers))

        self.assertIn(1, controller._valve_drivers)
        valve_driver_1 = controller.get_valve_driver(1)
        self.assertIn(2, controller._valve_drivers)
        valve_driver_2 = controller.get_valve_driver(2)
        self.assertIn(3, controller._valve_drivers)
        valve_driver_3 = controller.get_valve_driver(3)

        for percentage, mode, results in [(100, 'equal', [100, 100]),
                                          (50, 'equal', [50, 50]),
                                          (0, 'equal', [0, 0]),
                                          (100, 'cascade', [100, 100]),
                                          (75, 'cascade', [100, 50]),
                                          (50, 'cascade', [100, 0]),
                                          (0, 'cascade', [0, 0])]:
            controller._set_valves(percentage, [1, 2], mode)
            self.assertEqual(results[0], valve_driver_1._desired_percentage)
            self.assertEqual(results[1], valve_driver_2._desired_percentage)
            self.assertEqual(0, valve_driver_3._desired_percentage)

    def test_transitions(self):
        with self.session as db:
            db.add_all([
                Pump(name='pump 1',
                     output=Output(number=1),
                     valves=[
                         Valve(name='valve 1', delay=30, output=Output(number=11)),
                         Valve(name='valve 2', delay=15, output=Output(number=12)),
                     ]),
                Pump(name='pump 2',
                     output=Output(number=2),
                     valves=[
                         Valve(name='valve 3', delay=15, output=Output(number=13)),
                     ])
            ])
            db.commit()

        SetUpTestInjections(output_controller=mock.Mock(OutputController))
        controller = ValvePumpController()
        controller.update_from_db()

        valve_driver_1 = controller.get_valve_driver(1)
        valve_driver_2 = controller.get_valve_driver(2)
        valve_driver_3 = controller.get_valve_driver(3)
        pump_driver_1 = controller._pump_drivers[1]
        pump_driver_2 = controller._pump_drivers[2]

        # Initial state, everything is off
        self.assertFalse(pump_driver_1.state)
        self.assertEqual(None, valve_driver_1.percentage)
        self.assertEqual(None, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(None, valve_driver_3.percentage)

        # Set the second valve to 50%
        # The pump should only be turned on after 15s
        controller.steer(50, [2])
        self.assertFalse(pump_driver_1.state)
        self.assertEqual(0, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(0, valve_driver_3.percentage)

        # Pump still off after 10s
        time.sleep(10)
        controller.update_system()
        self.assertFalse(pump_driver_1.state)
        self.assertEqual(0, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(0, valve_driver_3.percentage)

        # Pump is on after 10s
        time.sleep(10)
        controller.update_system()
        self.assertTrue(pump_driver_1.state)
        self.assertEqual(0, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(0, valve_driver_3.percentage)

        # Other valves are also opened
        controller.steer(100, [1, 3])
        self.assertTrue(pump_driver_1.state)
        self.assertEqual(100, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(100, valve_driver_3.percentage)

        # After a time, both valves are fully open
        time.sleep(40)
        controller.update_system()
        self.assertTrue(pump_driver_1.state)
        self.assertEqual(100, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertTrue(pump_driver_2.state)
        self.assertEqual(100, valve_driver_3.percentage)

        # Two valves are closed again
        # When valves are closed, the pumps are stopped immediately
        controller.steer(0, [2,3])
        self.assertTrue(pump_driver_1.state)
        self.assertEqual(100, valve_driver_1.percentage)
        self.assertEqual(0, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(0, valve_driver_3.percentage)
