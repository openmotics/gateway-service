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
from gateway.api.serializers import SensorSerializer
from gateway.dto import DimmerConfigurationDTO, EnergyModuleDTO, \
    LegacyScheduleDTO, LegacyStartupActionDTO, ModuleDTO, OutputStatusDTO, \
    ScheduleDTO, SensorDTO, SensorSourceDTO, SensorStatusDTO, ThermostatDTO, \
    ThermostatGroupDTO, ThermostatStatusDTO, UserDTO, VentilationDTO, \
    VentilationSourceDTO, VentilationStatusDTO, PumpGroupDTO
from gateway.energy_module_controller import EnergyModuleController
from gateway.enums import HardwareType, ModuleType
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
        self.thermostat_controller = mock.Mock(ThermostatController)
        self.ventilation_controller = mock.Mock(VentilationController)
        self.module_controller = mock.Mock(ModuleController)
        self.energy_module_controller = mock.Mock(EnergyModuleController)
        SetUpTestInjections(frontpanel_controller=mock.Mock(FrontpanelController),
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
                            thermostat_controller=self.thermostat_controller,
                            user_controller=self.user_controller,
                            ventilation_controller=self.ventilation_controller,
                            module_controller=self.module_controller,
                            energy_module_controller=self.energy_module_controller,
                            uart_controller=mock.Mock(),
                            rebus_controller=None)
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
            role='SUPER',
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

    def test_set_sensor_configuration(self):
        config = {'id': 2,
                  'name': 'foo',
                  'room': 255,
                  'offset': 0,
                  'virtual': False}
        sensor_dto = SensorSerializer.deserialize(config)
        expected_response = [SensorSerializer.serialize(sensor_dto, fields=None)]
        with mock.patch.object(self.sensor_controller, 'save_sensors',
                               return_value=[sensor_dto]) as save:
            response = self.web.set_sensor_configuration(config=config)
            self.assertEqual(expected_response, json.loads(response)['config'])
            save.assert_called()

    def test_set_sensor_configurations(self):
        config = [{'id': 2, 'name': 'foo', 'room': 255, 'offset': 0, 'virtual': False},
                  {'id': 3, 'name': 'foo2', 'room': 255, 'offset': 0, 'virtual': False}]
        sensor_dtos = [SensorSerializer.deserialize(el) for el in config]
        expected_response = [SensorSerializer.serialize(sensor_dto, fields=None) for sensor_dto in sensor_dtos]
        with mock.patch.object(self.sensor_controller, 'save_sensors',
                               return_value=sensor_dtos) as save:
            response = self.web.set_sensor_configurations(config=config)
            self.assertEqual(expected_response, json.loads(response)['config'])
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

    def test_get_global_thermostat_configuration(self):
        with mock.patch.object(self.thermostat_controller, 'load_thermostat_group',
                               return_value=ThermostatGroupDTO(0,
                                                               pump_delay=120,
                                                               switch_to_heating_0=(8, 100),
                                                               switch_to_cooling_0=(9, 0))):
            response = self.web.get_global_thermostat_configuration()
            self.assertEqual({
                'pump_delay': 120,
                'switch_to_heating_output_0': 8,
                'switch_to_heating_output_1': 255,
                'switch_to_heating_output_2': 255,
                'switch_to_heating_output_3': 255,
                'switch_to_heating_value_0': 100,
                'switch_to_heating_value_1': 255,
                'switch_to_heating_value_2': 255,
                'switch_to_heating_value_3': 255,
                'switch_to_cooling_output_0': 9,
                'switch_to_cooling_output_1': 255,
                'switch_to_cooling_output_2': 255,
                'switch_to_cooling_output_3': 255,
                'switch_to_cooling_value_0': 0,
                'switch_to_cooling_value_1': 255,
                'switch_to_cooling_value_2': 255,
                'switch_to_cooling_value_3': 255,
            }, json.loads(response)['config'])

    def test_set_global_thermostat_configuration(self):
        with mock.patch.object(self.thermostat_controller, 'save_thermostat_groups',
                               return_value=None) as save:
            config = {
                'id': 0,
                'name': 'Foo',
                'pump_delay': 120,
                'switch_to_heating_output_0': 8,
                'switch_to_heating_value_0': 100,
                'switch_to_cooling_output_0': 255,
                'switch_to_cooling_value_0': 255,
            }
            self.web.set_global_thermostat_configuration(config=config)
            save.assert_called_with([
                ThermostatGroupDTO(id=0,
                                   name='Foo',
                                   pump_delay=120,
                                   switch_to_heating_0=[8, 100],
                                   switch_to_cooling_0=None)
            ])

    def test_get_pump_group_configurations(self):
        with mock.patch.object(self.thermostat_controller, 'load_heating_pump_groups',
                               return_value=[PumpGroupDTO(0,
                                                          pump_output_id=1,
                                                          valve_output_ids=[8, 9, 10])]):
            response = self.web.get_pump_group_configurations()
            self.assertIn({
                'id': 0,
                'output': 1,
                'outputs': '8,9,10',
                'room': 255
            }, json.loads(response)['config'])
            self.assertIn({
                'id': 1,
                'output': 255,
                'outputs': '',
                'room': 255
            }, json.loads(response)['config'])
            self.assertEqual(len(json.loads(response)['config']), 8)

    def test_set_pump_group_configurations(self):
        with mock.patch.object(self.thermostat_controller, 'save_heating_pump_groups',
                               return_value=None) as save:
            response = self.web.set_pump_group_configurations([
                {'id': 0,
                 'output': 1,
                 'outputs': '8,9,10'},
                {'id': 1,
                 'output': 255,
                 'outputs': ''}
            ])
            save.assert_called_with([
                PumpGroupDTO(0, pump_output_id=1, valve_output_ids=[8, 9, 10]),
                PumpGroupDTO(0, pump_output_id=None, valve_output_ids=[])
            ])

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
            set_status.reset_mock()

            floor_expectations = [(255, None), (2, 'Unsupported'), (0, 'Unsupported')]
            for expectation in floor_expectations:
                response = json.loads(self.web.set_all_lights_floor_off(floor=expectation[0]))
                if expectation[1] is None:
                    self.assertTrue(response.get('success'))
                    set_status.assert_called_with(action='OFF')
                else:
                    self.assertFalse(response.get('success'))
                    self.assertEqual(expectation[1], response['msg'])
                    set_status.assert_not_called()
                set_status.reset_mock()

    def test_set_all_lights_on(self):
        expectations = [(255, None), (2, 'Unsupported'), (0, 'Unsupported')]
        with mock.patch.object(self.output_controller, 'set_all_lights',
                               return_value={}) as set_status:
            for expectation in expectations:
                response = json.loads(self.web.set_all_lights_floor_on(floor=expectation[0]))
                if expectation[1] is None:
                    set_status.assert_called_with(action='ON')
                else:
                    self.assertFalse(response.get('success'))
                    self.assertEqual(expectation[1], response['msg'])
                    set_status.assert_not_called()
                set_status.reset_mock()

    def test_get_modules_information(self):
        master_modules = [ModuleDTO(source=ModuleDTO.Source.MASTER,
                                    module_type=ModuleType.OUTPUT,
                                    address='079.000.000.001',
                                    hardware_type=HardwareType.INTERNAL,
                                    firmware_version='3.1.0',
                                    hardware_version='4',
                                    order=0,
                                    online=True)]
        energy_modules = [ModuleDTO(source=ModuleDTO.Source.GATEWAY,
                                    module_type=ModuleType.ENERGY,
                                    address='2',
                                    hardware_type=HardwareType.PHYSICAL,
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

    def test_set_power_modules(self):
        with mock.patch.object(self.energy_module_controller, 'save_modules') as save_modules:
            api_response = json.loads(self.web.set_power_modules(modules=[{'id': 2, 'version': 12, 'name': '',
                                                                           'input0': 'test', 'input1': '', 'input2': '', 'input3': '', 'input4': '', 'input5': '', 'input6': '', 'input7': '', 'input8': '', 'input9': '', 'input10': '', 'input11': '',
                                                                           'inverted0': 0, 'inverted1': False, 'inverted2': False, 'inverted3': False, 'inverted4': False, 'inverted5': False, 'inverted6': False, 'inverted7': False, 'inverted8': False, 'inverted9': False, 'inverted10': False, 'inverted11': False,
                                                                           'sensor0': 3, 'sensor1': 2, 'sensor2': 2, 'sensor3': 3, 'sensor4': 2, 'sensor5': 2, 'sensor6': 2, 'sensor7': 2, 'sensor8': 2, 'sensor9': 2, 'sensor10': 2, 'sensor11': 2,
                                                                           'times0': '', 'times1': '', 'times2': '', 'times3': '', 'times4': '', 'times5': '', 'times6': '', 'times7': '', 'times8': '', 'times9': '', 'times10': '', 'times11': ''}]))
            self.assertEqual({'success': True}, api_response)
            extra_kwargs = {}
            for i in range(12):
                extra_kwargs.update({'input{0}'.format(i): '',
                                     'inverted{0}'.format(i): False,
                                     'sensor{0}'.format(i): 2,
                                     'times{0}'.format(i): ''})
            extra_kwargs.update({'input0': 'test',
                                 'inverted0': 0,
                                 'sensor0': 3, 'sensor3': 3})
            save_modules.assert_called_once_with([EnergyModuleDTO(id=2, version=12, name='', address=None,
                                                                  **extra_kwargs)])
        with mock.patch.object(self.energy_module_controller, 'load_modules') as load_modules:
            extra_kwargs.update({'input0': 'foobar',
                                 'inverted0': True,
                                 'sensor0': 4})
            load_modules.side_effect = [[EnergyModuleDTO(id=2, version=12, name='bar', address=32,
                                                         **extra_kwargs)]]
            api_response = json.loads(self.web.get_power_modules())
            self.assertEqual({'success': True,
                              'modules': [{'id': 2, 'version': 12, 'name': 'bar', 'address': 'E32',
                                           'input0': 'foobar', 'input1': '', 'input2': '', 'input3': '', 'input4': '', 'input5': '', 'input6': '', 'input7': '', 'input8': '', 'input9': '', 'input10': '', 'input11': '',
                                           'inverted0': True, 'inverted1': False, 'inverted2': False, 'inverted3': False, 'inverted4': False, 'inverted5': False, 'inverted6': False, 'inverted7': False, 'inverted8': False, 'inverted9': False, 'inverted10': False, 'inverted11': False,
                                           'sensor0': 4, 'sensor1': 2, 'sensor2': 2, 'sensor3': 3, 'sensor4': 2, 'sensor5': 2, 'sensor6': 2, 'sensor7': 2, 'sensor8': 2, 'sensor9': 2, 'sensor10': 2, 'sensor11': 2,
                                           'times0': '', 'times1': '', 'times2': '', 'times3': '', 'times4': '', 'times5': '', 'times6': '', 'times7': '', 'times8': '', 'times9': '', 'times10': '', 'times11': ''}]}, api_response)
