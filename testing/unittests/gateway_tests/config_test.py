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
"""
Tests for the config module.
"""

from __future__ import absolute_import

import mock
import unittest
import xmlrunner
import logging
from sqlalchemy import create_engine, select
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool
from logs import Logs
from ioc import SetTestMode
from gateway.models import Config, Database, Base

MODELS = [Config]


class ConfigControllerTest(unittest.TestCase):
    """ Tests for ConfigurationController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        Logs.set_loglevel(logging.DEBUG, namespace='gateway.config_controller')
        # Logs.set_loglevel(logging.DEBUG, namespace='sqlalchemy.engine')

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

    def test_empty(self):
        """ Test an empty database. """
        res = Config.get_entry('test', None)
        self.assertIsNone(res)

        Config.set_entry('test', 'test')

        res = Config.get_entry('test', None)
        self.assertEqual(res, 'test')

        Config.remove_entry('test')

        res = Config.get_entry('test', None)
        self.assertIsNone(res)

    def test_duplicates(self):
        """test of duplicate settings"""
        Config.set_entry('test', 'test')

        res = Config.get_entry('test', None)
        self.assertEqual(res, 'test')

        Config.set_entry('test', 'test2')

        res = Config.get_entry('test', None)
        self.assertEqual(res, 'test2')

        Config.remove_entry('test')

        res = Config.get_entry('test', None)
        self.assertIsNone(res)

    def test_multiple_types(self):
        """ Test different types """
        Config.set_entry('str', 'test')
        Config.set_entry('int', 37)
        Config.set_entry('bool', True)

        res = Config.get_entry('str', None)
        self.assertEqual(res, 'test')

        res = Config.get_entry('int', None)
        self.assertEqual(res, 37)

        res = Config.get_entry('bool', None)
        self.assertEqual(res, True)

    def test_delete_non_existing(self):
        """ Test deleting non existing setting """
        Config.set_entry('str', 'test')
        Config.set_entry('int', 37)
        Config.set_entry('bool', True)

        Config.remove_entry('str')
        res = Config.get_entry('str', None)
        self.assertIsNone(res)

        Config.remove_entry('str')
        res = Config.get_entry('str', None)
        self.assertIsNone(res)

        res = Config.get_entry('int', None)
        self.assertEqual(res, 37)

        res = Config.get_entry('bool', None)
        self.assertEqual(res, True)


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
