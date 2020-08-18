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
from bus.om_bus_client import MessageClient
from gateway.hal.master_controller import MasterController
from gateway.maintenance_controller import MaintenanceController
from gateway.models import Input
from gateway.dto import InputDTO
from gateway.input_controller import InputController
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Input]


class InputControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.master_controller = mock.Mock(MasterController)
        SetUpTestInjections(maintenance_controller=mock.Mock(MaintenanceController),
                            master_controller=self.master_controller,
                            message_client=mock.Mock(MessageClient))
        self.controller = InputController()

    def test_full_loaded_inputs(self):
        Input.get_or_create(number=1, event_enabled=False)
        Input.get_or_create(number=2, event_enabled=True)
        master_dtos = {1: InputDTO(id=1, name='one'),
                       2: InputDTO(id=2, name='two')}

        with mock.patch.object(self.master_controller, 'load_input',
                               side_effect=lambda input_id: master_dtos.get(input_id)):
            dtos = self.controller.load_inputs()
            self.assertEqual(2, len(dtos))
            self.assertIn(InputDTO(id=1, name='one', event_enabled=False), dtos)
            self.assertIn(InputDTO(id=2, name='two', event_enabled=True), dtos)
