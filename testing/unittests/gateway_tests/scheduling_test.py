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
from datetime import datetime, timedelta

from mock import Mock
from peewee import SqliteDatabase

from gateway.dto import ScheduleDTO
from gateway.group_action_controller import GroupActionController
from gateway.models import Schedule
from gateway.scheduling_controller import SchedulingController
from gateway.ventilation_controller import VentilationController
from gateway.webservice import WebInterface
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Schedule]


class SchedulingControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

        system_controller = Mock()
        system_controller.get_timezone.return_value = 'UTC'

        self.group_action_controller = Mock(GroupActionController)
        self.group_action_controller.do_group_action.return_value = {}
        self.group_action_controller.do_basic_action.return_value = {}

        SetUpTestInjections(system_controller=system_controller,
                            user_controller=None,
                            maintenance_controller=None,
                            message_client=None,
                            configuration_controller=None,
                            thermostat_controller=None,
                            ventilation_controller=Mock(VentilationController),
                            shutter_controller=Mock(),
                            output_controller=Mock(),
                            room_controller=Mock(),
                            input_controller=Mock(),
                            sensor_controller=Mock(),
                            pulse_counter_controller=Mock(),
                            frontpanel_controller=Mock(),
                            group_action_controller=self.group_action_controller,
                            module_controller=Mock(),
                            energy_module_controller=Mock(),
                            uart_controller=Mock(),
                            master_controller=Mock())
        self.controller = SchedulingController()
        SetUpTestInjections(scheduling_controller=self.controller)
        self.controller.set_webinterface(WebInterface())
        self.controller.start()

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()
        self.controller.stop()

    def test_save_load(self):
        dto = ScheduleDTO(id=None, name='schedule', start=0, action='GROUP_ACTION', arguments=0)
        self.controller.save_schedules([dto])
        loaded_dto = self.controller.load_schedule(schedule_id=1)
        for field in ['name', 'start', 'action', 'repeat', 'duration', 'end', 'arguments']:
            self.assertEqual(getattr(dto, field), getattr(loaded_dto, field))
        self.assertEqual('ACTIVE', loaded_dto.status)
        self.controller._schedules = {}  # Clear cache
        self.controller.reload_schedules()
        loaded_dto = self.controller.load_schedule(schedule_id=1)
        for field in ['name', 'start', 'action', 'repeat', 'duration', 'end', 'arguments']:
            self.assertEqual(getattr(dto, field), getattr(loaded_dto, field))
        self.assertEqual('ACTIVE', loaded_dto.status)

    def test_base_validation(self):
        with self.assertRaises(RuntimeError):
            # Must have a name
            schedule = Schedule(name=None)
            self.controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Unaccepted action
            schedule = Schedule(name='test', start=time.time(), action='FOO')
            self.controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Duration too short
            schedule = Schedule(name='test', start=time.time(), action='GROUP_ACTION', duration=10)
            self.controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # End when not repeating
            schedule = Schedule(name='test', start=time.time(), action='GROUP_ACTION', end=time.time() + 1)
            self.controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Invalid repeat string
            schedule = Schedule(name='test', start=time.time(), action='GROUP_ACTION', repeat='foo')
            self.controller._validate(schedule)

    def test_group_action(self):
        # New self.controller is empty
        self.assertEqual(0, len(self.controller.load_schedules()))

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

        # Normal
        self._add_schedule(name='schedule', start=time.time() + 0.5, action='GROUP_ACTION', arguments=1)
        schedules = self.controller.load_schedules()
        self.assertEqual(1, len(schedules))
        schedule = schedules[0]
        self.assertEqual('schedule', schedule.name)
        self.assertEqual('ACTIVE', schedule.status)

        while schedule.last_executed is None:
            time.sleep(0.1)  # Wait until the schedule has been executed
        schedule = self.controller.load_schedules()[0]
        self.assertIsNotNone(schedule.last_executed)
        self.assertEqual(schedule.status, 'COMPLETED')
        self.group_action_controller.do_group_action.assert_called_with(1)

    def test_basic_action(self):
        # New self.controller is empty
        self.assertEqual(0, len(self.controller.load_schedules()))

        # Doesn't support duration
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='BASIC_ACTION', duration=1000)
        self.assertEqual('A schedule of type BASIC_ACTION does not have a duration. It is a one-time trigger',
                         str(ctx.exception))

        # Incorrect argument
        invalid_arguments_error = 'The arguments of a BASIC_ACTION schedule must be of type dict with arguments ' \
                                  '`action_type` and `action_number`'
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='BASIC_ACTION', arguments='foo')
        self.assertEqual(invalid_arguments_error, str(ctx.exception))
        with self.assertRaises(RuntimeError) as ctx:
            self._add_schedule(name='schedule', start=0, action='BASIC_ACTION',
                               arguments={'action_type': 1})
        self.assertEqual(invalid_arguments_error, str(ctx.exception))

        # Normal
        dto = ScheduleDTO(id=None, name='schedule', start=time.time() + 0.5, action='BASIC_ACTION',
                          arguments={'action_type': 1, 'action_number': 2})
        self.controller.save_schedules([dto])
        schedules = self.controller.load_schedules()
        self.assertEqual(1, len(schedules))
        schedule = schedules[0]
        self.assertEqual('schedule', schedule.name)
        self.assertEqual('ACTIVE', schedule.status)
        for _ in range(60):
            if schedule.last_executed:
                break
            time.sleep(0.1)  # Wait until the schedule has been executed
        schedule = self.controller.load_schedules()[0]
        self.assertIsNotNone(schedule.last_executed)
        self.assertEqual(schedule.status, 'COMPLETED')
        self.group_action_controller.do_basic_action.assert_called_with(action_number=2, action_type=1)

    def test_local_api(self):
        # New self.controller is empty
        self.assertEqual(0, len(self.controller.load_schedules()))

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

        # Normal
        self._add_schedule(name='schedule', start=time.time() + 0.5, action='LOCAL_API',
                           arguments={'name': 'do_basic_action',
                                      'parameters': {'action_type': 3,
                                                     'action_number': 4}})
        schedules = self.controller.load_schedules()
        self.assertEqual(1, len(schedules))
        schedule = schedules[0]
        self.assertEqual('schedule', schedule.name)
        self.assertEqual('ACTIVE', schedule.status)
        while schedule.last_executed is None:
            time.sleep(0.1)  # Wait until the schedule has been executed
        schedule = self.controller.load_schedules()[0]
        self.assertIsNotNone(schedule.last_executed)
        self.assertEqual(schedule.status, 'COMPLETED')
        self.group_action_controller.do_basic_action.assert_called_with(3, 4)

    def test_two_actions(self):
        self._add_schedule(name='basic_action', start=0, action='BASIC_ACTION',
                           arguments={'action_type': 1, 'action_number': 2})
        self._add_schedule(name='group_action', start=0, action='GROUP_ACTION',
                           arguments=1)
        schedules = self.controller.load_schedules()
        self.assertEqual(2, len(schedules))
        self.assertEqual(['basic_action', 'group_action'], sorted(s.name for s in schedules))
        for s in schedules:
            if s.name == 'group_action':
                self.controller.remove_schedules([s])
        schedules = self.controller.load_schedules()
        self.assertEqual(1, len(schedules))
        self.assertEqual('basic_action', schedules[0].name)

    def test_execute_grace_time(self):
        self._add_schedule(name='schedule',
                           start=time.time() - 3000,  # 50m
                           action='GROUP_ACTION',
                           arguments=1,
                           status='ACTIVE')
        self.controller.refresh_schedules()
        time.sleep(0.5)
        schedule = self.controller.load_schedules()[0]
        self.assertEqual(schedule.status, 'COMPLETED')
        self.assertTrue(time.time() - 10 < schedule.last_executed < time.time() + 10)

    def test_skip_grace_time(self):
        self._add_schedule(name='schedule',
                           start=time.time() - 86400,  # yesterday
                           action='GROUP_ACTION',
                           arguments=1,
                           status='ACTIVE')
        self.controller.refresh_schedules()
        time.sleep(0.5)
        schedule = self.controller.load_schedules()[0]
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
        self.controller.refresh_schedules()
        time.sleep(0.5)
        schedule = self.controller.load_schedules()[0]
        self.assertEqual(schedule.status, 'COMPLETED')
        self.assertIsNone(schedule.last_executed)

    def _add_schedule(self, **kwargs):
        dto = ScheduleDTO(id=None, **kwargs)
        self.controller.save_schedules([dto])
