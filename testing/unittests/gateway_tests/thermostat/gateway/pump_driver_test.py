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
from peewee import SqliteDatabase

from gateway.models import Pump, Output
from gateway.thermostat.gateway.pump_driver import PumpDriver
from gateway.output_controller import OutputController
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Pump, Output]


class PumpDriverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.test_db = SqliteDatabase(':memory:')
        self.test_db.bind(MODELS)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_pump_driver(self):
        output = Output.create(number=0)
        pump = Pump.create(number=1,
                           name='pump',
                           output=output)

        SetUpTestInjections(output_controller=mock.Mock(OutputController))
        driver = PumpDriver(pump)
        self.assertIsNone(driver.state)
        self.assertFalse(driver.error)
        self.assertEqual(1, driver.number)

        driver.turn_on()
        self.assertTrue(driver.state)
        self.assertFalse(driver.error)

        driver.turn_off()
        self.assertFalse(driver.state)
        self.assertFalse(driver.error)

        driver._output_controller.set_output_status.side_effect = RuntimeError()
        with self.assertRaises(RuntimeError):
            driver.turn_on()
        self.assertFalse(driver.state)
        self.assertTrue(driver.error)

        driver._output_controller.set_output_status.side_effect = None
        driver.turn_on()
        self.assertTrue(driver.state)
        self.assertFalse(driver.error)

        driver._output_controller.set_output_status.side_effect = RuntimeError()
        with self.assertRaises(RuntimeError):
            driver.turn_off()
        self.assertTrue(driver.state)
        self.assertTrue(driver.error)

        driver._output_controller.set_output_status.side_effect = None
        driver.turn_off()
        self.assertFalse(driver.state)
        self.assertFalse(driver.error)
