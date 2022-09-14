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
from gateway.valve_pump.valve_driver import ValveDriver
from ioc import SetTestMode, SetUpTestInjections


class ValveDriverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fakesleep.monkey_patch()
        SetTestMode()

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

        SetUpTestInjections(output_controller=mock.Mock(OutputController))


    def test_valve_driver(self):
        with self.session as db:
            db.add(
                Valve(name='valve 1', delay=30,
                      output=Output(number=2))
            )
            db.commit()

            valve = db.query(Valve).filter_by(id=1).one()
            driver = ValveDriver(valve)
            self.assertEqual(valve.id, driver.id)

        self.assertEqual(0, driver.percentage)
        self.assertEqual(0, driver._desired_percentage)
        self.assertEqual(0, driver._current_percentage)
        self.assertFalse(driver.is_open())
        self.assertFalse(driver.in_transition)

        driver.set(50)
        self.assertEqual(50, driver._desired_percentage)
        driver.close()
        self.assertEqual(0, driver._desired_percentage)
        driver.open()
        self.assertEqual(100, driver._desired_percentage)
        self.assertTrue(driver.will_open)
        driver.steer_output()
        driver._output_controller.set_output_status.assert_called_once()
        self.assertFalse(driver.will_open)
        self.assertEqual(100, driver.percentage)
        self.assertFalse(driver.is_open())
        self.assertTrue(driver.in_transition)

        time.sleep(20)
        self.assertFalse(driver.is_open())
        self.assertTrue(driver.in_transition)

        time.sleep(15)
        self.assertTrue(driver.is_open())
        self.assertFalse(driver.in_transition)
