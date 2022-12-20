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
from datetime import datetime, timedelta

import pytz
import six
from apscheduler.events import EVENT_JOB_EXECUTED
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import JobLookupError
from croniter import croniter

from gateway.daemon_thread import DaemonThread
from gateway.dto import ScheduleDTO, ScheduleSetpointDTO
from gateway.dto.schedule import BaseScheduleDTO
from gateway.events import GatewayEvent
from gateway.mappers import ScheduleMapper
from gateway.models import Database, DaySchedule, NoResultFound, Schedule
from gateway.pubsub import PubSub
from gateway.webservice import params_parser
from ioc import INJECTED, Inject, Injectable, Singleton
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from typing import Dict, Iterable, List, Optional, Tuple
    from apscheduler.job import Job
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
    def __init__(self, group_action_controller=INJECTED, pubsub=INJECTED, system_controller=INJECTED):
        # type: (GroupActionController, PubSub, SystemController) -> None
        self._group_action_controller = group_action_controller
        self._pubsub = pubsub
        self._web_interface = None  # type: Optional[WebInterface]
        self._sync_thread = None  # type: Optional[DaemonThread]
        self._schedules = {}  # type: Dict[int, ScheduleDTO]
        timezone = system_controller.get_timezone()
        self._scheduler = BackgroundScheduler(timezone=timezone, job_defaults={
            'coalesce': True,
            'misfire_grace_time': 3600  # 1h
        })
        # self._scheduler.add_listener(self._handle_job_executed, EVENT_JOB_EXECUTED)

    def set_webinterface(self, web_interface):
        # type: (WebInterface) -> None
        self._web_interface = web_interface

    def start(self):
        # type: () -> None
        self._scheduler.start()
        self._sync_thread = DaemonThread(name='schedulingsync',
                                         target=self._sync_configuration,
                                         interval=900,
                                         delay=300)
        self._sync_thread.start()

    def stop(self):
        # type: () -> None
        self._scheduler.shutdown()
        if self._sync_thread is not None:
            self._sync_thread.stop()

    def refresh_schedules(self):
        if self._sync_thread is not None:
            self._sync_thread.request_single_run()

    def _sync_configuration(self):
        # type: () -> None
        stale_schedules = {k: v for k, v in self._schedules.items()}
        with Database.get_session() as db:
            schedule_dtos = [ScheduleMapper(db).orm_to_dto(schedule) for schedule in
                             db.query(Schedule).filter_by(status='ACTIVE')]
        for schedule_dto in schedule_dtos:
            self._update_status(schedule_dto)
            if schedule_dto.status == 'ACTIVE':
                if self._schedules.get(schedule_dto.id) != schedule_dto:
                    self._submit_schedule(schedule_dto)
                    self._schedules[schedule_dto.id] = schedule_dto
                stale_schedules.pop(schedule_dto.id, None)
        for schedule_dto in stale_schedules.values():
            self._abort(schedule_dto)
            self._schedules.pop(schedule_dto.id, None)
        logger.debug('Scheduled jobs %s', self._scheduler.get_jobs())

    def _submit_schedule(self, schedule_dto):
        # type: (ScheduleDTO) -> None
        logger.debug('Submitting schedule %s', schedule_dto)
        kwargs = {'replace_existing': True,
                  'id': schedule_dto.job_id,
                  'args': (schedule_dto,),
                  'name': schedule_dto.name}

        if schedule_dto.repeat is None:
            run_date = datetime.fromtimestamp(schedule_dto.start)
            kwargs.update({'trigger': 'date', 'run_date': run_date})
        else:
            # TODO: parse
            minute, hour, day, month, day_of_week = schedule_dto.repeat.split(' ')
            end_date = datetime.fromtimestamp(schedule_dto.end) if schedule_dto.end else None
            start_date = datetime.fromtimestamp(schedule_dto.start) if schedule_dto.start else None
            kwargs.update({'trigger': 'cron', 'start_date': start_date, 'end_date': end_date,
                           'minute': minute, 'hour': hour, 'day': day, 'month': month, 'day_of_week': day_of_week})
        self._scheduler.add_job(self._execute_schedule, **kwargs)

    def _abort(self, base_dto):
        # type: (BaseScheduleDTO) -> None
        try:
            logger.debug('Removing schedule %s', base_dto)
            self._scheduler.remove_job(base_dto.job_id)
        except JobLookupError:
            pass

    def set_schedule_status(self, schedule_id, status):
        # type: (int, str) -> ScheduleDTO
        schedule_dto = self._schedules.get(schedule_id)
        with Database.get_session() as db:
            mapper = ScheduleMapper(db)
            if schedule_dto:
                schedule = mapper.dto_to_orm(schedule_dto)
            else:
                schedule = db.query(Schedule).filter_by(id=schedule_id).one()
            if schedule.status != 'COMPLETED':
                schedule.status = status
            schedule_dto = mapper.orm_to_dto(schedule)
            db.commit()
        self.refresh_schedules()
        return schedule_dto

    def load_schedule(self, schedule_id):
        # type: (int) -> ScheduleDTO
        schedule_dto = self._schedules.get(schedule_id)
        if schedule_dto is None:
            raise NoResultFound('Schedule {0} does not exist'.format(schedule_id))
        return schedule_dto

    def load_schedules(self):
        # type: () -> List[ScheduleDTO]
        schedules = []
        with Database.get_session() as db:
            mapper = ScheduleMapper(db)
            for schedule in db.query(Schedule):
                if schedule.id in self._schedules:
                    schedules.append(self._schedules[schedule.id])
                else:
                    schedules.append(mapper.orm_to_dto(schedule))
        return schedules

    def save_schedules(self, schedules):
        # type: (List[ScheduleDTO]) -> None
        with Database.get_session() as db:
            for schedule_dto in schedules:
                schedule = ScheduleMapper(db).dto_to_orm(schedule_dto)
                self._validate(schedule)
                db.add(schedule)
            db.commit()
        self.refresh_schedules()

    def remove_schedules(self, schedules):
        # type: (List[ScheduleDTO]) -> None
        with Database.get_session() as db:
            db.query(Schedule).where(Schedule.id.in_([s.id for s in schedules])).delete()
            db.commit()
        self.refresh_schedules()


    def _submit_setpoint(self, setpoint_dto):
        # type: (ScheduleSetpointDTO) -> None
        kwargs = {'replace_existing': True,
                  'id': setpoint_dto.job_id,
                  'args': (setpoint_dto,),
                  'name': 'Thermostat {0}'.format(setpoint_dto.thermostat),
                  'trigger': 'cron',
                  'minute': setpoint_dto.minute,
                  'hour': setpoint_dto.hour,
                  'day_of_week': setpoint_dto.weekday}
        self._scheduler.add_job(self._execute_setpoint, **kwargs)

    def _execute_setpoint(self, setpoint_dto):
        # type: (ScheduleSetpointDTO) -> None
        event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE,
                             {'id': setpoint_dto.thermostat,
                              'status': {'mode': setpoint_dto.mode,
                                         'current_setpoint': setpoint_dto.temperature}})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.SCHEDULER, event)
        logger.info('Thermostat %s: scheduled %s temperature=%s', setpoint_dto.thermostat, setpoint_dto.mode, setpoint_dto.temperature)

    def _execute_schedule(self, schedule_dto):
        # type: (ScheduleDTO) -> None
        logger.info('Executing schedule %s (%s)', schedule_dto.name, schedule_dto.action)
        if schedule_dto.running:
            return
        try:
            schedule_dto.running = True
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
            self._update_status(schedule_dto)
        except CommunicationTimedOutException as ex:
            logger.error('Got error while executing schedule: {0}'.format(ex))
        except Exception as ex:
            logger.error('Got error while executing schedule: {0}'.format(ex))
            schedule_dto.last_executed = time.time()
        finally:
            schedule_dto.running = False

    def _update_status(self, schedule_dto):
        # type: (ScheduleDTO) -> None
        if schedule_dto.has_ended:
            logger.debug('Completed schedule %s', schedule_dto.name)
            schedule_dto.next_execution = None
            schedule_dto.status = 'COMPLETED'
            with Database.get_session() as db:
                schedule = ScheduleMapper(db).dto_to_orm(schedule_dto)
                schedule.status = 'COMPLETED'
                db.add(schedule)
                db.commit()
        else:
            try:
                job = self._scheduler.get_job(schedule_dto.job_id)
                if job and hasattr(job, 'next_run_time') and job.next_run_time:
                    schedule_dto.next_execution = datetime_to_timestamp(job.next_run_time)
            except JobLookupError:
                pass

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



def datetime_to_timestamp(date):
    # type: (datetime) -> float
    return (date - datetime(1970, 1, 1, tzinfo=pytz.UTC)).total_seconds()
