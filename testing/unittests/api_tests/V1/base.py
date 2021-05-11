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
import time

from cherrypy.test import helper
import mock

from gateway.authentication_controller import AuthenticationToken, TokenStore, AuthenticationController
from gateway.user_controller import UserController

from ioc import SetTestMode, SetUpTestInjections

if False:  # MyPy
    from typing import Optional, Dict
    from gateway.dto import UserDTO


class BaseCherryPyUnitTester(helper.CPWebCase):

    def setUp(self):
        super(BaseCherryPyUnitTester, self).setUp()
        SetTestMode()
        SetUpTestInjections(token_timeout=3)
        self.auth_controller = mock.Mock(AuthenticationController)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        self.users_controller = mock.Mock(UserController)
        self.config = {'cloud_user': 'root', 'cloud_password': 'root'}
        self.token_store = mock.Mock(TokenStore)
        SetUpTestInjections(token_store=self.token_store)
        self.users_controller.authentication_controller = self.auth_controller
        SetUpTestInjections(user_controller=self.users_controller,
                            config=self.config)

    def general_request(self, url, method, login_user, headers, body=None):
        if login_user is not None:
            token = AuthenticationToken(login_user, token='test-token', expire_timestamp=(int(time.time()) + 3600))
        else:
            token = None
        with mock.patch.object(self.users_controller, 'check_token', return_value=token), \
                mock.patch.object(self.auth_controller, 'check_token', return_value=token):
            headers = headers or []
            if token is not None:
                headers.append(('Authorization', 'Bearer {}'.format(token.token)))
            if body is not None:
                headers.append(('Content-Length', str(len(body)) if body is not None else '0'))
                headers.append(('Content-Type', 'application/json'))
            return self.getPage(url, headers=headers, method=method, body=body)

    def GET(self, url, login_user=None, headers=None):
        # type: (str, Optional[UserDTO], Optional[Dict]) -> str
        return self.general_request(url, method='GET', login_user=login_user, headers=headers, body=None)

    def POST(self, url, login_user=None, headers=None, body=None):
        # type: (str, Optional[UserDTO], Optional[Dict], Optional[str]) -> str
        return self.general_request(url, method='POST', login_user=login_user, headers=headers, body=body)

    def PUT(self, url, login_user=None, headers=None, body=None):
        # type: (str, Optional[UserDTO], Optional[Dict], Optional[str]) -> str
        return self.general_request(url, method='PUT', login_user=login_user, headers=headers, body=body)

    def DELETE(self, url, login_user=None, headers=None):
        # type: (str, Optional[UserDTO], Optional[Dict]) -> str
        return self.general_request(url, method='DELETE', login_user=login_user, headers=headers, body=None)

    @classmethod
    def setup_server(cls):
        pass

    # Do not run the standard test to check if the tree is mounted, the other tests will also fail
    def test_gc(self):
        pass
