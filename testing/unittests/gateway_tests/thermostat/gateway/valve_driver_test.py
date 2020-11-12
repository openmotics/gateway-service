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
from peewee import SqliteDatabase

from gateway.models import Pump, Output, Valve, PumpToValve
from gateway.thermostat.gateway.valve_driver import ValveDriver
from gateway.output_controller import OutputController
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Pump, Output, Valve, PumpToValve]


class ValveDriverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fakesleep.monkey_patch()
        SetTestMode()

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

    def test_valve_driver(self):
        pump_output_1 = Output.create(number=0)
        valve_output_1 = Output.create(number=2)
        pump_1 = Pump.create(number=1, name='pump 1', output=pump_output_1)
        valve_1 = Valve.create(number=1, name='valve 1', delay=30, output=valve_output_1)

        SetUpTestInjections(output_controller=mock.Mock(OutputController))
        driver_1 = ValveDriver(valve_1)

        self.assertEqual(1, driver_1.number)
        self.assertEqual(0, driver_1.percentage)
        self.assertEqual(0, driver_1._desired_percentage)
        self.assertFalse(driver_1.is_open)
        self.assertFalse(driver_1.in_transition)
        self.assertEqual([], driver_1.pump_drivers)

        PumpToValve.create(pump=pump_1, valve=valve_1)

        self.assertEqual(1, len(driver_1.pump_drivers))

        driver_1.set(50)
        self.assertEqual(50, driver_1._desired_percentage)
        driver_1.close()
        self.assertEqual(0, driver_1._desired_percentage)
        driver_1.open()
        self.assertEqual(100, driver_1._desired_percentage)
        self.assertTrue(driver_1.will_open)
        driver_1.steer_output()
        driver_1._output_controller.set_output_status.assert_called_once()
        self.assertFalse(driver_1.will_open)
        self.assertEqual(100, driver_1.percentage)
        self.assertFalse(driver_1.is_open)
        self.assertTrue(driver_1.in_transition)

        time.sleep(20)
        self.assertFalse(driver_1.is_open)
        self.assertTrue(driver_1.in_transition)

        time.sleep(15)
        self.assertTrue(driver_1.is_open)
        self.assertFalse(driver_1.in_transition)
