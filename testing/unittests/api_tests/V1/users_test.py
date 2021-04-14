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
import time
import unittest

import mock

from gateway.authentication_controller import AuthenticationController, AuthenticationToken
from gateway.api.serializers.user import UserSerializer
from gateway.dto.user import UserDTO
from gateway.user_controller import UserController
from gateway.webservice_v1 import Users

from ioc import SetTestMode, SetUpTestInjections


class ApiUsersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.users_controller = mock.Mock(UserController)
        SetUpTestInjections(user_controller=self.users_controller)
        self.web = Users()

    def test_get_users_list(self):
        user_dto = UserDTO(
            id=37,
            username='testerken',
            role='ADMIN',
            pin_code='1234',
            apartment=None,
            accepted_terms=1
        )
        with mock.patch.object(self.users_controller, 'load_users', return_value=[user_dto]):
            auth_token = AuthenticationToken(user=user_dto, token='test-token', expire_timestamp=int(time.time() + 3600))
            response = self.web.GET(token=auth_token, role=user_dto.role)
            resp_dict = json.loads(response)
            first_user = resp_dict[0]
            user_dto_response = UserDTO(**first_user)
            self.assertNotIn('pin_code', first_user)
            user_dto_response.pin_code = user_dto.pin_code  # Manually set the pin code since this is filtered out in the api
            self.assertEqual(user_dto, user_dto_response)

