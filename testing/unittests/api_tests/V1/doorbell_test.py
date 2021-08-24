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
Doorbell API tests
"""
from __future__ import absolute_import

import cherrypy
import ujson as json

import mock

from gateway.api.serializers.doorbell import DoorbellSerializer
from gateway.dto import UserDTO, ApartmentDTO, DoorbellDTO
from esafe.rebus.rebus_controller import RebusController
from gateway.api.V1.doorbell import Doorbell

from ioc import SetUpTestInjections

from .base import BaseCherryPyUnitTester


class DoorbellApiCherryPyTest(BaseCherryPyUnitTester):

    def mount_web(self):
        cherrypy.tree.mount(root=self.web,
                            script_name=self.web.API_ENDPOINT,
                            config={'/':  {'request.dispatch': self.web.route_dispatcher}})

    def setUp(self):
        self.rebus_controller = mock.Mock(RebusController)
        SetUpTestInjections(rebus_controller=self.rebus_controller)
        super(DoorbellApiCherryPyTest, self).setUp()
        self.web = Doorbell()
        self.mount_web()

        self.test_apartment_1 = ApartmentDTO(
            id=1,
            name='test_apartment_1',
            mailbox_rebus_id=None,
            doorbell_rebus_id=17
        )

        self.test_admin = UserDTO(
            id=30,
            username='admin_1',
            role='ADMIN'
        )

        self.test_user_1 = UserDTO(
            id=40,
            username='user_1',
            role='USER',
            apartment=self.test_apartment_1
        )
        self.test_user_1.set_password('test')

        self.test_user_2 = UserDTO(
            id=41,
            username='user_2',
            role='USER'
        )
        self.test_user_2.set_password('test')

        self.test_doorbell_1 = DoorbellDTO(17, label='17', apartment=self.test_apartment_1)
        self.test_doorbell_2 = DoorbellDTO(18, label='18', apartment=None)
        self.test_doorbell_3 = DoorbellDTO(19, label='19', apartment=None)
        self.test_doorbell_4 = DoorbellDTO(20, label='20', apartment=None)

        self.all_doorbells = [self.test_doorbell_1, self.test_doorbell_2, self.test_doorbell_3, self.test_doorbell_4]

    def test_no_rebus_controller(self):
        SetUpTestInjections(rebus_controller=None)
        self.web = Doorbell()
        self.mount_web()
        status, headers, response = self.GET('/api/v1/doorbells', login_user=self.test_user_1, headers=None)
        self.assertStatus('409 Conflict')
        status, headers, response = self.PUT('/api/v1/doorbells/ring/17', login_user=self.test_user_1, headers=None)
        self.assertStatus('409 Conflict')

    def test_get_doorbells(self):
        with mock.patch.object(self.rebus_controller, 'get_doorbells', return_value=self.all_doorbells) as get_doorbell_func:
            # Auth: normal user
            status, headers, response = self.GET('/api/v1/doorbells', login_user=self.test_user_1, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps([DoorbellSerializer.serialize(doorbell) for doorbell in self.all_doorbells]))
            get_doorbell_func.assert_called_once_with()
            get_doorbell_func.reset_mock()

            # Auth: no auth
            status, headers, response = self.GET('/api/v1/doorbells', login_user=None, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps([DoorbellSerializer.serialize(doorbell) for doorbell in self.all_doorbells]))
            get_doorbell_func.assert_called_once_with()
            get_doorbell_func.reset_mock()

    def test_ring_doorbell(self):
        with mock.patch.object(self.rebus_controller, 'get_doorbells', return_value=self.all_doorbells) as get_doorbell_func, \
                mock.patch.object(self.rebus_controller, 'ring_doorbell') as ring_doorbell_func:
            # Auth: normal user
            status, headers, response = self.PUT('/api/v1/doorbells/ring/17', login_user=self.test_user_1, headers=None)
            self.assertStatus('204 No Content')
            get_doorbell_func.assert_called_once_with()
            get_doorbell_func.reset_mock()
            ring_doorbell_func.assert_called_once_with(17)
            ring_doorbell_func.reset_mock()

            # Auth: no user
            status, headers, response = self.PUT('/api/v1/doorbells/ring/17', login_user=None, headers=None)
            self.assertStatus('204 No Content')
            get_doorbell_func.assert_called_once_with()
            get_doorbell_func.reset_mock()
            ring_doorbell_func.assert_called_once_with(17)
            ring_doorbell_func.reset_mock()

            # Auth: no user
            status, headers, response = self.PUT('/api/v1/doorbells/ring/foo', login_user=None, headers=None)
            self.assertStatus('400 Bad Request')
            get_doorbell_func.assert_not_called()
            get_doorbell_func.reset_mock()
            ring_doorbell_func.assert_not_called()
            ring_doorbell_func.reset_mock()

            # Auth: no user
            status, headers, response = self.PUT('/api/v1/doorbells/ring/13', login_user=None, headers=None)
            self.assertStatus('404 Not Found')
            get_doorbell_func.assert_called_once_with()
            get_doorbell_func.reset_mock()
            ring_doorbell_func.assert_not_called()
            ring_doorbell_func.reset_mock()

