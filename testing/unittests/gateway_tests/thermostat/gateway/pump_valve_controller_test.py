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
import fakesleep
import mock
import time
import logging
from peewee import SqliteDatabase

from gateway.models import Pump, Output, Valve, PumpToValve
from gateway.thermostat.gateway.pump_valve_controller import PumpValveController
from gateway.output_controller import OutputController
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Pump, Output, Valve, PumpToValve]


class PumpValveControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fakesleep.monkey_patch()
        SetTestMode()
        logger = logging.getLogger('openmotics')
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    @classmethod
    def tearDownClass(cls):
        fakesleep.monkey_restore()

    def setUp(self):
        self.test_db = SqliteDatabase(':memory:')
        self.test_db.bind(MODELS)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_open_valves(self):
        Valve.create(number=1, name='valve 1', delay=30, output=Output.create(number=1))
        Valve.create(number=2, name='valve 2', delay=30, output=Output.create(number=2))
        Valve.create(number=3, name='valve 3', delay=30, output=Output.create(number=3))

        SetUpTestInjections(output_controller=mock.Mock(OutputController))
        controller = PumpValveController()
        controller.refresh_from_db()

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
            controller.set_valves(percentage, [1, 2], mode)
            self.assertEqual(results[0], valve_driver_1._desired_percentage)
            self.assertEqual(results[1], valve_driver_2._desired_percentage)
            self.assertEqual(0, valve_driver_3._desired_percentage)

    def test_transitions(self):
        pump_1 = Pump.create(number=1, name='pump 1', output=Output.create(number=1))
        pump_2 = Pump.create(number=2, name='pump 2', output=Output.create(number=2))
        valve_1 = Valve.create(number=1, name='valve 1', delay=30, output=Output.create(number=11))
        valve_2 = Valve.create(number=2, name='valve 2', delay=15, output=Output.create(number=12))
        valve_3 = Valve.create(number=3, name='valve 3', delay=15, output=Output.create(number=13))
        PumpToValve.create(pump=pump_1, valve=valve_1)
        PumpToValve.create(pump=pump_1, valve=valve_2)
        PumpToValve.create(pump=pump_2, valve=valve_3)

        SetUpTestInjections(output_controller=mock.Mock(OutputController))
        controller = PumpValveController()
        controller.refresh_from_db()

        valve_driver_1 = controller.get_valve_driver(1)
        valve_driver_2 = controller.get_valve_driver(2)
        valve_driver_3 = controller.get_valve_driver(3)
        pump_driver_1 = controller._pump_drivers[1]
        pump_driver_2 = controller._pump_drivers[2]

        # Initial state, everything is off
        self.assertFalse(pump_driver_1.state)
        self.assertEqual(0, valve_driver_1.percentage)
        self.assertEqual(0, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(0, valve_driver_3.percentage)

        # Set the second valve to 50%
        # The pump should only be turned on after 15s
        valve_driver_2.set(50)
        controller.steer()
        self.assertFalse(pump_driver_1.state)
        self.assertEqual(0, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(0, valve_driver_3.percentage)

        # Pump still off after 10s
        time.sleep(10)
        controller.steer()
        self.assertFalse(pump_driver_1.state)
        self.assertEqual(0, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(0, valve_driver_3.percentage)

        # Pump is on after 10s
        time.sleep(10)
        controller.steer()
        self.assertTrue(pump_driver_1.state)
        self.assertEqual(0, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(0, valve_driver_3.percentage)

        # Other valves are also opened
        valve_driver_1.set(100)
        valve_driver_3.set(100)
        controller.steer()
        self.assertTrue(pump_driver_1.state)
        self.assertEqual(100, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(100, valve_driver_3.percentage)

        # After a time, both valves are fully open
        time.sleep(40)
        controller.steer()
        self.assertTrue(pump_driver_1.state)
        self.assertEqual(100, valve_driver_1.percentage)
        self.assertEqual(50, valve_driver_2.percentage)
        self.assertTrue(pump_driver_2.state)
        self.assertEqual(100, valve_driver_3.percentage)

        # Two valves are closed again
        # When valves are closed, the pumps are stopped immediately
        valve_driver_2.set(0)
        valve_driver_3.set(0)
        time.sleep(10)
        controller.steer()
        self.assertTrue(pump_driver_1.state)
        self.assertEqual(100, valve_driver_1.percentage)
        self.assertEqual(0, valve_driver_2.percentage)
        self.assertFalse(pump_driver_2.state)
        self.assertEqual(0, valve_driver_3.percentage)
