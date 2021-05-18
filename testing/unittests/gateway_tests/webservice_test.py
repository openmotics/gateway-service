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
from gateway.dto import DimmerConfigurationDTO, LegacyScheduleDTO, \
    LegacyStartupActionDTO, ModuleDTO, OutputStatusDTO, ScheduleDTO, \
    SensorDTO, SensorSourceDTO, SensorStatusDTO, UserDTO, VentilationDTO, \
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
from gateway.scheduling_controller import SchedulingController
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
        self.maxDiff = None
        self.user_controller = mock.Mock(UserController)
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
                            user_controller=self.user_controller,
                            ventilation_controller=self.ventilation_controller,
                            module_controller=self.module_controller,
                            uart_controller=mock.Mock())
        self.web = WebInterface()

    def test_get_usernames(self):
        loaded_users = [
            UserDTO(
                id=1,
                username='test user_1',
                role='ADMIN',
                pin_code='1234',
                apartment=None,
                accepted_terms=1
            ),
            UserDTO(
                id=2,
                username='test user_2',
                role='USER',
                pin_code='',
                apartment=None,
                accepted_terms=1
            )
        ]
        with mock.patch.object(self.user_controller, 'load_users',
                               return_value=loaded_users):
            response = self.web.get_usernames()
            self.assertEqual(
                {'usernames': ['test user_1', 'test user_2'], 'success': True},
                json.loads(response)
            )

    def test_create_user(self):
        to_save_user = UserDTO(
            username='test',
            role='ADMIN',
            pin_code=None
        )
        to_save_user.set_password('test')
        with mock.patch.object(self.user_controller, 'save_user') as save_user_func:
            response = self.web.create_user(username='test', password='test')
            save_user_func.assert_called_once_with(to_save_user)
            self.assertEqual(
                {'success': True},
                json.loads(response)
            )

    def test_remove_user(self):
        to_remove_user = UserDTO(
            username='test',
        )
        with mock.patch.object(self.user_controller, 'remove_user') as remove_user_func:
            response = self.web.remove_user(username='test')
            remove_user_func.assert_called_once_with(to_remove_user)
            self.assertEqual(
                {'success': True},
                json.loads(response)
            )

    def test_output_status(self):
        with mock.patch.object(self.output_controller, 'get_output_statuses',
                               return_value=[OutputStatusDTO(id=0, status=True)]):
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

    def test_sensor_configurations(self):
        sensor_dto = SensorDTO(id=2,
                               source=SensorSourceDTO('master'),
                               external_id='0',
                               physical_quantity='temperature',
                               unit='celcius',
                               name='foo')
        with mock.patch.object(self.sensor_controller, 'load_sensors',
                               return_value=[sensor_dto]):
            response = self.web.get_sensor_configurations()
            self.assertEqual([{
                'id': 2,
                'source': {'type': 'master', 'name': None},
                'external_id': '0',
                'physical_quantity': 'temperature',
                'unit': 'celcius',
                'name': 'foo',
                'room': 255,
                'offset': 0,
                'virtual': False,
            }], json.loads(response)['config'])

    def test_set_sensor_configurations(self):
        with mock.patch.object(self.sensor_controller, 'save_sensors',
                               return_value=None) as save:
            config = {'id': 2,
                      'name': 'foo',
                      'room': 255,
                      'offset': 0,
                      'virtual': False}
            self.web.set_sensor_configuration(config=config)
            save.assert_called()

    def test_sensor_status(self):
        status_dto = SensorStatusDTO(id=2, value=21.0)
        with mock.patch.object(self.sensor_controller, 'get_sensors_status',
                               return_value=[status_dto]):
            response = self.web.get_sensor_status()
            self.assertEqual([{
                'id': 2,
                'value': 21.0,
            }], json.loads(response)['status'])

    def test_set_sensor_status(self):
        with mock.patch.object(self.sensor_controller, 'set_sensor_status',
                               side_effect=lambda x: x) as set_status:
            status = {'id': 2,
                      'value': 21.0}
            self.web.set_sensor_status(status=status)
            set_status.assert_called()

    def test_get_sensors_temperature(self):
        with mock.patch.object(self.sensor_controller, 'get_temperature_status',
                               return_value=[None, None, 21.0]):
            response = self.web.get_sensor_temperature_status()
            expected_status = [
                None, None, 21.0
            ]
            self.assertEqual(expected_status, json.loads(response)['status'])

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
                               return_value=None) as save:
            config = {'id': 1,
                      'source': {'type': 'plugin', 'name': 'dummy'},
                      'external_id': 'device-00001',
                      'name': 'test',
                      'device': {'vendor': 'example',
                                 'type': '0A',
                                 'serial': 'device-00001'}}
            response = self.web.set_ventilation_configuration(config=config)
            self.assertEqual({
                'id': 1,
                'amount_of_levels': 0,
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
                'connected': True,
                'mode': 'manual',
                'level': 2,
                'remaining_time': 60.0,
                'timer': None
            }, json.loads(response)['status'])
            set_status.assert_called()

    def test_set_all_lights_off(self):
        with mock.patch.object(self.output_controller, 'set_all_lights',
                               return_value={}) as set_status:
            self.web.set_all_lights_off()
            set_status.assert_called_with(action='OFF')

            floor_expectations = [(255, None), (2, 2), (0, 0)]
            for expectation in floor_expectations:
                self.web.set_all_lights_floor_off(floor=expectation[0])
                set_status.assert_called_with(action='OFF', floor_id=expectation[1])

    def test_set_all_lights_on(self):
        expectations = [(255, None), (2, 2), (0, 0)]
        with mock.patch.object(self.output_controller, 'set_all_lights',
                               return_value={}) as set_status:
            for expectation in expectations:
                self.web.set_all_lights_floor_on(floor=expectation[0])
                set_status.assert_called_with(action='ON', floor_id=expectation[1])

    def test_get_modules_information(self):
        master_modules = [ModuleDTO(source=ModuleDTO.Source.MASTER,
                                    module_type=ModuleDTO.ModuleType.OUTPUT,
                                    address='079.000.000.001',
                                    hardware_type=ModuleDTO.HardwareType.INTERNAL,
                                    firmware_version='3.1.0',
                                    hardware_version='4',
                                    order=0,
                                    online=True)]
        energy_modules = [ModuleDTO(source=ModuleDTO.Source.GATEWAY,
                                    module_type=ModuleDTO.ModuleType.ENERGY,
                                    address='2',
                                    hardware_type=ModuleDTO.HardwareType.PHYSICAL,
                                    firmware_version='1.2.3',
                                    order=0)]
        with mock.patch.object(self.module_controller, 'load_master_modules', return_value=master_modules) as load_master_modules, \
                mock.patch.object(self.module_controller, 'load_energy_modules', return_value=energy_modules) as load_energy_modules:
            api_response = json.loads(self.web.get_modules_information())
            load_master_modules.assert_called()
            load_energy_modules.assert_called()
            self.assertDictEqual(api_response, {"modules": {"energy": {'2': {'address': '2',
                                                                             'firmware': '1.2.3',
                                                                             'id': 0,
                                                                             'type': 'E'}},
                                                            "master": {"079.000.000.001": {"category": "OUTPUT",
                                                                                           "is_can": False,
                                                                                           "hardware_type": "internal",
                                                                                           "module_nr": 0,
                                                                                           "is_virtual": False,
                                                                                           "address": "079.000.000.001",
                                                                                           "type": "O"}}},
                                                "success": True})

    def test_scheduled_action_configurations(self):
        dtos = [LegacyScheduleDTO(id=0, hour=1, day=2, minute=3, action=[4, 5])]
        with mock.patch.object(self.scheduling_controller, 'load_scheduled_actions', return_value=dtos) as load_scheduled_actions:
            api_response = json.loads(self.web.get_scheduled_action_configurations())
            load_scheduled_actions.assert_called()
            self.assertEqual({'success': True,
                              'config': [{'id': 0, 'hour': 1, 'day': 2, 'minute': 3, 'action': '4,5'}]}, api_response)
        config = [{'id': 5, 'hour': 4, 'day': 3, 'minute': 2, 'action': '1,0'}]
        with mock.patch.object(self.scheduling_controller, 'save_scheduled_actions') as save_scheduled_actions:
            api_response = json.loads(self.web.set_scheduled_action_configurations(config=config))
            self.assertEqual({'success': True}, api_response)
            save_scheduled_actions.assert_called_with([LegacyScheduleDTO(id=5, hour=4, day=3, minute=2, action=[1, 0])])

    def test_startup_action_configuration(self):
        dto = LegacyStartupActionDTO(actions=[0, 1, 2, 3])
        with mock.patch.object(self.scheduling_controller, 'load_startup_action', return_value=dto) as load_startup_action:
            api_response = json.loads(self.web.get_startup_action_configuration())
            load_startup_action.assert_called()
            self.assertEqual({'success': True,
                              'config': {'actions': '0,1,2,3'}}, api_response)
        config = {'actions': '3,2,1,0'}
        with mock.patch.object(self.scheduling_controller, 'save_startup_action') as save_startup_action:
            api_response = json.loads(self.web.set_startup_action_configuration(config=config))
            self.assertEqual({'success': True}, api_response)
            save_startup_action.assert_called_with(LegacyStartupActionDTO(actions=[3, 2, 1, 0]))

    def test_dimmer_configuration(self):
        dto = DimmerConfigurationDTO(min_dim_level=0, dim_memory=1, dim_step=2)
        with mock.patch.object(self.output_controller, 'load_dimmer_configuration', return_value=dto) as load_dimmer_configuration:
            api_response = json.loads(self.web.get_dimmer_configuration())
            load_dimmer_configuration.assert_called()
            self.assertEqual({'success': True,
                              'config': {'min_dim_level': 0, 'dim_memory': 1, 'dim_step': 2, 'dim_wait_cycle': 255}}, api_response)
        config = {'min_dim_level': 255, 'dim_memory': 2, 'dim_step': 1, 'dim_wait_cycle': 0}
        with mock.patch.object(self.output_controller, 'save_dimmer_configuration') as save_dimmer_configuration:
            api_response = json.loads(self.web.set_dimmer_configuration(config=config))
            self.assertEqual({'success': True}, api_response)
            save_dimmer_configuration.assert_called_with(DimmerConfigurationDTO(dim_memory=2, dim_step=1, dim_wait_cycle=0))
