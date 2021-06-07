# Copyright (C) 2021 OpenMotics BV
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
basic authentication for v0 api
"""
import time

import cherrypy
import mock
import ujson as json


from bus.om_bus_client import MessageClient
from gateway.dto import DimmerConfigurationDTO, LegacyScheduleDTO, \
    LegacyStartupActionDTO, ModuleDTO, OutputStatusDTO, ScheduleDTO, \
    SensorDTO, SensorSourceDTO, SensorStatusDTO, UserDTO, VentilationDTO, \
    VentilationSourceDTO, VentilationStatusDTO
from gateway.exceptions import *
from gateway.authentication_controller import AuthenticationToken
from gateway.gateway_api import GatewayApi
from gateway.group_action_controller import GroupActionController
from gateway.hal.frontpanel_controller import FrontpanelController
from gateway.input_controller import InputController
from gateway.maintenance_controller import MaintenanceController
from gateway.module_controller import ModuleController
from gateway.output_controller import OutputController
from gateway.pulse_counter_controller import PulseCounterController
from gateway.room_controller import RoomController
from gateway.scheduling_controller import SchedulingController
from gateway.sensor_controller import SensorController
from gateway.shutter_controller import ShutterController
from gateway.thermostat.thermostat_controller import ThermostatController
from gateway.user_controller import UserController
from gateway.ventilation_controller import VentilationController
from gateway.webservice import WebInterface
from ioc import SetTestMode, SetUpTestInjections

from ..V1.base import BaseCherryPyUnitTester

if False:  # MyPy
    from typing import Optional, Dict
    from gateway.dto import UserDTO


class v0AuthenticationTest(BaseCherryPyUnitTester):
    def setUp(self):
        super(v0AuthenticationTest, self).setUp()
        self.maxDiff = None
        self.output_controller = mock.Mock(OutputController)
        self.scheduling_controller = mock.Mock(SchedulingController)
        self.sensor_controller = mock.Mock(SensorController)
        self.ventilation_controller = mock.Mock(VentilationController)
        self.gateway_api = mock.Mock(GatewayApi)
        self.module_controller = mock.Mock(ModuleController)
        SetUpTestInjections(frontpanel_controller=mock.Mock(FrontpanelController),
                            gateway_api=self.gateway_api,
                            group_action_controller=mock.Mock(GroupActionController),
                            input_controller=mock.Mock(InputController),
                            maintenance_controller=mock.Mock(MaintenanceController),
                            message_client=mock.Mock(MessageClient),
                            output_controller=self.output_controller,
                            pulse_counter_controller=mock.Mock(PulseCounterController),
                            room_controller=mock.Mock(RoomController),
                            scheduling_controller=self.scheduling_controller,
                            sensor_controller=self.sensor_controller,
                            shutter_controller=mock.Mock(ShutterController),
                            system_controller=mock.Mock(),
                            thermostat_controller=mock.Mock(ThermostatController),
                            user_controller=self.users_controller,
                            ventilation_controller=self.ventilation_controller,
                            module_controller=self.module_controller,
                            uart_controller=mock.Mock())
        self.web = WebInterface()

        config = {'/': {'tools.cors.on': False,
                        'tools.sessions.on': False}}

        cherrypy.tree.mount(root=self.web, config=config)

        self.test_admin = UserDTO(
            id=30,
            username='admin_1',
            role='ADMIN'
        )

        self.test_technician_1 = UserDTO(
            id=40,
            username='user_1',
            role='TECHNICIAN'
        )
        self.test_technician_1.set_password('test')

        self.test_user_1 = UserDTO(
            id=50,
            username='user_1',
            role='USER'
        )
        self.test_user_1.set_password('test')

        self.test_courier_1 = UserDTO(
            id=60,
            username='user_1',
            role='COURIER'
        )
        self.test_courier_1.set_password('test')


    def test_authentication_admin_only(self):
        status, headers, response = self.GET('/get_version')
        self.assertStatus('401 Unauthorized')

        auth_token = AuthenticationToken(self.test_admin, 'test-token-admin', int(time.time()) + 3600)
        with mock.patch.object(self.users_controller, 'login', return_value=(True, auth_token)):
            status, headers, response = self.GET('/login?username=test&password=test')
            self.assertStatus('200 OK')

        status, headers, response = self.GET('/get_version', login_user=self.test_admin)
        self.assertStatus('200 OK')

        status, headers, response = self.GET('/get_version', login_user=self.test_user_1)
        self.assertStatus('401 Unauthorized')

        status, headers, response = self.GET('/get_version', login_user=self.test_courier_1)
        self.assertStatus('401 Unauthorized')

        status, headers, response = self.GET('/get_version', login_user=self.test_technician_1)
        self.assertStatus('401 Unauthorized')
