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

import os
import tempfile
import time
import unittest

import xmlrunner
from mock import Mock
from peewee import SqliteDatabase

import fakesleep
from gateway.dto import ScheduleDTO
from gateway.models import Schedule
from gateway.scheduling import SchedulingController
from gateway.ventilation_controller import VentilationController
from gateway.webservice import WebInterface
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Schedule]


class SchedulingControllerTest(unittest.TestCase):
    RETURN_DATA = {}
    ORIGINAL_TIME = time.time
    ORIGINAL_SLEEP = time.sleep
    _db_filename = None

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls._db_filename = tempfile.mktemp()
        cls.test_db = SqliteDatabase(cls._db_filename)
        fakesleep.monkey_patch()

    @classmethod
    def tearDownClass(cls):
        fakesleep.monkey_restore()
        if os.path.exists(cls._db_filename):
            os.remove(cls._db_filename)

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        SchedulingControllerTest.RETURN_DATA = {}

    def tearDown(self):
        SchedulingControllerTest.RETURN_DATA = {}
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    @staticmethod
    def _get_controller():
        def _do_group_action(group_action_id):
            SchedulingControllerTest.RETURN_DATA['do_group_action'] = group_action_id
            return {}

        def _do_basic_action(action_type, action_number):
            SchedulingControllerTest.RETURN_DATA['do_basic_action'] = (action_type, action_number)
            return {}

        gateway_api = Mock()
        gateway_api.get_timezone = lambda: 'UTC'
        gateway_api.do_basic_action = _do_basic_action

        group_action_controller = Mock()
        group_action_controller.do_group_action = _do_group_action

        SetUpTestInjections(gateway_api=gateway_api,
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
                            group_action_controller=group_action_controller,
                            module_controller=Mock())
        controller = SchedulingController()
        SetUpTestInjections(scheduling_controller=controller)
        controller.set_webinterface(WebInterface())
        return controller

    def test_save_load(self):
        controller = SchedulingControllerTest._get_controller()
        dto = ScheduleDTO(id=None, name='schedule', start=0, action='GROUP_ACTION', arguments=0)
        controller.save_schedules([(dto, ['name', 'start', 'action', 'arguments'])])
        loaded_dto = controller.load_schedule(schedule_id=1)
        for field in ['name', 'start', 'action', 'repeat', 'duration', 'end', 'arguments']:
            self.assertEqual(getattr(dto, field), getattr(loaded_dto, field))
        self.assertEqual('ACTIVE', loaded_dto.status)
        controller = SchedulingControllerTest._get_controller()  # Force new controller
        loaded_dto = controller.load_schedule(schedule_id=1)
        for field in ['name', 'start', 'action', 'repeat', 'duration', 'end', 'arguments']:
            self.assertEqual(getattr(dto, field), getattr(loaded_dto, field))
        self.assertEqual('ACTIVE', loaded_dto.status)

    def test_base_validation(self):
        controller = SchedulingControllerTest._get_controller()
        with self.assertRaises(RuntimeError):
            # Must have a name
            schedule = Schedule(name=None)
            controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Unaccepted action
            schedule = Schedule(name='test', start=time.time(), action='FOO')
            controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Duration too short
            schedule = Schedule(name='test', start=time.time(), action='GROUP_ACTION', duration=10)
            controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # End when not repeating
            schedule = Schedule(name='test', start=time.time(), action='GROUP_ACTION', end=time.time() + 1)
            controller._validate(schedule)
        with self.assertRaises(RuntimeError):
            # Invalid repeat string
            schedule = Schedule(name='test', start=time.time(), action='GROUP_ACTION', repeat='foo')
            controller._validate(schedule)

    def test_group_action(self):
        fakesleep.monkey_restore()
        controller = SchedulingControllerTest._get_controller()

        # New controller is empty
        self.assertEqual(0, len(controller.load_schedules()))

        # Doesn't support duration
        with self.assertRaises(RuntimeError) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='GROUP_ACTION', duration=1000)
        self.assertEqual('A schedule of type GROUP_ACTION does not have a duration. It is a one-time trigger',
                         str(ctx.exception))

        # Incorrect argument
        with self.assertRaises(RuntimeError) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='GROUP_ACTION', arguments='foo')
        self.assertEqual(
            'The arguments of a GROUP_ACTION schedule must be an integer, representing the Group Action to be executed',
            str(ctx.exception))

        # Normal
        SchedulingControllerTest._add_schedule(controller,
                                               name='schedule', start=time.time()+5, action='GROUP_ACTION', arguments=1)
        schedules = controller.load_schedules()
        self.assertEqual(1, len(schedules))
        schedule = schedules[0]
        self.assertEqual('schedule', schedule.name)
        self.assertEqual('ACTIVE', schedule.status)
        controller.start()
        time.sleep(0.5)
        controller.stop()
        schedule = controller.load_schedules()[0]
        self.assertIsNotNone(schedule.last_executed)
        self.assertEqual(schedule.status, 'COMPLETED')
        self.assertEqual(1, SchedulingControllerTest.RETURN_DATA['do_group_action'])
        fakesleep.monkey_patch()

    def test_basic_action(self):
        fakesleep.monkey_restore()
        controller = SchedulingControllerTest._get_controller()

        # New controller is empty
        self.assertEqual(0, len(controller.load_schedules()))

        # Doesn't support duration
        with self.assertRaises(RuntimeError) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='BASIC_ACTION', duration=1000)
        self.assertEqual('A schedule of type BASIC_ACTION does not have a duration. It is a one-time trigger',
                         str(ctx.exception))

        # Incorrect argument
        invalid_arguments_error = 'The arguments of a BASIC_ACTION schedule must be of type dict with arguments ' \
                                  '`action_type` and `action_number`'
        with self.assertRaises(RuntimeError) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='BASIC_ACTION', arguments='foo')
        self.assertEqual(invalid_arguments_error, str(ctx.exception))
        with self.assertRaises(RuntimeError) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='BASIC_ACTION',
                                                   arguments={'action_type': 1})
        self.assertEqual(invalid_arguments_error, str(ctx.exception))

        # Normal
        dto = ScheduleDTO(id=None, name='schedule', start=time.time()+5, action='BASIC_ACTION',
                          arguments={'action_type': 1, 'action_number': 2})
        controller.save_schedules([(dto, ['name', 'start', 'action', 'arguments'])])
        schedules = controller.load_schedules()
        self.assertEqual(1, len(schedules))
        schedule = schedules[0]
        self.assertEqual('schedule', schedule.name)
        self.assertEqual('ACTIVE', schedule.status)
        controller.start()
        time.sleep(0.5)
        controller.stop()
        schedule = controller.load_schedules()[0]
        self.assertIsNotNone(schedule.last_executed)
        self.assertEqual(schedule.status, 'COMPLETED')
        self.assertEqual((1, 2), SchedulingControllerTest.RETURN_DATA['do_basic_action'])
        fakesleep.monkey_patch()

    def test_local_api(self):
        fakesleep.monkey_restore()
        controller = SchedulingControllerTest._get_controller()

        # New controller is empty
        self.assertEqual(0, len(controller.load_schedules()))

        # Doesn't support duration
        with self.assertRaises(RuntimeError) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='LOCAL_API', duration=1000)
        self.assertEqual('A schedule of type LOCAL_API does not have a duration. It is a one-time trigger',
                         str(ctx.exception))

        # Incorrect argument
        invalid_arguments_error = 'The arguments of a LOCAL_API schedule must be of type dict with arguments `name` ' \
                                  'and `parameters`'
        with self.assertRaises(RuntimeError) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='LOCAL_API', arguments='foo')
        self.assertEqual(invalid_arguments_error, str(ctx.exception))
        with self.assertRaises(RuntimeError) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='LOCAL_API', arguments={'name': 1})
        self.assertEqual(invalid_arguments_error, str(ctx.exception))

        # Not a valid call
        with self.assertRaises(RuntimeError) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='LOCAL_API',
                                                   arguments={'name': 'foo', 'parameters': {}})
        self.assertEqual('The arguments of a LOCAL_API schedule must specify a valid and (plugin_)exposed call',
                         str(ctx.exception))
        with self.assertRaises(Exception) as ctx:
            SchedulingControllerTest._add_schedule(controller,
                                                   name='schedule', start=0, action='LOCAL_API',
                                                   arguments={'name': 'do_basic_action',
                                                              'parameters': {'action_type': 'foo',
                                                                             'action_number': 4}})
        self.assertIn('could not convert string to float', str(ctx.exception))

        # Normal
        SchedulingControllerTest._add_schedule(controller,
                                               name='schedule', start=time.time()+5, action='LOCAL_API',
                                               arguments={'name': 'do_basic_action',
                                                          'parameters': {'action_type': 3,
                                                                         'action_number': 4}})
        schedules = controller.load_schedules()
        self.assertEqual(1, len(schedules))
        schedule = schedules[0]
        self.assertEqual('schedule', schedule.name)
        self.assertEqual('ACTIVE', schedule.status)
        controller.start()
        time.sleep(0.5)
        controller.stop()
        schedule = controller.load_schedules()[0]
        self.assertIsNotNone(schedule.last_executed)
        self.assertEqual(schedule.status, 'COMPLETED')
        self.assertEqual((3, 4), SchedulingControllerTest.RETURN_DATA['do_basic_action'])
        fakesleep.monkey_patch()

    def test_two_actions(self):
        controller = SchedulingControllerTest._get_controller()
        SchedulingControllerTest._add_schedule(controller,
                                               name='basic_action', start=0, action='BASIC_ACTION',
                                               arguments={'action_type': 1, 'action_number': 2})
        SchedulingControllerTest._add_schedule(controller,
                                               name='group_action', start=0, action='GROUP_ACTION',
                                               arguments=1)
        schedules = controller.load_schedules()
        self.assertEqual(2, len(schedules))
        self.assertEqual(['basic_action', 'group_action'], sorted(s.name for s in schedules))
        for s in schedules:
            if s.name == 'group_action':
                controller.remove_schedules([s])
        schedules = controller.load_schedules()
        self.assertEqual(1, len(schedules))
        self.assertEqual('basic_action', schedules[0].name)

    def test_schedule_is_due(self):
        now_offset = 1577836800  # 2020-01-01
        offset_2018 = 1514764800  # 2018-01-01
        minute = 60
        hour = 60 * minute
        fakesleep.reset(seconds=offset_2018)
        SchedulingController.TIMEZONE = 'Europe/Brussels'
        schedule = ScheduleDTO(id=1,
                               name='schedule',
                               start=offset_2018,
                               repeat='0 * * * *',
                               duration=None,
                               end=now_offset + 24 * hour,
                               action='GROUP_ACTION',
                               arguments=1,
                               status='ACTIVE')
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertFalse(schedule.is_due)
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(SchedulingController.NO_NTP_LOWER_LIMIT + 1 * hour, schedule.next_execution)
        time.sleep(1 * hour)
        self.assertFalse(schedule.is_due)  # Date is before 2019
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(SchedulingController.NO_NTP_LOWER_LIMIT + 1 * hour, schedule.next_execution)
        fakesleep.reset(seconds=now_offset)
        self.assertFalse(schedule.is_due)  # Time jump is ignored
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(now_offset + 1 * hour, schedule.next_execution)
        time.sleep(1 * hour)
        self.assertTrue(schedule.is_due)
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(now_offset + 2 * hour, schedule.next_execution)

    def test_one_minute_schedule(self):
        now_offset = 1577836800  # 2020
        minute = 60
        fakesleep.reset(seconds=now_offset)
        SchedulingController.TIMEZONE = 'Europe/Brussels'
        schedule = ScheduleDTO(id=1,
                               name='schedule',
                               start=0 * minute,
                               repeat='* * * * *',
                               duration=None,
                               end=now_offset + 60 * minute,
                               action='GROUP_ACTION',
                               arguments=1,
                               status='ACTIVE')
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertFalse(schedule.is_due)
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(now_offset + 1 * minute, schedule.next_execution)
        time.sleep(1 * minute)
        self.assertTrue(schedule.is_due)
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(now_offset + 2 * minute, schedule.next_execution)
        time.sleep(1 * minute)
        self.assertTrue(schedule.is_due)
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(now_offset + 3 * minute, schedule.next_execution)

    def test_midnight_crossover(self):
        now_offset = 1615939080  # 16/03/21 23:58
        minute = 60
        fakesleep.reset(seconds=now_offset)  # Tricks the system to be in the time we specified
        SchedulingController.TIMEZONE = 'Europe/Brussels'
        schedule = ScheduleDTO(id=1,
                               name='schedule',
                               start=0 * minute,
                               repeat='* * * * *',
                               duration=None,
                               end=now_offset + 10 * minute,
                               action='GROUP_ACTION',
                               arguments=1,
                               status='ACTIVE')
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertFalse(schedule.is_due)
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(now_offset + 1 * minute, schedule.next_execution)
        time.sleep(1 * minute)
        self.assertTrue(schedule.is_due)
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(now_offset + 2 * minute, schedule.next_execution)
        time.sleep(1 * minute)
        self.assertTrue(schedule.is_due)
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertEqual(now_offset + 3 * minute, schedule.next_execution)

    # test edge cases -> sunday evening until monday morning AND end of month till new month
    def test_edge_cases_cron(self):
        now_offset = 1616371020  # Date and time: Sunday, March 21, 2021 11:57:00 PM GMT
        minute = 60
        SchedulingController.TIMEZONE = 'Europe/Brussels'
        fakesleep.reset(seconds=now_offset)
        SchedulingController.TIMEZONE = 'Europe/Brussels'
        schedule = ScheduleDTO(id=1,
                               name='schedule',
                               start=200,  # Thursday, January 1, 1970 1:03:20 AM
                               repeat='* * * * *',  # every minute
                               duration=None,
                               end=now_offset + 10 * minute,  # for 10 minuted
                               action='GROUP_ACTION',
                               arguments=1,
                               status='ACTIVE')
        # Should be 1616371020 + 60 = 1616371080
        schedule.next_execution = SchedulingController._get_next_execution(schedule)
        self.assertFalse(schedule.is_due)
        # Should still be 1616371020 + 60 = 1616371080
        for i in range(1, 11):
            schedule.next_execution = SchedulingController._get_next_execution(schedule)
            self.assertEqual(now_offset + i * minute, schedule.next_execution)
            time.sleep(minute)
            self.assertTrue(schedule.is_due)

        # now testing end of month behaviour
        now_offset = 1617235020  # 2021-03-31 23:57:00
        fakesleep.reset(seconds=now_offset)
        schedule.end = now_offset + 10 * minute  # Update when the schedule should end
        for i in range(1, 11):
            schedule.next_execution = SchedulingController._get_next_execution(schedule)
            self.assertEqual(now_offset + i * minute, schedule.next_execution)
            time.sleep(minute)
            self.assertTrue(schedule.is_due)

    def test_next_exec(self):  # Fixed scheduling bug, where a GW reboot set the DTO's next_exec to when the
        # Schedule started (in the past), and the schedule never got reloaded
        fakesleep.monkey_restore()
        # Stop fakesleep, because of race conditions with the controllers's processing thread
        # Make a scheduleController object
        controller = SchedulingControllerTest._get_controller()
        scheduledto = ScheduleDTO(id=1,
                               name='schedule',
                               start=0,  # Thursday, January 1, 1970 1:03:20 AM
                               repeat='* * * * *',  # every minute
                               duration=None,
                               action='GROUP_ACTION',
                               arguments=1,
                               status='ACTIVE')
        scheduledto.next_execution = 56828400  # 1990
        # Manualy set the next_exec to avoid reloading the schedules
        controller._schedules[1] = scheduledto, None
        # Start the thread
        controller.start()
        time.sleep(0.5)
        controller.stop()
        sched = controller.load_schedules()[0]
        self.assertTrue(time.time() + 60 > sched.next_execution > time.time())
        fakesleep.monkey_patch()

    @staticmethod
    def _add_schedule(controller, **kwargs):
        dto = ScheduleDTO(id=None, **kwargs)
        controller.save_schedules([(dto, list(kwargs.keys()))])


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
