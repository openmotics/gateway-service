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

from gateway.dto import InputDTO
from gateway.events import GatewayEvent
from gateway.hal.master_controller import MasterController
from gateway.input_controller import InputController
from gateway.models import Input
from gateway.pubsub import PubSub
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
        self.pubsub = PubSub()  # triggernig manually
        self.master_controller = mock.Mock(MasterController)
        SetUpTestInjections(master_controller=self.master_controller,
                            maintenance_controller=mock.Mock(),
                            pubsub=self.pubsub)
        self.controller = InputController()

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_orm_sync(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        input_dto = InputDTO(id=42)
        with mock.patch.object(self.master_controller, 'load_inputs', return_value=[input_dto]):
            self.controller.run_sync_orm()
            self.pubsub._publish_all_events()
            assert Input.select().where(Input.number == input_dto.id).count() == 1
            assert GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'input'}) in events
            assert len(events) == 1

    def test_full_loaded_inputs(self):
        master_dtos = {1: InputDTO(id=1, name='one'),
                       2: InputDTO(id=2, name='two')}
        orm_inputs = [Input(id=0, number=1, event_enabled=False),
                      Input(id=1, number=2, event_enabled=True)]
        select_mock = mock.Mock()
        select_mock.join_from.return_value = orm_inputs
        with mock.patch.object(Input, 'select', return_value=select_mock), \
             mock.patch.object(self.master_controller, 'load_input',
                               side_effect=lambda input_id: master_dtos.get(input_id)):
            dtos = self.controller.load_inputs()
            self.assertEqual(2, len(dtos))
            self.assertIn(InputDTO(id=1, name='one', event_enabled=False), dtos)
            self.assertIn(InputDTO(id=2, name='two', event_enabled=True), dtos)
