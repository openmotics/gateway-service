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
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from gateway.models import Base, Database, Output, Pump
from gateway.output_controller import OutputController
from gateway.valve_pump.pump_driver import PumpDriver
from ioc import SetTestMode, SetUpTestInjections


class PumpDriverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

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

    def test_pump_driver(self):
        with self.session as db:
            db.add(
                Pump(name='pump',
                     output=Output(number=0))
            )
            db.commit()

        SetUpTestInjections(output_controller=mock.Mock(OutputController))

        with self.session as db:
            pump = db.query(Pump).filter_by(id=1).one()
            driver = PumpDriver(pump)
            self.assertEqual(pump.id, driver.id)

        self.assertIsNone(driver.state)
        self.assertFalse(driver.error)

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
