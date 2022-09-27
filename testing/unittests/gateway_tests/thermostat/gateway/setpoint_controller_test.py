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

class SetpointControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(SetpointControllerTest, cls).setUpClass()
        SetTestMode()
        Logs.set_loglevel(logging.DEBUG, namespace='gateway.setpoint_controller')
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


    def test_update_thermostat_setpoints(self):
        self.setpoint_controller.update_thermostat_setpoints(0, 'heating', [
            DaySchedule(id=10, index=0, content='{"21600": 21.5}')
        ])
        jobs = self.scheduling_controller._scheduler.get_jobs()
        assert len(self.scheduler.add_job.call_args_list) == 1
        job_id = self.scheduler.add_job.call_args_list[0][1]['id']
        assert job_id == 'thermostat.heating.0.mon.06h00m'
        setpoint_dto = self.scheduler.add_job.call_args_list[0][1]['args'][0]
        assert setpoint_dto.thermostat == 0
        assert setpoint_dto.temperature == 21.5

        self.setpoint_controller.update_thermostat_setpoints(0, 'heating', [
            DaySchedule(id=10, index=0, content='{"28800": 22.0}')
        ])
        assert len(self.scheduler.add_job.call_args_list) == 2
        job_id = self.scheduler.add_job.call_args_list[1][1]['id']
        assert job_id == 'thermostat.heating.0.mon.08h00m'
        setpoint_dto = self.scheduler.add_job.call_args_list[1][1]['args'][0]
        assert setpoint_dto.thermostat == 0
        assert setpoint_dto.temperature == 22.0