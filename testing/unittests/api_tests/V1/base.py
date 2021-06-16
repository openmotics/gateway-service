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

import cherrypy
from cherrypy.test import helper
import mock
import ujson as json

from gateway.authentication_controller import AuthenticationToken, TokenStore, AuthenticationController
from gateway.user_controller import UserController

from ioc import SetTestMode, SetUpTestInjections, TearDownTestInjections

if False:  # MyPy
    from typing import Optional, Dict
    from gateway.dto import UserDTO


class BaseCherryPyUnitTester(helper.CPWebCase):

    @classmethod
    def setUpClass(cls):
        super(BaseCherryPyUnitTester, cls).setUpClass()
        SetTestMode()

        # setting the same error return values as the web service
        def error_generic(status, message, *args, **kwargs):
            _ = args, kwargs
            cherrypy.response.headers["Content-Type"] = "application/json"
            cherrypy.response.status = status
            return json.dumps({"success": False, "msg": message})

        def error_unexpected():
            cherrypy.response.headers["Content-Type"] = "application/json"
            cherrypy.response.status = 500  # Internal Server Error
            return json.dumps({"success": False, "msg": "unknown_error"})

        cherrypy.config.update({'error_page.404': error_generic,
                                'error_page.401': error_generic,
                                'error_page.503': error_generic,
                                'request.error_response': error_unexpected})

    def tearDown(self):
        super(BaseCherryPyUnitTester, self).tearDown()
        TearDownTestInjections()

    def setUp(self):
        super(BaseCherryPyUnitTester, self).setUp()
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
                mock.patch.object(self.auth_controller, 'check_token', return_value=token), \
                mock.patch.object(self.auth_controller, 'check_api_secret', wraps=lambda secret: secret == 'Test-Secret'):
            headers = headers or {}
            headers = [(k, v) for k, v in headers.items()]
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

    # explicitly do nothing in the setup_server function, but keep it here since it triggers it to setup the cherrypy tree
    @classmethod
    def setup_server(cls):
        pass

    # Do not run the standard test to check if the tree is mounted, the other tests will also fail
    def test_gc(self):
        pass

    # Function that is usefull for debugging
    def print_request_result(self):
        print('-----------------------')
        print('Status:  {}'.format(self.status))
        print('Headers: {}'.format(self.headers))
        print('Body:    {}'.format(self.body))
        print('-----------------------')
