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
rfid api tests
"""

from __future__ import absolute_import

import cherrypy
import time
import ujson as json
import unittest

import mock

from gateway.api.serializers import RfidSerializer
from gateway.authentication_controller import AuthenticationController, AuthenticationToken
from gateway.dto import RfidDTO, UserDTO
from gateway.exceptions import *
from gateway.user_controller import UserController
from gateway.rfid_controller import RfidController
from gateway.webservice_v1 import Rfid

from ioc import SetTestMode, SetUpTestInjections

from .base import BaseCherryPyUnitTester


class ApiSystemConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.user_controller = mock.Mock(UserController)
        self.rfid_controller = mock.Mock(RfidController)
        SetUpTestInjections(rfid_controller=self.rfid_controller, user_controller=self.user_controller)
        self.web = Rfid()

        self.test_user_1 = UserDTO(
            id=1,
            username='TEST_USER_1',
            role='USER'
        )

        self.test_admin_1 = UserDTO(
            id=2,
            username='TEST_ADMIN_1',
            role='ADMIN'
        )

        self.test_rfid_1 = RfidDTO(
            id=1,
            tag_string='tag_1',
            uid_manufacturer='uid_manu_1',
            timestamp_created=RfidController.current_timestamp_to_string_format(),
            user=self.test_user_1,
            uid_extension='',
            enter_count=0,
            blacklisted=False,
            label='test-rfid-1',
            timestamp_last_used=RfidController.current_timestamp_to_string_format()
        )

        self.test_rfid_2 = RfidDTO(
            id=2,
            tag_string='tag_2',
            uid_manufacturer='uid_manu_2',
            timestamp_created=RfidController.current_timestamp_to_string_format(),
            user=self.test_admin_1,
            uid_extension='',
            enter_count=0,
            blacklisted=False,
            label='test-rfid-2',
            timestamp_last_used=RfidController.current_timestamp_to_string_format()
        )

        self.all_test_rfids = [self.test_rfid_1, self.test_rfid_2]

    def test_get_rfid(self):
        with mock.patch.object(self.rfid_controller, 'load_rfids', return_value=self.all_test_rfids):
            auth_token = AuthenticationToken(self.test_admin_1, token='test-token', expire_timestamp=int(time.time() + 3600))
            resp = self.web.get_rfids(token=auth_token)
            rfids = json.loads(resp)
            all_test_rfids_serial = [RfidSerializer.serialize(x) for x in self.all_test_rfids]
            self.assertEqual(all_test_rfids_serial, rfids)

    def test_get_rfid_normal_user(self):
        with mock.patch.object(self.rfid_controller, 'load_rfids', return_value=self.all_test_rfids):
            auth_token = AuthenticationToken(self.test_user_1, token='test-token', expire_timestamp=int(time.time() + 3600))
            resp = self.web.get_rfids(token=auth_token)
            rfids = json.loads(resp)
            all_test_rfids_serial = [RfidSerializer.serialize(self.test_rfid_1)]
            self.assertEqual(all_test_rfids_serial, rfids)

    def test_get_one_rfid_normal_user(self):
        with mock.patch.object(self.rfid_controller, 'load_rfid', return_value=self.test_rfid_1):
            auth_token = AuthenticationToken(self.test_user_1, token='test-token', expire_timestamp=int(time.time() + 3600))
            resp = self.web.get_rfid(rfid_id=1, token=auth_token)
            rfids = json.loads(resp)
            all_test_rfids_serial = RfidSerializer.serialize(self.test_rfid_1)
            self.assertEqual(all_test_rfids_serial, rfids)

    def test_get_one_rfid_wrong_user(self):
        with mock.patch.object(self.rfid_controller, 'load_rfid', return_value=self.test_rfid_2):
            auth_token = AuthenticationToken(self.test_user_1, token='test-token', expire_timestamp=int(time.time() + 3600))
            resp = self.web.get_rfid(rfid_id=2, token=auth_token)
            print(resp)
            # should be unauthorized since you request another rfid that is not yours as a non admin
            self.assertIn(UnAuthorizedException.bytes_message(), resp)

    def test_get_one_rfid_admin_user(self):
        with mock.patch.object(self.rfid_controller, 'load_rfid', return_value=self.test_rfid_1):
            auth_token = AuthenticationToken(self.test_admin_1, token='test-token', expire_timestamp=int(time.time() + 3600))
            resp = self.web.get_rfid(rfid_id=1, token=auth_token)
            rfids = json.loads(resp)
            all_test_rfids_serial = RfidSerializer.serialize(self.test_rfid_1)
            # Should go as planned, admin can request all rfids
            self.assertEqual(all_test_rfids_serial, rfids)

    def test_delete_rfid_happy_path(self):
        with mock.patch.object(self.rfid_controller, 'load_rfid', return_value=self.test_rfid_1), \
                mock.patch.object(self.rfid_controller, 'delete_rfid') as delete_rfid_func:
            auth_token = AuthenticationToken(self.test_admin_1, token='test-token', expire_timestamp=int(time.time() + 3600))
            resp = self.web.delete_rfid(rfid_id=1, token=auth_token)
            self.assertEqual(b'OK', resp)

    def test_delete_rfid_wrong_auth(self):
        with mock.patch.object(self.rfid_controller, 'load_rfid', return_value=self.test_rfid_2), \
                mock.patch.object(self.rfid_controller, 'delete_rfid') as delete_rfid_func:
            auth_token = AuthenticationToken(self.test_user_1, token='test-token', expire_timestamp=int(time.time() + 3600))
            resp = self.web.delete_rfid(rfid_id=1, token=auth_token)
            self.assertIn(UnAuthorizedException.bytes_message(), resp)


class RFIDApiCherryPyTest(BaseCherryPyUnitTester):
    def setUp(self):
        super(RFIDApiCherryPyTest, self).setUp()
        self.rfid_controller = mock.Mock(RfidController)
        SetUpTestInjections(rfid_controller=self.rfid_controller)
        self.web = Rfid()
        cherrypy.tree.mount(root=self.web,
                            script_name=self.web.API_ENDPOINT,
                            config={'/':  {'request.dispatch': self.web.route_dispatcher}})

        self.test_user_1 = UserDTO(
            id=1,
            username='TEST_USER_1',
            role='USER'
        )

        self.test_admin_1 = UserDTO(
            id=2,
            username='TEST_ADMIN_1',
            role='ADMIN'
        )

        self.test_rfid_1 = RfidDTO(
            id=1,
            tag_string='tag_1',
            uid_manufacturer='uid_manu_1',
            timestamp_created=RfidController.current_timestamp_to_string_format(),
            user=self.test_user_1,
            uid_extension='',
            enter_count=0,
            blacklisted=False,
            label='test-rfid-1',
            timestamp_last_used=RfidController.current_timestamp_to_string_format()
        )

        self.test_rfid_2 = RfidDTO(
            id=2,
            tag_string='tag_2',
            uid_manufacturer='uid_manu_2',
            timestamp_created=RfidController.current_timestamp_to_string_format(),
            user=self.test_admin_1,
            uid_extension='',
            enter_count=0,
            blacklisted=False,
            label='test-rfid-2',
            timestamp_last_used=RfidController.current_timestamp_to_string_format()
        )

        self.all_test_rfids = [self.test_rfid_1, self.test_rfid_2]


    def test_get_no_auth(self):
        with mock.patch.object(self.rfid_controller, 'load_rfids', return_value=self.all_test_rfids):
            status, headers, response = self.GET('/api/v1/rfid', login_user=None)
            self.assertStatus('401 Unauthorized')

    def test_get_one_no_auth(self):
        with mock.patch.object(self.rfid_controller, 'load_rfids', return_value=self.all_test_rfids):
            status, headers, response = self.GET('/api/v1/rfid/1', login_user=None)
            self.assertStatus('401 Unauthorized')

    def test_put_body(self):
        body = json.dumps({'dummy': 'test'})
        status, headers, response = self.PUT('/api/v1/rfid/add_new/cancel', login_user=None, body=body)
        self.assertStatus('400 Bad Request')
        self.assertBody('Could not parse input: Received a body, but no body is required')

    def test_delete_one_no_auth(self):
        with mock.patch.object(self.rfid_controller, 'load_rfid', return_value=self.test_rfid_1), \
                mock.patch.object(self.rfid_controller, 'delete_rfid') as delete_rfid_func:
            status, headers, response = self.DELETE('/api/v1/rfid/1', login_user=None)
            self.assertStatus('401 Unauthorized')

