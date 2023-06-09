# Copyright (C) 2017 OpenMotics BV
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
Tests for the scheduling module.
"""
from __future__ import absolute_import

import logging
import time
import unittest
import mock
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine, select
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from gateway.dto import ScheduleDTO
from gateway.group_action_controller import GroupActionController
from gateway.hal.master_controller import MasterController
from gateway.models import Base, Database, DaySchedule, Schedule
from gateway.pubsub import PubSub
from gateway.scheduling_controller import SchedulingController
from gateway.thermostat.gateway.setpoint_controller import SetpointController
from gateway.system_controller import SystemController
from gateway.webservice import WebInterface
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs

MODELS = [DaySchedule, Schedule]


class SchedulingControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(SchedulingControllerTest, cls).setUpClass()
        SetTestMode()
        Logs.set_loglevel(logging.DEBUG, namespace='gateway.scheduling_controller')
        # Logs.set_loglevel(logging.DEBUG, namespace='sqlalchemy.engine')

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=True, bind=engine)

        self.db = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.db)
        session_mock.start()
        self.addCleanup(session_mock.stop)

        self.group_action_controller = mock.Mock(GroupActionController)
        self.master_controller = mock.Mock(MasterController)

        SetUpTestInjections(master_controller=self.master_controller,
                            message_client=None,
                            module_controller=None,
                            pubsub=mock.Mock(PubSub))
        SetUpTestInjections(system_controller=SystemController())
        SetUpTestInjections(configuration_controller=None,
                            energy_module_controller=None,
                            frontpanel_controller=None,
                            group_action_controller=self.group_action_controller,
                            input_controller=None,
                            maintenance_controller=None,
                            output_controller=None,
                            pulse_counter_controller=None,
                            room_controller=None,
                            sensor_controller=None,
                            shutter_controller=None,
                            thermostat_controller=None,
                            uart_controller=None,
                            update_controller=None,
                            event_sender=None,
                            user_controller=None,
                            ventilation_controller=None,
                            hvac_controller=None)

        self.scheduling_controller = SchedulingController()
        SetUpTestInjections(scheduling_controller=self.scheduling_controller)
        self.setpoint_controller = SetpointController()

        self.web_interface = WebInterface()
        self.scheduling_controller.set_webinterface(self.web_interface)
        self.scheduler = mock.Mock(BackgroundScheduler)
        self.scheduler.get_job.return_value = None
        self.scheduling_controller._scheduler = self.scheduler
        # patch: do not wait to async sync_configuration using a new thread, but directly sync inline for testing
        mock_refresh = mock.patch.object(self.scheduling_controller, 'refresh_schedules',
                                         side_effect=self.scheduling_controller._sync_configuration)
        mock_refresh.start()
        self.scheduling_controller._scheduler.start()

    def tearDown(self):
        self.scheduling_controller.stop()

    def test_save_load(self):
        dto = ScheduleDTO(id=None, name='schedule', start=0, action='GROUP_ACTION', arguments=0)
        self.scheduling_controller.save_schedules([dto])
        loaded_dto = self.scheduling_controller.load_schedule(schedule_id=1)
        for field in ['name', 'start', 'action', 'repeat', 'duration', 'end', 'arguments']:
            self.assertEqual(getattr(dto, field), getattr(loaded_dto, field))
        self.assertEqual('ACTIVE', loaded_dto.status)
        self.scheduling_controller._schedules = {}  # Clear internal cache
        self.scheduling_controller._sync_configuration()
        loaded_dto = self.scheduling_controller.load_schedule(schedule_id=1)
        for field in ['name', 'start', 'action', 'repeat', 'duration', 'end', 'arguments']:
            self.assertEqual(getattr(dto, field), getattr(loaded_dto, field))
        self.assertEqual('ACTIVE', loaded_dto.status)

    def test_pause_resume(self):
        schedule_dto = ScheduleDTO(id=1, name='schedule', start=0, action='GROUP_ACTION', arguments=0)
        self.scheduling_controller.save_schedules([schedule_dto])

        with mock.patch.object(self.scheduling_controller, '_abort') as abort:
            self.scheduling_controller.set_schedule_status(schedule_dto.id, 'PAUSED')
            self.assertNotIn(schedule_dto.id, self.scheduling_controller._schedules)  # disable schedule
            abort.assert_called()

        with mock.patch.object(self.scheduling_controller, '_submit_schedule') as submit:
            self.scheduling_controller.set_schedule_status(schedule_dto.id, 'ACTIVE')
            self.assertIn(schedule_dto.id, self.scheduling_controller._schedules)  # enable schedule
            submit.assert_called()

    def test_base_validation(self):
        with self.assertRaises(RuntimeError):
            # Must have a name
            schedule = Schedule(name=None)
            self.scheduling_controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Unaccepted action
            schedule = Schedule(name='test', start=time.time(), action='FOO')
            self.scheduling_controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Duration too short
            schedule = Schedule(name='test', start=time.time(), action='GROUP_ACTION', duration=10)
            self.scheduling_controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # End when not repeating
            schedule = Schedule(name='test', start=time.time(), action='GROUP_ACTION', end=time.time() + 1)
            self.scheduling_controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Invalid repeat string
            schedule = Schedule(name='test', start=time.time(), action='GROUP_ACTION', repeat='foo')
            self.scheduling_controller._validate(schedule)

    def test_validate_group_action(self):
        # New self.scheduling_controller is empty
        self.assertEqual(0, len(self.scheduling_controller.load_schedules()))

        # Doesn't support duration
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='GROUP_ACTION', duration=1000)
        self.assertEqual('A schedule of type GROUP_ACTION does not have a duration. It is a one-time trigger',
                         str(ctx.exception))

        # Incorrect argument
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='GROUP_ACTION', arguments='foo')
        self.assertEqual(
            'The arguments of a GROUP_ACTION schedule must be an integer, representing the Group Action to be executed',
            str(ctx.exception))

    def test_group_action(self):
        self.group_action_controller.do_group_action.return_value = {}
        self.group_action_controller.do_basic_action.return_value = {}

        schedule_dto = ScheduleDTO(id=None,
                                   name='schedule',
                                   start=time.time() + 0.5,
                                   action='GROUP_ACTION',
                                   arguments=1)
        self.scheduling_controller._execute_schedule(schedule_dto)
        assert schedule_dto.last_executed is not None
        assert schedule_dto.status == 'COMPLETED'
        self.group_action_controller.do_group_action.assert_called_with(1)

    def test_validate_basic_action(self):
        # New self.scheduling_controller is empty
        assert len(self.scheduling_controller.load_schedules()) == 0

        # Doesn't support duration
        duration_error = 'A schedule of type BASIC_ACTION does not have a duration. It is a one-time trigger'
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='BASIC_ACTION', duration=1000)
        assert str(ctx.exception) == duration_error

        # Incorrect argument
        invalid_arguments_error = 'The arguments of a BASIC_ACTION schedule must be of type dict with arguments ' \
                                  '`action_type` and `action_number`'
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='BASIC_ACTION', arguments='foo')
        self.assertEqual(invalid_arguments_error, str(ctx.exception))
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='BASIC_ACTION',
                               arguments={'action_type': 1})
        assert str(ctx.exception) == invalid_arguments_error
        self.scheduler.add_job.assert_not_called()

    def test_basic_action(self):
        schedule_dto = ScheduleDTO(id=None,
                                   name='schedule',
                                   start=time.time() + 0.5,
                                   action='BASIC_ACTION',
                                   arguments={'action_type': 1, 'action_number': 2})
        self.scheduling_controller._execute_schedule(schedule_dto)
        assert schedule_dto.last_executed is not None
        assert schedule_dto.status == 'COMPLETED'
        self.group_action_controller.do_basic_action.assert_called_with(action_number=2, action_type=1)

    def test_validate_local_api(self):
        # New self.scheduling_controller is empty
        self.assertEqual(0, len(self.scheduling_controller.load_schedules()))

        # Doesn't support duration
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='LOCAL_API', duration=1000)
        self.assertEqual('A schedule of type LOCAL_API does not have a duration. It is a one-time trigger',
                         str(ctx.exception))

        # Incorrect argument
        invalid_arguments_error = 'The arguments of a LOCAL_API schedule must be of type dict with arguments `name` ' \
                                  'and `parameters`'
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='LOCAL_API', arguments='foo')
        self.assertEqual(invalid_arguments_error, str(ctx.exception))
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='LOCAL_API', arguments={'name': 1})
        self.assertEqual(invalid_arguments_error, str(ctx.exception))

        # Not a valid call
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='LOCAL_API',
                               arguments={'name': 'foo', 'parameters': {}})
        self.assertEqual('The arguments of a LOCAL_API schedule must specify a valid and (plugin_)exposed call',
                         str(ctx.exception))
        with self.assertRaises(Exception) as ctx:
            self._add_schedule(name='schedule', start=0, action='LOCAL_API',
                               arguments={'name': 'do_basic_action',
                                          'parameters': {'action_type': 'foo',
                                                         'action_number': 4}})
        self.assertIn('could not convert string to float', str(ctx.exception))

    def test_local_api(self):
        schedule_dto = ScheduleDTO(id=None,
                                   name='schedule', start=time.time() + 0.5, action='LOCAL_API',
                                   arguments={'name': 'do_basic_action',
                                              'parameters': {'action_type': 3,
                                                             'action_number': 4}})
        self.scheduling_controller._execute_schedule(schedule_dto)
        assert schedule_dto.last_executed is not None
        assert schedule_dto.status == 'COMPLETED'
        self.group_action_controller.do_basic_action.assert_called_with(3, 4)

    def test_two_actions(self):
        self._add_schedule(name='basic_action', start=0, action='BASIC_ACTION',
                           arguments={'action_type': 1, 'action_number': 2})
        self._add_schedule(name='group_action', start=0, action='GROUP_ACTION',
                           arguments=1)
        schedules = self.scheduling_controller.load_schedules()
        self.assertEqual(2, len(schedules))
        self.assertEqual(['basic_action', 'group_action'], sorted(s.name for s in schedules))
        for s in schedules:
            if s.name == 'group_action':
                self.scheduling_controller.remove_schedules([s])
        schedules = self.scheduling_controller.load_schedules()
        self.assertEqual(1, len(schedules))
        self.assertEqual('basic_action', schedules[0].name)

    def test_skip_grace_time(self):
        self._add_schedule(name='schedule',
                           start=time.time() - 86400,  # yesterday
                           action='GROUP_ACTION',
                           arguments=1,
                           status='ACTIVE')
        schedule = self.scheduling_controller.load_schedules()[0]
        self.assertEqual(schedule.status, 'ACTIVE')
        self.assertIsNone(schedule.last_executed)

    def test_expire_repeat_end(self):
        self._add_schedule(name='schedule',
                           start=time.time() - 86400,  # yesterday
                           end=time.time() - 14400,  # 4h
                           repeat='* * * * *',
                           action='GROUP_ACTION',
                           arguments=1,
                           status='ACTIVE')
        schedule = self.scheduling_controller.load_schedules()[0]
        self.assertEqual(schedule.status, 'COMPLETED')
        self.assertIsNone(schedule.last_executed)

    def _add_schedule(self, **kwargs):
        dto = ScheduleDTO(id=None, **kwargs)
        self.scheduling_controller.save_schedules([dto])
