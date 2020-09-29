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

import os
import tempfile
import time
import unittest
import xmlrunner
from threading import Lock
from pytest import mark
from peewee import SqliteDatabase

from gateway.config_controller import ConfigurationController
from gateway.dto import ConfigDTO
from gateway.mappers.config import ConfigMapper
from ioc import SetTestMode, SetUpTestInjections

from gateway.models import Config

MODELS = [Config]


class ConfigControllerTest(unittest.TestCase):
    """ Tests for UserController. """

    _db_filename = None

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls._db_filename = tempfile.mktemp()
        cls.test_db = SqliteDatabase(cls._db_filename)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._db_filename):
            os.remove(cls._db_filename)

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        ConfigControllerTest.RETURN_DATA = {}

    def tearDown(self):
        ConfigControllerTest.RETURN_DATA = {}
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def _get_controller(self):
        """ Get a ConfigController using FILE. """
        return ConfigurationController()

    def test_empty(self):
        """ Test an empty database. """
        config_controller = self._get_controller()

        res = config_controller.get('test')
        self.assertIsNone(res)

        config_controller.set('test', 'test')

        res = config_controller.get('test')
        self.assertEqual(res, 'test')

        config_controller.remove('test')

        res = config_controller.get('test')
        self.assertIsNone(res)

    def test_duplicates(self):
        """test of duplicate settings"""
        config_controller = self._get_controller()

        config_controller.set('test', 'test')

        res = config_controller.get('test')
        self.assertEqual(res, 'test')

        config_controller.set('test', 'test2')

        res = config_controller.get('test')
        self.assertEqual(res, 'test2')

        config_controller.remove('test')

        res = config_controller.get('test')
        self.assertIsNone(res)

    def test_multiple_types(self):
        """ Test different types """
        config_controller = self._get_controller()

        config_controller.set('str', 'test')
        config_controller.set('int', 37)
        config_controller.set('bool', True)

        res = config_controller.get('str')
        self.assertEqual(res, 'test')

        res = config_controller.get('int')
        self.assertEqual(res, 37)

        res = config_controller.get('bool')
        self.assertEqual(res, True)

    def test_delete_non_existing(self):
        """ Test different types """
        config_controller = self._get_controller()

        config_controller.set('str', 'test')
        config_controller.set('int', 37)
        config_controller.set('bool', True)

        config_controller.remove('str')
        res = config_controller.get('str')
        self.assertIsNone(res)

        config_controller.remove('str')
        res = config_controller.get('str')
        self.assertIsNone(res)

        res = config_controller.get('int')
        self.assertEqual(res, 37)

        res = config_controller.get('bool')
        self.assertEqual(res, True)


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
