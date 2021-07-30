# Copyright (C) 2016 OpenMotics BV
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
The scheduling module contains the SchedulingController, this controller is used for scheduling various actions
"""

from __future__ import absolute_import

import json
import logging
import time
from datetime import datetime
import threading

import pytz
import six
from croniter import croniter
from operator import itemgetter, attrgetter

from gateway.daemon_thread import BaseThread, DaemonThread
from gateway.dto import ScheduleDTO
from gateway.mappers import ScheduleMapper
from gateway.models import Schedule
from gateway.webservice import params_parser
from ioc import INJECTED, Inject, Injectable, Singleton
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from typing import List, Dict, Tuple, Optional
    from gateway.group_action_controller import GroupActionController
    from gateway.gateway_api import GatewayApi

logger = logging.getLogger('gateway.scheduling.controller')


@Injectable.named('scheduling_controller')
@Singleton
class SchedulingController(object):
    """
    The SchedulingController controls schedules and executes them. Based on their type, they can trigger different
    behavior.

    Supported actions:
    * GROUP_ACTION: Executes a Group Action
      * Required arguments: json encoded Group Action id
    * BASIC_ACTION: Executes a Basic Action
      * Required arguments: {'action_type': <action type>,
                             'action_number': <action number>}
    * LOCAL_API: Executes a local API call
      * Required arguments: {'name': '<name of the call>',
                             'parameters': {<kwargs for the call>}}

    Supported repeats:
    * None: Single execution at start time
    * String: Cron format, docs at https://github.com/kiorky/croniter
    """

    NO_NTP_LOWER_LIMIT = 1546300800.0  # 2019-01-01
    TIMEZONE = None

    @Inject
    def __init__(self, gateway_api=INJECTED, group_action_controller=INJECTED):
        # type: (GatewayApi, GroupActionController) -> None
        self._gateway_api = gateway_api
        self._group_action_controller = group_action_controller
        self._web_interface = None
        self._stop = False
        self._processor = None  # type: Optional[DaemonThread]
        self._schedules = {}  # type: Dict[int, Tuple[ScheduleDTO, Schedule]]
        self._event = threading.Event()

        SchedulingController.TIMEZONE = gateway_api.get_timezone()
        self.reload_schedules()

    def set_webinterface(self, web_interface):
        self._web_interface = web_interface

    def reload_schedules(self):
        found_ids = []
        for schedule in Schedule.select():
            schedule_dto = ScheduleMapper.orm_to_dto(schedule)
            schedule_dto.next_execution = SchedulingController._get_next_execution(schedule_dto)
            self._schedules[schedule_dto.id] = (schedule_dto, schedule)
            found_ids.append(schedule_dto.id)
        for schedule_id in list(self._schedules.keys()):
            if schedule_id not in found_ids:
                self._schedules.pop(schedule_id, None)

    def refresh_schedules(self):
        for schedule, _ in self._schedules.values():
            schedule.next_execution = SchedulingController._get_next_execution(schedule)

    def load_schedule(self, schedule_id):  # type: (int) -> ScheduleDTO
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            raise Schedule.DoesNotExist('Schedule {0} does not exist'.format(schedule_id))
        return schedule[0]

    def load_schedules(self):  # type: () -> List[ScheduleDTO]
        return [dto for dto, _ in self._schedules.values()]

    def save_schedules(self, schedules):  # type: (List[ScheduleDTO]) -> None
        for schedule_dto in schedules:
            schedule = ScheduleMapper.dto_to_orm(schedule_dto)
            self._validate(schedule)
            schedule.save()
        self.reload_schedules()
        self._event.set()  # If a new schedule is saved, set an event to interrupt the hanging _process thread

    def remove_schedules(self, schedules):  # type: (List[ScheduleDTO]) -> None
        _ = self
        Schedule.delete().where(Schedule.id.in_([s.id for s in schedules])).execute()
        self.reload_schedules()

    def start(self, custom_interval=30):  # Adding custom interval to pass the tests faster
        self._stop = False
        self._processor = DaemonThread(target=self._process,
                                       name='schedulingctl',
                                       interval=custom_interval)
        self._processor.start()

    def stop(self):
        if self._processor is not None:
            self._processor.stop()

    def _process(self):
        now = time.time()
        self.refresh_schedules()  # Bug fix
        pending_schedules = []
        for schedule_id in list(self._schedules.keys()):
            schedule_tuple = self._schedules.get(schedule_id)
            if schedule_tuple is None:
                continue
            schedule_dto, schedule = schedule_tuple
            if schedule_dto.status != 'ACTIVE':
                continue
            if schedule_dto.end is not None and schedule_dto.end < time.time():
                schedule_dto.status = 'COMPLETED'
                schedule.status = 'COMPLETED'
                schedule.save()
                continue
            if schedule_dto.next_execution is not None and schedule_dto.next_execution < now - 60:
                continue
            pending_schedules.append(schedule_dto)
        # Sort the schedules according to their next_execution

        pending_schedules = list(sorted(pending_schedules, key=attrgetter('next_execution')))
        if not pending_schedules:
            return
        next_start = pending_schedules[0].next_execution
        schedules_to_execute = [schedule_dto for schedule_dto in pending_schedules if schedule_dto.next_execution < next_start + 60]
        if not schedules_to_execute:
            return
        # Let this thread hang until it's time to execute the schedule
        logger.debug('next pending schedule %s, waiting %ss', datetime.fromtimestamp(next_start), next_start - now)
        self._event.wait(next_start - now)
        if self._event.isSet():  # If a new schedule is saved, stop hanging and refresh the schedules
            self._event.clear()
            return
        thread = BaseThread(name='schedulingexc',
                            target=self._execute_schedule, args=(schedules_to_execute,))
        thread.daemon = True
        thread.start()

    @staticmethod
    def _get_next_execution(schedule_dto):
        # type: (ScheduleDTO) -> Optional[float]
        if schedule_dto.repeat is None:
            # Check if start has passed
            return schedule_dto.start
        base_time = max(SchedulingController.NO_NTP_LOWER_LIMIT, schedule_dto.start, time.time())
        cron = croniter(schedule_dto.repeat,
                        datetime.fromtimestamp(base_time,
                                               pytz.timezone(SchedulingController.TIMEZONE)))
        return cron.get_next(ret_type=float)

    def _execute_schedule(self, schedules_to_execute):
        # type: (List[ScheduleDTO]) -> None
        for schedule_dto in schedules_to_execute:
            if schedule_dto.running:
                continue
            try:
                schedule_dto.running = True
                logger.info('Executing schedule {0} ({1})'.format(schedule_dto.name, schedule_dto.action))
                if schedule_dto.arguments is None:
                    raise ValueError('Invalid schedule arguments')
                # Execute
                if schedule_dto.action == 'GROUP_ACTION':
                    self._group_action_controller.do_group_action(schedule_dto.arguments)
                elif schedule_dto.action == 'BASIC_ACTION':
                    self._gateway_api.do_basic_action(**schedule_dto.arguments)
                elif schedule_dto.action == 'LOCAL_API':
                    func = getattr(self._web_interface, schedule_dto.arguments['name'])
                    func(**schedule_dto.arguments['parameters'])
                else:
                    logger.warning('Did not process schedule_dto {0}'.format(schedule_dto.name))

                # Cleanup or prepare for next run
                schedule_dto.last_executed = time.time()
                if schedule_dto.has_ended:
                    schedule_dto.status = 'COMPLETED'
                    schedule = ScheduleMapper.dto_to_orm(schedule_dto)
                    schedule.save()
            except CommunicationTimedOutException as ex:
                logger.error('Got error while executing schedule: {0}'.format(ex))
            except Exception as ex:
                logger.error('Got error while executing schedule: {0}'.format(ex))
                schedule_dto.last_executed = time.time()
            finally:
                schedule_dto.running = False
                schedule_dto.next_execution = SchedulingController._get_next_execution(schedule_dto)

    def _validate(self, schedule):
        # type: (Schedule) -> None
        if schedule.name is None or not isinstance(schedule.name, six.string_types) or schedule.name.strip() == '':
            raise RuntimeError('A schedule must have a name')
        # Check whether the requested type is valid
        accepted_types = ['GROUP_ACTION', 'BASIC_ACTION', 'LOCAL_API']
        if schedule.action not in accepted_types:
            raise RuntimeError('Unknown schedule type. Allowed: {0}'.format(', '.join(accepted_types)))
        # Check duration/repeat/end combinations
        if schedule.repeat is None:
            if schedule.end is not None:
                raise RuntimeError('No `end` is allowed when it is a non-repeated schedule')
        else:
            if not croniter.is_valid(schedule.repeat):
                raise RuntimeError('Invalid `repeat`. Should be a cron-style string. See croniter documentation')
        if schedule.duration is not None and schedule.duration <= 60:
            raise RuntimeError('If a duration is specified, it should be at least more than 60s')
        # Type specific checks
        if schedule.action == 'BASIC_ACTION':
            if schedule.duration is not None:
                raise RuntimeError('A schedule of type BASIC_ACTION does not have a duration. It is a one-time trigger')
            arguments = None if schedule.arguments is None else json.loads(schedule.arguments)
            if (not isinstance(arguments, dict) or
                    'action_type' not in arguments or not isinstance(arguments['action_type'], int) or
                    'action_number' not in arguments or not isinstance(arguments['action_number'], int) or
                    len(arguments) != 2):
                raise RuntimeError('The arguments of a BASIC_ACTION schedule must be of type dict with arguments `action_type` and `action_number`')
        elif schedule.action == 'GROUP_ACTION':
            if schedule.duration is not None:
                raise RuntimeError('A schedule of type GROUP_ACTION does not have a duration. It is a one-time trigger')
            arguments = None if schedule.arguments is None else json.loads(schedule.arguments)
            if not isinstance(arguments, int) or arguments < 0 or arguments > 254:
                raise RuntimeError('The arguments of a GROUP_ACTION schedule must be an integer, representing the Group Action to be executed')
        elif schedule.action == 'LOCAL_API':
            if schedule.duration is not None:
                raise RuntimeError('A schedule of type LOCAL_API does not have a duration. It is a one-time trigger')
            arguments = None if schedule.arguments is None else json.loads(schedule.arguments)
            if (not isinstance(arguments, dict) or
                    'name' not in arguments or
                    'parameters' not in arguments or not isinstance(arguments['parameters'], dict)):
                raise RuntimeError('The arguments of a LOCAL_API schedule must be of type dict with arguments `name` and `parameters`')
            func = getattr(self._web_interface, arguments['name']) if hasattr(self._web_interface, arguments['name']) else None
            if func is None or not callable(func) or not hasattr(func, 'plugin_exposed') or getattr(func, 'plugin_exposed') is False:
                raise RuntimeError('The arguments of a LOCAL_API schedule must specify a valid and (plugin_)exposed call')
            check = getattr(func, 'check')
            if check is not None:
                params_parser(arguments['parameters'], check)
