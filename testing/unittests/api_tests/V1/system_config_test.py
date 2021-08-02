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
System configuration API tests
"""
from __future__ import absolute_import

import cherrypy
import ujson as json
import unittest

import mock

from gateway.authentication_controller import AuthenticationController
from gateway.api.serializers import SystemDoorbellConfigSerializer, SystemRFIDConfigSerializer, \
    SystemRFIDSectorBlockConfigSerializer, SystemGlobalConfigSerializer, SystemActivateUserConfigSerializer
from gateway.dto import SystemDoorbellConfigDTO, SystemRFIDConfigDTO, SystemRFIDSectorBlockConfigDTO, \
    SystemGlobalConfigDTO, SystemActivateUserConfigDTO, UserDTO
from gateway.user_controller import UserController
from gateway.system_config_controller import SystemConfigController
from gateway.api.V1.system_config import SystemConfiguration

from ioc import SetTestMode, SetUpTestInjections

from .base import BaseCherryPyUnitTester


class ApiSystemConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.authentication_controller = mock.Mock(AuthenticationController)
        SetUpTestInjections(authentication_controller=self.authentication_controller)
        self.user_controller = mock.Mock(UserController)
        self.system_config_controller = mock.Mock(SystemConfigController)
        SetUpTestInjections(system_config_controller=self.system_config_controller, user_controller=self.user_controller)
        self.web = SystemConfiguration()

        self.doorbell_config = SystemDoorbellConfigDTO(enabled=True)
        self.rfid_config = SystemRFIDConfigDTO(enabled=True, security_enabled=False, max_tags=4)
        self.rfid_sector_block_config = SystemRFIDSectorBlockConfigDTO(rfid_sector_block=37)
        self.global_config = SystemGlobalConfigDTO(
            device_name='TEST',
            country='EN',
            postal_code='1234',
            city='TEST',
            street='street',
            house_number='123',
            language='EN'
        )
        self.activate_user_config = SystemActivateUserConfigDTO(change_first_name=True, change_last_name=False,
                                                                change_language=True, change_pin_code=False)

    def test_doorbell_config_api(self):
        with mock.patch.object(self.system_config_controller, 'get_doorbell_config', return_value=self.doorbell_config), \
                mock.patch.object(self.system_config_controller, 'save_doorbell_config') as save_config_func:
            resp = self.web.get_doorbell_config()
            doorbell_config_recv = SystemDoorbellConfigSerializer.deserialize(json.loads(resp))
            self.assertEqual(self.doorbell_config, doorbell_config_recv)

            serial_config = {
                'enabled': False
            }
            self.web.put_doorbell_config(request_body=serial_config)
            save_config_func.assert_called_once_with(SystemDoorbellConfigSerializer.deserialize(serial_config))

    def test_rfid_config_api(self):
        with mock.patch.object(self.system_config_controller, 'get_rfid_config', return_value=self.rfid_config), \
                mock.patch.object(self.system_config_controller, 'save_rfid_config') as save_config_func:
            resp = self.web.get_rfid_config()
            rfid_config_recv = SystemRFIDConfigSerializer.deserialize(json.loads(resp))
            self.assertEqual(self.rfid_config, rfid_config_recv)

            serial_config = {
                'enabled': False,
                'security_enabled': True,
                'max_tags': 37
            }
            self.web.put_rfid_config(request_body=serial_config)
            save_config_func.assert_called_once_with(SystemRFIDConfigSerializer.deserialize(serial_config))

    def test_rfid_sector_block_config_api(self):
        with mock.patch.object(self.system_config_controller, 'get_rfid_sector_block_config', return_value=self.rfid_sector_block_config), \
                mock.patch.object(self.system_config_controller, 'save_rfid_sector_block_config') as save_config_func:
            resp = self.web.get_rfid_sector_block_config()
            rfid_sector_block_config_recv = SystemRFIDSectorBlockConfigSerializer.deserialize(json.loads(resp))
            self.assertEqual(self.rfid_sector_block_config, rfid_sector_block_config_recv)

            serial_config = {
                'rfid_sector_block': 37,
            }
            self.web.put_rfid_sector_block_config(request_body=serial_config)
            save_config_func.assert_called_once_with(SystemRFIDSectorBlockConfigSerializer.deserialize(serial_config))
            
    def test_global_config_api(self):
        with mock.patch.object(self.system_config_controller, 'get_global_config', return_value=self.global_config), \
                mock.patch.object(self.system_config_controller, 'save_global_config') as save_config_func:
            resp = self.web.get_global_config()
            global_config_recv = SystemGlobalConfigSerializer.deserialize(json.loads(resp))
            self.assertEqual(self.global_config, global_config_recv)

            serial_config = {
                'city': 'test',
                'country': 'NL',
                'postal_code': '8790',
                'language': 'Nederlands'
            }
            self.web.put_global_config(request_body=serial_config)
            save_config_func.assert_called_once_with(SystemGlobalConfigSerializer.deserialize(serial_config))
            
    def test_user_activate_config_api(self):
        with mock.patch.object(self.system_config_controller, 'get_activate_user_config', return_value=self.activate_user_config), \
                mock.patch.object(self.system_config_controller, 'save_activate_user_config') as save_config_func:
            resp = self.web.get_activate_user_config()
            activate_user_config_recv = SystemActivateUserConfigSerializer.deserialize(json.loads(resp))
            self.assertEqual(self.activate_user_config, activate_user_config_recv)

            serial_config = {
                'change_first_name_enabled': True,
                'change_last_name_enabled': False,
                'change_language_enabled': False,
                'change_user_code_enabled': True
            }
            self.web.put_activate_user_config(request_body=serial_config)
            save_config_func.assert_called_once_with(SystemActivateUserConfigSerializer.deserialize(serial_config))


class SystemConfigApiCherryPyTest(BaseCherryPyUnitTester):
    def setUp(self):
        super(SystemConfigApiCherryPyTest, self).setUp()
        self.system_config_controller = mock.Mock(SystemConfigController)
        SetUpTestInjections(system_config_controller=self.system_config_controller)
        self.web = SystemConfiguration()
        cherrypy.tree.mount(root=self.web,
                            script_name=self.web.API_ENDPOINT,
                            config={'/':  {'request.dispatch': self.web.route_dispatcher}})

        self.test_admin = UserDTO(
            id=30,
            username='admin_1',
            role='ADMIN'
        )

        self.test_user_1 = UserDTO(
            id=30,
            username='user_1',
            role='USER'
        )
        self.test_user_1.set_password('test')

        self.doorbell_config = SystemDoorbellConfigDTO(enabled=True)

    def test_get_no_auth(self):
        with mock.patch.object(self.system_config_controller, 'get_doorbell_config', return_value=self.doorbell_config):
            status, headers, response = self.GET('/api/v1/system/configuration/doorbell', login_user=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps({'enabled': True}))

    def test_put_unauthorized(self):
        with mock.patch.object(self.system_config_controller, 'save_doorbell_config') as save_config_func:
            body = {
                'enabled': False
            }
            status, headers, response = self.PUT('/api/v1/system/configuration/doorbell', login_user=None, body=json.dumps(body))
            save_config_func.assert_not_called()
            self.assertStatus('401 Unauthorized')

            status, headers, response = self.PUT('/api/v1/system/configuration/doorbell', login_user=self.test_user_1, body=json.dumps(body))
            save_config_func.assert_not_called()
            self.assertStatus('401 Unauthorized')

    def test_put_body(self):
        with mock.patch.object(self.system_config_controller, 'save_doorbell_config') as save_config_func:
            body = {
                'enabled': False
            }
            status, headers, response = self.PUT('/api/v1/system/configuration/doorbell', login_user=self.test_admin, body=json.dumps(body))
            save_config_func.assert_called_once_with(SystemDoorbellConfigDTO(enabled=False))
            self.assertStatus('200 OK')
            self.assertBody('')

    def test_put_no_body(self):
        with mock.patch.object(self.system_config_controller, 'save_doorbell_config') as save_config_func:
            status, headers, response = self.PUT('/api/v1/system/configuration/doorbell', login_user=None, body=None)
            save_config_func.assert_not_called()
            self.assertStatus('400 Bad Request')
            self.assertBody('Wrong input parameter: No body has been passed to the request')
