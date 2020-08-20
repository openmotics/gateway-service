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
import unittest

import xmlrunner
import time
import fakesleep
from mock import Mock
from threading import Lock
from ioc import SetTestMode, SetUpTestInjections
from gateway.webservice import WebInterface
from gateway.scheduling import SchedulingController, Schedule


class SchedulingControllerTest(unittest.TestCase):
    RETURN_DATA = {}
    ORIGINAL_TIME = time.time
    ORIGINAL_SLEEP = time.sleep

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        fakesleep.monkey_patch()

    @classmethod
    def tearDownClass(cls):
        fakesleep.monkey_restore()

    def setUp(self):
        self._db = "test.schedule.{0}.db".format(time.time())
        SchedulingControllerTest.RETURN_DATA = {}
        if os.path.exists(self._db):
            os.remove(self._db)

    def tearDown(self):
        SchedulingControllerTest.RETURN_DATA = {}
        if os.path.exists(self._db):
            os.remove(self._db)

    def _get_controller(self):
        def _do_group_action(group_action_id):
            SchedulingControllerTest.RETURN_DATA['do_group_action'] = group_action_id
            return {}

        def _do_basic_action(action_type, action_number):
            SchedulingControllerTest.RETURN_DATA['do_basic_action'] = (action_type, action_number)
            return {}

        gateway_api = Mock()
        gateway_api.get_timezone = lambda: 'Europe/Brussels'
        gateway_api.do_basic_action = _do_basic_action

        group_action_controller = Mock()
        group_action_controller.do_group_action = _do_group_action

        SetUpTestInjections(scheduling_db=self._db,
                            scheduling_db_lock=Lock(),
                            gateway_api=gateway_api,
                            user_controller=None,
                            maintenance_controller=None,
                            message_client=None,
                            configuration_controller=None,
                            thermostat_controller=None,
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

    def test_base_validation(self):
        controller = self._get_controller()
        with self.assertRaises(RuntimeError):
            # Must have a name
            controller._validate(None, None, None, None, None, None, None)
        with self.assertRaises(RuntimeError):
            # Unaccepted type
            controller._validate('test', time.time(), 'FOO', None, None, None, None)
        with self.assertRaises(RuntimeError):
            # Duration too short
            controller._validate('test', time.time(), 'GROUP_ACTION', None, None, 10, None)
        with self.assertRaises(RuntimeError):
            # End when not repeating
            controller._validate('test', time.time(), 'GROUP_ACTION', None, None, None, 1)
        with self.assertRaises(RuntimeError):
            # Invalid repeat string
            controller._validate('test', time.time(), 'GROUP_ACTION', None, 'foo', None, None)

    def test_group_action(self):
        start = time.time()
        controller = self._get_controller()

        # New controller is empty
        self.assertEqual(len(controller.schedules), 0)

        # Doesn't support duration
        with self.assertRaises(RuntimeError) as ctx:
            controller.add_schedule('group_action', start + 120, 'GROUP_ACTION', None, None, 1000, None)
        self.assertEqual(str(ctx.exception), 'A schedule of type GROUP_ACTION does not have a duration. It is a one-time trigger')

        # Incorrect argument
        with self.assertRaises(RuntimeError) as ctx:
            controller.add_schedule('group_action', start + 120, 'GROUP_ACTION', 'foo', None, None, None)
        self.assertEqual(str(ctx.exception), 'The arguments of a GROUP_ACTION schedule must be an integer, representing the Group Action to be executed')

        # Normal
        controller.add_schedule('group_action', start + 120, 'GROUP_ACTION', 1, None, None, None)
        self.assertEqual(len(controller.schedules), 1)
        schedule = controller.schedules[0]
        self.assertEqual(schedule.name, 'group_action')
        self.assertEqual(schedule.status, 'ACTIVE')
        controller.start()
        self._wait_for_completed(schedule)
        self.assertEqual(SchedulingControllerTest.RETURN_DATA['do_group_action'], 1)
        controller.stop()

    def test_basic_action(self):
        start = time.time()
        controller = self._get_controller()

        # New controller is empty
        self.assertEqual(len(controller.schedules), 0)

        # Doesn't support duration
        with self.assertRaises(RuntimeError) as ctx:
            controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', None, None, 1000, None)
        self.assertEqual(str(ctx.exception), 'A schedule of type BASIC_ACTION does not have a duration. It is a one-time trigger')

        # Incorrect argument
        invalid_arguments_error = 'The arguments of a BASIC_ACTION schedule must be of type dict with arguments `action_type` and `action_number`'
        with self.assertRaises(RuntimeError) as ctx:
            controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', 'foo', None, None, None)
        self.assertEqual(str(ctx.exception), invalid_arguments_error)
        with self.assertRaises(RuntimeError) as ctx:
            controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', {'action_type': 1}, None, None, None)
        self.assertEqual(str(ctx.exception), invalid_arguments_error)

        # Normal
        controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', {'action_type': 1, 'action_number': 2}, None, None, None)
        self.assertEqual(len(controller.schedules), 1)
        schedule = controller.schedules[0]
        self.assertEqual(schedule.name, 'basic_action')
        self.assertEqual(schedule.status, 'ACTIVE')
        controller.start()
        self._wait_for_completed(schedule)
        self.assertEqual(SchedulingControllerTest.RETURN_DATA['do_basic_action'], (1, 2))
        controller.stop()

    def test_local_api(self):
        start = time.time()
        controller = self._get_controller()

        # New controller is empty
        self.assertEqual(len(controller.schedules), 0)

        # Doesn't support duration
        with self.assertRaises(RuntimeError) as ctx:
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', None, None, 1000, None)
        self.assertEqual(str(ctx.exception), 'A schedule of type LOCAL_API does not have a duration. It is a one-time trigger')

        # Incorrect argument
        invalid_arguments_error = 'The arguments of a LOCAL_API schedule must be of type dict with arguments `name` and `parameters`'
        with self.assertRaises(RuntimeError) as ctx:
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', 'foo', None, None, None)
        self.assertEqual(str(ctx.exception), invalid_arguments_error)
        with self.assertRaises(RuntimeError) as ctx:
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', {'name': 1}, None, None, None)
        self.assertEqual(str(ctx.exception), invalid_arguments_error)

        # Not a valid call
        with self.assertRaises(RuntimeError) as ctx:
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', {'name': 'foo', 'parameters': {}}, None, None, None)
        self.assertEqual(str(ctx.exception), 'The arguments of a LOCAL_API schedule must specify a valid and (plugin_)exposed call')
        with self.assertRaises(Exception) as ctx:
            controller.add_schedule('local_api', start + 120, 'LOCAL_API', {'name': 'do_basic_action',
                                                                            'parameters': {'action_type': 'foo', 'action_number': 4}}, None, None, None)
        self.assertEqual(str(ctx.exception), 'could not convert string to float: foo')

        # Normal
        controller.add_schedule('local_api', start + 120, 'LOCAL_API', {'name': 'do_basic_action',
                                                                        'parameters': {'action_type': 3, 'action_number': 4}}, None, None, None)
        self.assertEqual(len(controller.schedules), 1)
        schedule = controller.schedules[0]
        self.assertEqual(schedule.name, 'local_api')
        self.assertEqual(schedule.status, 'ACTIVE')
        controller.start()
        self._wait_for_completed(schedule)
        self.assertEqual(SchedulingControllerTest.RETURN_DATA['do_basic_action'], (3, 4))
        controller.stop()

    def test_two_actions(self):
        start = time.time()
        controller = self._get_controller()
        controller.add_schedule('basic_action', start + 120, 'BASIC_ACTION', {'action_type': 1, 'action_number': 2}, None, None, None)
        controller.add_schedule('group_action', start + 120, 'GROUP_ACTION', 1, None, None, None)
        self.assertEqual(len(controller.schedules), 2)
        self.assertEqual(sorted(s.name for s in controller.schedules), ['basic_action', 'group_action'])
        for s in controller.schedules:
            if s.name == 'group_action':
                controller.remove_schedule(s.id)
        self.assertEqual(len(controller.schedules), 1)
        self.assertEqual(controller.schedules[0].name, 'basic_action')

    def test_schedule_is_due(self):
        now_offset = 1577836800  # 2020-01-01
        offset_2018 = 1514764800  # 2018-01-01
        minute = 60
        hour = 60 * minute
        fakesleep.reset(seconds=offset_2018)
        Schedule.timezone = 'UTC'
        schedule = Schedule(id=1,
                            name='schedule',
                            start=offset_2018,
                            repeat='0 * * * *',
                            duration=None,
                            end=now_offset + 24 * hour,
                            schedule_type='GROUP_ACTION',
                            arguments=1,
                            status='ACTIVE')
        self.assertFalse(schedule.is_due)
        self.assertEqual(offset_2018 + 1 * hour, schedule.next_execution)
        time.sleep(1 * hour)
        self.assertFalse(schedule.is_due)  # Date is before 2019
        self.assertEqual(offset_2018 + 2 * hour, schedule.next_execution)
        time.sleep(1 * hour)
        self.assertFalse(schedule.is_due)  # Date is (still) before 2019
        self.assertEqual(offset_2018 + 3 * hour, schedule.next_execution)
        fakesleep.reset(seconds=now_offset)
        self.assertFalse(schedule.is_due)  # Time jump is ignored
        self.assertEqual(now_offset + 1 * hour, schedule.next_execution)
        time.sleep(1 * hour)
        self.assertTrue(schedule.is_due)
        self.assertEqual(now_offset + 2 * hour, schedule.next_execution)

    def test_one_minute_schedule(self):
        now_offset = 1577836800  # 2020
        minute = 60
        fakesleep.reset(seconds=now_offset)
        Schedule.timezone = 'UTC'
        schedule = Schedule(id=1,
                            name='schedule',
                            start=0 * minute,
                            repeat='* * * * *',
                            duration=None,
                            end=60 * minute,
                            schedule_type='GROUP_ACTION',
                            arguments=1,
                            status='ACTIVE')
        self.assertFalse(schedule.is_due)
        self.assertEqual(now_offset + 1 * minute, schedule.next_execution)
        time.sleep(1 * minute)
        self.assertTrue(schedule.is_due)
        self.assertEqual(now_offset + 2 * minute, schedule.next_execution)
        time.sleep(1 * minute)
        self.assertTrue(schedule.is_due)
        self.assertEqual(now_offset + 3 * minute, schedule.next_execution)

    def test_next_execution(self):
        # Assert that the _next_execution won't return the base_time
        Schedule.timezone = 'UTC'
        next_execution = Schedule._next_execution(3600, '0 * * * *')
        self.assertEqual(7200, next_execution)

    def _wait_for_completed(self, schedule, timeout=5):
        def _is_completed():
            return schedule.last_executed is not None and schedule.status == 'COMPLETED'

        _time = SchedulingControllerTest.ORIGINAL_TIME
        _sleep = SchedulingControllerTest.ORIGINAL_SLEEP
        end = _time() + timeout
        while not _is_completed() and _time() < end:
            _sleep(0.01)
        self.assertTrue(_is_completed())


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
