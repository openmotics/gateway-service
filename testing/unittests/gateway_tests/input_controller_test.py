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
import logging
import fakesleep
import mock
from gateway.dto import InputDTO
from gateway.dto.input import InputStatusDTO
from gateway.events import GatewayEvent
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from sqlalchemy import create_engine, select
from sqlalchemy.orm import scoped_session, sessionmaker
from gateway.models import Database, Base, Input, Room
from gateway.input_controller import InputController
from gateway.pubsub import PubSub
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs


class InputControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(InputControllerTest, cls).setUpClass()
        SetTestMode()
        Logs.set_loglevel(logging.DEBUG, namespace='gateway.input_controller')
        # Logs.set_loglevel(logging.DEBUG, namespace='sqlalchemy.engine')
        fakesleep.monkey_patch()

    @classmethod
    def tearDownClass(cls):
        super(InputControllerTest, cls).tearDownClass()
        fakesleep.monkey_restore()

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=True, bind=engine)

        self.session = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()
        self.addCleanup(session_mock.stop)

        self.master_controller = mock.Mock(MasterController)
        self.pubsub = PubSub()  # triggernig manually
        self.master_controller = mock.Mock(MasterController)
        SetUpTestInjections(master_controller=self.master_controller,
                            maintenance_controller=mock.Mock(),
                            pubsub=self.pubsub)
        self.controller = InputController()

    def test_orm_sync(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        input_dto = InputDTO(id=42)
        with mock.patch.object(self.master_controller, 'load_inputs', return_value=[input_dto]):
            self.controller.run_sync_orm()
            self.pubsub._publish_all_events(blocking=False)

        with self.session as db:
            assert db.query(Input).where(Input.number == input_dto.id).count() == 1
            assert GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'input'}) in events
            assert len(events) == 1

    def test_full_loaded_inputs(self):
        with self.session as db:
            db.add_all([
                Input(id=10, number=1, event_enabled=False),
                Input(id=11, number=2, event_enabled=True)
            ])
            db.commit()

        master_dtos = {1: InputDTO(id=1, name='one'),
                       2: InputDTO(id=2, name='two')}
        with mock.patch.object(self.master_controller, 'load_input',
                               side_effect=lambda input_id: master_dtos.get(input_id)):
            dtos = self.controller.load_inputs()
            self.assertEqual(2, len(dtos))
            self.assertIn(InputDTO(id=1, name='one', event_enabled=False), dtos)
            self.assertIn(InputDTO(id=2, name='two', event_enabled=True), dtos)

    def test_get_last_inputs(self):
        with self.session as db:
            db.add_all([
                Input(id=10, number=1, event_enabled=False),
                Input(id=11, number=2, event_enabled=True)
            ])
            db.commit()

        master_dtos = {1: InputDTO(id=1, name='one'),
                       2: InputDTO(id=2, name='two')}
        with mock.patch.object(self.master_controller, 'load_input',
                               side_effect=lambda input_id: master_dtos.get(input_id)):
            fakesleep.reset(0)
            self.controller.load_inputs()
            # test 1: all inputs should have a new status upon init
            last_inputs = self.controller.get_last_inputs()
            self.assertEqual([1, 2], last_inputs)

            # test 2: after 10 seconds, all statuses are stable, and not in last inputs
            fakesleep.sleep(15)
            last_inputs = self.controller.get_last_inputs()
            self.assertEqual([], last_inputs)

            # test 3: a new pressed event comes from the master, this should trigger and appear in the recent list
            master_event = MasterEvent(event_type=MasterEvent.Types.INPUT_CHANGE,
                                       data={'state': InputStatusDTO(id=2, status=True)})
            self.controller._handle_master_event(master_event)
            last_inputs = self.controller.get_last_inputs()
            self.assertEqual([2], last_inputs)

            # test 4: after 10 seconds, all statuses are stable, and not in last inputs
            fakesleep.sleep(15)
            last_inputs = self.controller.get_last_inputs()
            self.assertEqual([], last_inputs)

            # test 3: a new released event comes from the master, this should also trigger and appear in the recent list
            master_event = MasterEvent(event_type=MasterEvent.Types.INPUT_CHANGE,
                                       data={'state': InputStatusDTO(id=2, status=False)})
            self.controller._handle_master_event(master_event)
            last_inputs = self.controller.get_last_inputs()
            self.assertEqual([2], last_inputs)

    def test_input_sync_change(self):
        with self.session as db:
            db.add_all([
                Input(id=0, number=2),
                Input(id=1, number=40, room=Room(id=2, number=3))
            ])
            db.commit()

        events = []

        def on_change(gateway_event):
            events.append(gateway_event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, on_change)

        inputs = {2: InputDTO(id=2),
                  40: InputDTO(id=40, module_type='I')}
        with mock.patch.object(self.master_controller, 'load_input',
                               side_effect=lambda input_id: inputs.get(input_id)), \
             mock.patch.object(self.master_controller, 'load_input_status',
                               return_value=[InputStatusDTO(id=2, status=True),
                                             InputStatusDTO(id=40, status=True)]):
            self.controller.load_inputs()
            self.controller._sync_state()
            self.pubsub._publish_all_events(blocking=False)
            self.assertListEqual([GatewayEvent('INPUT_CHANGE',
                                  {'id': 2, 'status': True, "location": {"room_id": 255}}),
                                  GatewayEvent('INPUT_CHANGE',
                                  {'id': 40, 'status': True, "location": {"room_id": 3}})], events)

        with mock.patch.object(self.master_controller, 'load_input',
                               side_effect=lambda input_id: inputs.get(input_id)), \
             mock.patch.object(self.master_controller, 'load_input_status',
                               return_value=[InputStatusDTO(id=2, status=True),
                                             InputStatusDTO(id=40, status=False)]):
            events = []
            self.controller._sync_state()
            self.pubsub._publish_all_events(blocking=False)
            self.assertListEqual([GatewayEvent('INPUT_CHANGE',
                                  {'id': 2, 'status': True, "location": {"room_id": 255}}),
                                  GatewayEvent('INPUT_CHANGE',
                                  {'id': 40, 'status': False, "location": {"room_id": 3}})], events)

    def test_periodic_input_events(self):
        # TODO: enable when on python 3 and configure freezegun to ignore threads
        pass
        # # https://github.com/spulec/freezegun
        # freezegun.configure(default_ignore_list=[])
        # initial_datetime = datetime.datetime(year=1, month=7, day=12,
        #                                      hour=15, minute=6, second=3)
        # events = []
        #
        # def on_change(gateway_event):
        #     events.append(gateway_event)
        # self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, on_change)
        #
        # inputs = {2: InputDTO(id=2),
        #           40: InputDTO(id=40, module_type='I')}
        # select_mock = mock.Mock()
        # select_mock.join_from.return_value = [Input(id=0, number=2),
        #                                       Input(id=1, number=40, room=Room(id=2, number=3))]
        # with mock.patch.object(Input, 'select', return_value=select_mock), \
        #      mock.patch.object(self.master_controller, 'load_input',
        #                        side_effect=lambda input_id: inputs.get(input_id)), \
        #      mock.patch.object(self.master_controller, 'load_input_status',
        #                        return_value=[InputStateDTO(id=2, status=True),
        #                                      InputStateDTO(id=40, status=True)]), \
        #      freeze_time(initial_datetime) as frozen_datetime:
        #
        #     assert frozen_datetime() == initial_datetime
        #     try:
        #         events = []
        #         self.controller.start()
        #         # after >10 seconds delay, the controller should publish events at startup
        #         frozen_datetime.tick(delta=datetime.timedelta(seconds=15))
        #         self.pubsub._publish_all_events(blocking=False)
        #         self.assertListEqual([GatewayEvent('INPUT_CHANGE',
        #                                            {'id': 2, 'status': True, "location": {"room_id": 255}}),
        #                               GatewayEvent('INPUT_CHANGE',
        #                                            {'id': 40, 'status': False, "location": {"room_id": 3}})], events)
        #         # after >10 more minutes, the controller should also periodically publish events regardless of changes
        #         events = []
        #         frozen_datetime.tick(delta=datetime.timedelta(minutes=11))
        #         self.pubsub._publish_all_events(blocking=False)
        #         self.assertListEqual([GatewayEvent('INPUT_CHANGE',
        #                                            {'id': 2, 'status': True, "location": {"room_id": 255}}),
        #                               GatewayEvent('INPUT_CHANGE',
        #                                            {'id': 40, 'status': False, "location": {"room_id": 3}})], events)
        #     finally:
        #         self.controller.stop()
