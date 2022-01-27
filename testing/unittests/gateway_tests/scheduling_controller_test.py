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
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta

from mock import Mock
from peewee import SqliteDatabase

from gateway.dto import ScheduleDTO, ScheduleSetpointDTO
from gateway.group_action_controller import GroupActionController
from gateway.hal.master_controller import MasterController
from gateway.maintenance_controller import MaintenanceController
from gateway.models import DaySchedule, Schedule
from gateway.module_controller import ModuleController
from gateway.pubsub import PubSub
from gateway.scheduling_controller import SchedulingController
from gateway.system_controller import SystemController
from gateway.webservice import WebInterface
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs

MODELS = [DaySchedule, Schedule]


class SchedulingControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        Logs.setup_logger(log_level_override=logging.DEBUG)
        cls._db_filename = tempfile.mktemp()
        cls.test_db = SqliteDatabase(cls._db_filename)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._db_filename):
            os.remove(cls._db_filename)

    def setUp(self):
        self.test_db.bind(MODELS)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

        # self.utcnow = datetime.utcnow().timestamp()
        self.utcnow = (datetime.utcnow() - timedelta(hours=1) - datetime(1970, 1, 1)).total_seconds()

        self.group_action_controller = Mock(GroupActionController)
        SetUpTestInjections(message_client=None,
                            module_controller=None,
                            pubsub=Mock(PubSub))
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
                            user_controller=None,
                            ventilation_controller=None,
                            rebus_controller=None)
        self.controller = SchedulingController()
        SetUpTestInjections(scheduling_controller=self.controller)
        self.web_interface = WebInterface()
        self.controller.set_webinterface(self.web_interface)
        self.controller.start()


    def tearDown(self):
        self.controller.stop()
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_save_load(self):
        dto = ScheduleDTO(id=None, source='gateway', name='schedule', start=0, action='GROUP_ACTION', arguments=0)
        self.controller.save_schedules([dto])
        time.sleep(0.2)
        loaded_dto = self.controller.load_schedule(schedule_id=1)
        for field in ['name', 'start', 'action', 'repeat', 'duration', 'end', 'arguments']:
            self.assertEqual(getattr(dto, field), getattr(loaded_dto, field))
        self.assertEqual('ACTIVE', loaded_dto.status)
        self.controller._schedules = {}  # Clear internal cache
        self.controller.refresh_schedules()
        time.sleep(0.2)
        loaded_dto = self.controller.load_schedule(schedule_id=1)
        for field in ['name', 'start', 'action', 'repeat', 'duration', 'end', 'arguments']:
            self.assertEqual(getattr(dto, field), getattr(loaded_dto, field))
        self.assertEqual('ACTIVE', loaded_dto.status)

    def test_update_thermostat_setpoints(self):
        self.controller.update_thermostat_setpoints(0, 'heating', [
            DaySchedule(id=10, index=0, content='{"21600": 21.5}')
        ])
        jobs = self.controller._scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == 'thermostat.heating.0.mon.06h00m'

        self.controller.update_thermostat_setpoints(0, 'heating', [
            DaySchedule(id=10, index=0, content='{"28800": 22.0}')
        ])
        jobs = self.controller._scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == 'thermostat.heating.0.mon.08h00m'

    def test_base_validation(self):
        with self.assertRaises(RuntimeError):
            # Must have a name
            schedule = Schedule(name=None)
            self.controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Unaccepted action
            schedule = Schedule(name='test', start=self.utcnow, action='FOO')
            self.controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Duration too short
            schedule = Schedule(name='test', start=self.utcnow, action='GROUP_ACTION', duration=10)
            self.controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # End when not repeating
            schedule = Schedule(name='test', start=self.utcnow, action='GROUP_ACTION', end=self.utcnow + 1)
            self.controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Invalid repeat string
            schedule = Schedule(name='test', start=self.utcnow, action='GROUP_ACTION', repeat='foo')
            self.controller._validate(schedule)

    def test_group_action(self):
        self.group_action_controller.do_group_action.return_value = {}
        self.group_action_controller.do_basic_action.return_value = {}

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
        self._add_schedule(name='schedule', start=self.utcnow + 0.5, action='GROUP_ACTION', arguments=1)
        time.sleep(0.2)
        schedules = self.controller.load_schedules()
        self.assertEqual(1, len(schedules))
        schedule = schedules[0]
        assert schedule.name == 'schedule'
        assert schedule.status in ('ACTIVE', 'COMPLETED')

        for _ in range(60):
            schedule = self.controller.load_schedules()[0]
            if schedule.last_executed:
                break
            time.sleep(0.1)
        assert schedule is not None, 'No schedule'
        assert schedule.last_executed is not None, ', '.join(str(x) for x in self.controller._scheduler.get_jobs())
        assert schedule.status == 'COMPLETED'
        self.group_action_controller.do_group_action.assert_called_with(1)

    def test_basic_action(self):
        # New self.controller is empty
        assert len(self.controller.load_schedules()) == 0

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

        # Normal
        dto = ScheduleDTO(id=None, source='gateway',
                          name='schedule', start=self.utcnow + 0.5, action='BASIC_ACTION',
                          arguments={'action_type': 1, 'action_number': 2})
        self.controller.save_schedules([dto])
        for _ in range(60):
            schedule = next(iter(self.controller.load_schedules()), None)
            if schedule and schedule.last_executed:
                break
            time.sleep(0.1)
        assert len(self.controller.load_schedules()) == 1
        assert schedule is not None, 'No schedule'
        assert schedule.last_executed is not None, ', '.join(str(x) for x in self.controller._scheduler.get_jobs())
        assert schedule.status == 'COMPLETED'
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
        self._add_schedule(name='schedule', start=self.utcnow + 0.5, action='LOCAL_API',
                           arguments={'name': 'do_basic_action',
                                      'parameters': {'action_type': 3,
                                                     'action_number': 4}})
        schedules = self.controller.load_schedules()
        assert len(schedules) == 1
        schedule = schedules[0]
        assert schedule is not None, 'No schedule'
        assert schedule.name == 'schedule'
        assert schedule.status in ('ACTIVE', 'COMPLETED')
        for _ in range(60):
            if schedule.last_executed:
                break
            time.sleep(0.1)
        assert schedule.last_executed is not None, ', '.join(str(x) for x in self.controller._scheduler.get_jobs())
        assert schedule.status == 'COMPLETED'
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
        time.sleep(0.1)
        schedules = self.controller.load_schedules()
        self.assertEqual(1, len(schedules))
        self.assertEqual('basic_action', schedules[0].name)

    # def test_execute_grace_time(self):
    #     time.sleep(0.2)
    #     self._add_schedule(name='schedule',
    #                        start=self.utcnow - 3000,  # 5m
    #                        action='GROUP_ACTION',
    #                        arguments=1,
    #                        status='ACTIVE')
    #     schedule = self.controller.load_schedules()[0]
    #     for _ in range(60):
    #         if schedule.last_executed:
    #             break
    #         time.sleep(0.1)
    #     assert schedule is not None, 'No schedule'
    #     assert schedule.last_executed is not None, ', '.join(str(x) for x in self.controller._scheduler.get_jobs())
    #     assert time.time() - 10 < schedule.last_executed < time.time() + 10
    #     assert schedule.status == 'COMPLETED'

    def test_skip_grace_time(self):
        self._add_schedule(name='schedule',
                           start=self.utcnow - 86400,  # yesterday
                           action='GROUP_ACTION',
                           arguments=1,
                           status='ACTIVE')
        schedule = self.controller.load_schedules()[0]
        time.sleep(0.2)
        self.assertEqual(schedule.status, 'ACTIVE')
        self.assertIsNone(schedule.last_executed)

    def test_expire_repeat_end(self):
        self._add_schedule(name='schedule',
                           start=self.utcnow - 86400,  # yesterday
                           end=self.utcnow - 14400,  # 4h
                           repeat='* * * * *',
                           action='GROUP_ACTION',
                           arguments=1,
                           status='ACTIVE')
        schedule = self.controller.load_schedules()[0]
        self.assertEqual(schedule.status, 'COMPLETED')
        self.assertIsNone(schedule.last_executed)

    def _add_schedule(self, **kwargs):
        schedules = self.controller.load_schedules()
        dto = ScheduleDTO(id=None, source='gateway', **kwargs)
        self.controller.save_schedules([dto])
        for _ in range(60):
            if len(self.controller.load_schedules()) > len(schedules):
                break
            time.sleep(0.1)
