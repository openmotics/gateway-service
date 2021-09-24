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

import pytz
import six
from apscheduler.events import EVENT_JOB_EXECUTED
from apscheduler.schedulers.background import BackgroundScheduler
from croniter import croniter

from gateway.dto import ScheduleDTO
from gateway.mappers import ScheduleMapper
from gateway.models import Schedule
from gateway.webservice import params_parser
from ioc import INJECTED, Inject, Injectable, Singleton
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from typing import Dict, List, Optional
    from apscheduler.job import Job
    from gateway.dto import LegacyScheduleDTO, LegacyStartupActionDTO
    from gateway.group_action_controller import GroupActionController
    from gateway.hal.master_controller import MasterController
    from gateway.system_controller import SystemController
    from gateway.webservice import WebInterface

logging.getLogger('apscheduler').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


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

    @Inject
    def __init__(self, group_action_controller=INJECTED, master_controller=INJECTED, system_controller=INJECTED):
        # type: (GroupActionController, MasterController, SystemController) -> None
        self._group_action_controller = group_action_controller
        self._master_controller = master_controller
        self._web_interface = None  # type: Optional[WebInterface]
        self._schedules = {}  # type: Dict[int, ScheduleDTO]
        self._jobs = {}  # type: Dict[str, Job]
        timezone = system_controller.get_python_timezone()
        self._scheduler = BackgroundScheduler(timezone=timezone, job_defaults={
            'coalesce': True,
            'misfire_grace_time': 3600  # 1h
        })
        self._scheduler.add_listener(self._handle_schedule_event, EVENT_JOB_EXECUTED)
        self.reload_schedules()

    def set_webinterface(self, web_interface):
        # type: (WebInterface) -> None
        self._web_interface = web_interface

    def start(self):
        # type: () -> None
        self._scheduler.start()

    def stop(self):
        # type: () -> None
        self._scheduler.shutdown()

    def _handle_schedule_event(self, event):
        job = self._jobs.get(event.job_id)
        schedule_dto = self._schedules[int(event.job_id)]
        if job and hasattr(job, 'next_run_time') and job.next_run_time:
            schedule_dto.next_execution = datetime_to_timestamp(job.next_run_time)
        else:
            schedule_dto.status = 'COMPLETED'
            schedule = ScheduleMapper.dto_to_orm(schedule_dto)
            schedule.save()

    def _schedule_job(self, schedule_dto):
        # type: (ScheduleDTO) -> None
        job_id = str(schedule_dto.id)
        if schedule_dto.status == 'ACTIVE':
            job = self._jobs.get(job_id)
            if schedule_dto.repeat is None:
                run_date = datetime.fromtimestamp(schedule_dto.start)
                job = self._scheduler.add_job(self._execute_schedule, args=(schedule_dto,),
                                              id=job_id, name=schedule_dto.name,
                                              trigger='date', run_date=run_date)
            else:
                # TODO: parse
                minute, hour, day, month, day_of_week = schedule_dto.repeat.split(' ')
                end_date = datetime.fromtimestamp(schedule_dto.end) if schedule_dto.end else None
                job = self._scheduler.add_job(self._execute_schedule, args=(schedule_dto,),
                                              id=job_id, name=schedule_dto.name,
                                              trigger='cron', end_date=end_date,
                                              minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)
            self._jobs[job_id] = job

    def reload_schedules(self):
        # type: () -> None
        if time.time() < SchedulingController.NO_NTP_LOWER_LIMIT:
            logger.warning('Detected invalid system time, skipping schedules')
            return
        schedule_ids = []
        # TODO: reschedule jobs
        self._scheduler.remove_all_jobs()
        for schedule in Schedule.select():
            schedule_dto = ScheduleMapper.orm_to_dto(schedule)
            self._schedule_job(schedule_dto)
            self._schedules[schedule_dto.id] = schedule_dto
            schedule_ids.append(schedule_dto.id)
        for schedule_id in list(self._schedules.keys()):
            if schedule_id not in schedule_ids:
                self._schedules.pop(schedule_id, None)
                self._jobs.pop(str(schedule_id), None)
        self.refresh_schedules()

    def refresh_schedules(self):
        # type: () -> None
        for schedule_dto in self._schedules.values():
            job = self._jobs.get(str(schedule_dto.id))
            if job and hasattr(job, 'next_run_time') and job.next_run_time:
                schedule_dto.next_execution = datetime_to_timestamp(job.next_run_time)
            if schedule_dto.end and schedule_dto.end < time.time() - 3600:
                schedule_dto.status = 'COMPLETED'
                schedule = ScheduleMapper.dto_to_orm(schedule_dto)
                schedule.save()

    def load_schedule(self, schedule_id):
        # type: (int) -> ScheduleDTO
        schedule_dto = self._schedules.get(schedule_id)
        if schedule_dto is None:
            raise Schedule.DoesNotExist('Schedule {0} does not exist'.format(schedule_id))
        return schedule_dto

    def load_schedules(self, source=Schedule.Sources.GATEWAY):
        # type: (str) -> List[ScheduleDTO]
        return [schedule_dto for schedule_dto in self._schedules.values()
                if schedule_dto.source == source]

    def save_schedules(self, schedules):
        # type: (List[ScheduleDTO]) -> None
        for schedule_dto in schedules:
            schedule = ScheduleMapper.dto_to_orm(schedule_dto)
            self._validate(schedule)
            schedule.save()
        self.reload_schedules()

    def remove_schedules(self, schedules):
        # type: (List[ScheduleDTO]) -> None
        Schedule.delete().where(Schedule.id.in_([s.id for s in schedules])).execute()
        self.reload_schedules()

    def _execute_schedule(self, schedule_dto):
        # type: (ScheduleDTO) -> None
        if schedule_dto.running:
            return
        try:
            schedule_dto.running = True
            logger.debug('Executing schedule {0} ({1})'.format(schedule_dto.name, schedule_dto.action))
            if schedule_dto.arguments is None:
                raise ValueError('Invalid schedule arguments')
            # Execute
            if schedule_dto.action == 'GROUP_ACTION':
                self._group_action_controller.do_group_action(schedule_dto.arguments)
            elif schedule_dto.action == 'BASIC_ACTION':
                self._group_action_controller.do_basic_action(**schedule_dto.arguments)
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

    # Legacy master driven schedules & startup action

    def load_scheduled_action(self, scheduled_action_id):
        # type: (int) -> LegacyScheduleDTO
        return self._master_controller.load_scheduled_action(scheduled_action_id)

    def load_scheduled_actions(self):
        # type: () -> List[LegacyScheduleDTO]
        return self._master_controller.load_scheduled_actions()

    def save_scheduled_actions(self, scheduled_actions):
        # type: (List[LegacyScheduleDTO]) -> None
        self._master_controller.save_scheduled_actions(scheduled_actions)

    def load_startup_action(self):
        # type: () -> LegacyStartupActionDTO
        return self._master_controller.load_startup_action()

    def save_startup_action(self, startup_action):
        # type: (LegacyStartupActionDTO) -> None
        self._master_controller.save_startup_action(startup_action)


def datetime_to_timestamp(date):
    # type: (datetime) -> float
    return (date - datetime(1970, 1, 1, tzinfo=pytz.UTC)).total_seconds()
