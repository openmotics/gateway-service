# Copyright (C) 2020 OpenMotics BV
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
from __future__ import absolute_import

import json
import unittest

import mock

from bus.om_bus_client import MessageClient
from gateway.dto import OutputStateDTO, ScheduleDTO, VentilationDTO, \
    VentilationSourceDTO, VentilationStatusDTO
from gateway.gateway_api import GatewayApi
from gateway.group_action_controller import GroupActionController
from gateway.hal.frontpanel_controller import FrontpanelController
from gateway.input_controller import InputController
from gateway.maintenance_controller import MaintenanceController
from gateway.module_controller import ModuleController
from gateway.output_controller import OutputController
from gateway.pulse_counter_controller import PulseCounterController
from gateway.room_controller import RoomController
from gateway.scheduling import SchedulingController
from gateway.sensor_controller import SensorController
from gateway.shutter_controller import ShutterController
from gateway.thermostat.thermostat_controller import ThermostatController
from gateway.user_controller import UserController
from gateway.ventilation_controller import VentilationController
from gateway.webservice import WebInterface
from ioc import SetTestMode, SetUpTestInjections


class WebInterfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.output_controller = mock.Mock(OutputController)
        self.scheduling_controller = mock.Mock(SchedulingController)
        self.ventilation_controller = mock.Mock(VentilationController)
        self.gateway_api = mock.Mock(GatewayApi)
        SetUpTestInjections(frontpanel_controller=mock.Mock(FrontpanelController),
                            gateway_api=self.gateway_api,
                            group_action_controller=mock.Mock(GroupActionController),
                            input_controller=mock.Mock(InputController),
                            maintenance_controller=mock.Mock(MaintenanceController),
                            message_client=mock.Mock(MessageClient),
                            output_controller=self.output_controller,
                            pulse_counter_controller=mock.Mock(PulseCounterController),
                            room_controller =mock.Mock(RoomController),
                            scheduling_controller=self.scheduling_controller,
                            sensor_controller=mock.Mock(SensorController),
                            shutter_controller=mock.Mock(ShutterController),
                            thermostat_controller=mock.Mock(ThermostatController),
                            user_controller=mock.Mock(UserController),
                            ventilation_controller=self.ventilation_controller,
                            module_controller=mock.Mock(ModuleController))
        self.web = WebInterface()

    def test_output_status(self):
        with mock.patch.object(self.output_controller, 'get_output_statuses',
                               return_value=[OutputStateDTO(id=0, status=True)]):
            response = self.web.get_output_status()
            self.assertEqual([{'id': 0, 'status': 1, 'ctimer': 0, 'dimmer': 0, 'locked': False}], json.loads(response)['status'])

    def test_schedules(self):
        with mock.patch.object(self.scheduling_controller, 'load_schedules',
                               return_value=[ScheduleDTO(id=1, name='test', start=0, action='BASIC_ACTION')]):
            response = self.web.list_schedules()
            self.assertEqual([{'arguments': None,
                               'duration': None,
                               'end': None,
                               'id': 1,
                               'last_executed': None,
                               'name': 'test',
                               'next_execution': None,
                               'repeat': None,
                               'schedule_type': 'BASIC_ACTION',
                               'start': 0,
                               'status': None}], json.loads(response)['schedules'])

    def test_ventilation_configurations(self):
        with mock.patch.object(self.ventilation_controller, 'load_ventilations',
                               return_value=[VentilationDTO(id=1, name='test', amount_of_levels=4,
                                                            device_vendor='example',
                                                            device_type='0A',
                                                            device_serial='device-00001',
                                                            external_id='device-00001',
                                                            source=VentilationSourceDTO(id=2, type='plugin', name='dummy'))]):
            response = self.web.get_ventilation_configurations()
            self.assertEqual([{
                'id': 1,
                'name': 'test',
                'amount_of_levels': 4,
                'external_id': 'device-00001',
                'source': {'type': 'plugin', 'name': 'dummy'},
                'device': {'vendor': 'example',
                           'type': '0A',
                           'serial': 'device-00001'}
            }], json.loads(response)['config'])

    def test_set_ventilation_configuration(self):
        with mock.patch.object(self.ventilation_controller, 'save_ventilation',
                               return_value=VentilationDTO(id=1, name='test', amount_of_levels=4,
                                                           device_vendor='example',
                                                           device_type='0A',
                                                           device_serial='device-00001',
                                                           external_id='device-00001',
                                                           source=VentilationSourceDTO(id=2, type='plugin', name='dummy'))) as save:
            config = {'source': {'type': 'plugin', 'name': 'dummy'},
                      'external_id': 'device-00001',
                      'name': 'test',
                      'device': {'vendor': 'example',
                                 'type': '0A',
                                 'serial': 'device-00001'}}
            response = self.web.set_ventilation_configuration(config=config)
            self.assertEqual({
                'id': 1,
                'source': {'type': 'plugin', 'name': 'dummy'},
                'external_id': 'device-00001',
                'name': 'test',
                'device': {'vendor': 'example',
                           'type': '0A',
                           'serial': 'device-00001'},
            }, json.loads(response)['config'])
            save.assert_called()

    def test_set_ventilation_status(self):
        with mock.patch.object(self.ventilation_controller, 'set_status',
                               return_value=VentilationStatusDTO(id=1,
                                                                 mode='manual',
                                                                 level=2,
                                                                 remaining_time=60.0)) as set_status:
            status = {'id': 1, 'mode': 'manual', 'level': 2, 'remaining_time': 60.0}
            response = self.web.set_ventilation_status(status=status)
            self.assertEqual({
                'id': 1,
                'mode': 'manual',
                'level': 2,
                'remaining_time': 60.0
            }, json.loads(response)['status'])
            set_status.assert_called()
