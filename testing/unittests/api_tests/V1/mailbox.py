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
Mailbox API tests
"""
from __future__ import absolute_import

import cherrypy
import ujson as json

import mock

from gateway.dto import UserDTO, MailBoxDTO, ApartmentDTO
from gateway.delivery_controller import DeliveryController
from esafe.rebus.rebus_controller import EsafeController
from gateway.api.serializers import MailboxSerializer
from gateway.api.V1.mailbox import MailBox

from ioc import SetUpTestInjections

from .base import BaseCherryPyUnitTester


class MailboxApiCherryPyTest(BaseCherryPyUnitTester):
    def setUp(self):
        self.delivery_controller = mock.Mock(DeliveryController)
        SetUpTestInjections(delivery_controller=self.delivery_controller)
        self.esafe_controller = mock.Mock(EsafeController)
        SetUpTestInjections(esafe_controller=self.esafe_controller)
        super(MailboxApiCherryPyTest, self).setUp()
        self.web = MailBox()
        cherrypy.tree.mount(root=self.web,
                            script_name=self.web.API_ENDPOINT,
                            config={'/':  {'request.dispatch': self.web.route_dispatcher}})

        self.test_apartment_1 = ApartmentDTO(
            id=1,
            name='test_apartment_1',
            mailbox_rebus_id=32,
            doorbell_rebus_id=None
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

        self.test_mailbox_1 = MailBoxDTO(id=32, label='32', apartment=self.test_apartment_1, is_open=False)
        self.test_mailbox_2 = MailBoxDTO(id=48, label='48', apartment=None, is_open=True)
        self.test_mailbox_3 = MailBoxDTO(id=64, label='64', apartment=None, is_open=True)

        self.all_mailboxes = [self.test_mailbox_1, self.test_mailbox_2, self.test_mailbox_3]

    def test_get_mailboxes(self):
        with mock.patch.object(self.esafe_controller, 'get_mailboxes', return_value=self.all_mailboxes) as get_mailbox_func:
            # Auth: normal user
            status, headers, response = self.GET('/api/v1/mailboxes', login_user=self.test_user_1, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps([MailboxSerializer.serialize(mailbox) for mailbox in self.all_mailboxes]))
            get_mailbox_func.assert_called_once_with()
            get_mailbox_func.reset_mock()

            # Auth: No auth
            status, headers, response = self.GET('/api/v1/mailboxes', login_user=None, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps([MailboxSerializer.serialize(mailbox) for mailbox in self.all_mailboxes]))
            get_mailbox_func.assert_called_once_with()
            get_mailbox_func.reset_mock()

        with mock.patch.object(self.esafe_controller, 'get_mailboxes', return_value=[self.test_mailbox_1]) as get_mailbox_func:
            # Request one specific mailbox
            status, headers, response = self.GET('/api/v1/mailboxes/32', login_user=None, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps(MailboxSerializer.serialize(self.test_mailbox_1)))
            get_mailbox_func.assert_called_once_with(rebus_id=32)
            get_mailbox_func.reset_mock()

        with mock.patch.object(self.esafe_controller, 'get_mailboxes', return_value=[]) as get_mailbox_func:
            # non existing mailbox
            status, headers, response = self.GET('/api/v1/mailboxes/33', login_user=None, headers=None)
            self.assertStatus('404 Not Found')
            get_mailbox_func.assert_called_once_with(rebus_id=33)
            get_mailbox_func.reset_mock()

            # with non integer rebus_id
            status, headers, response = self.GET('/api/v1/mailboxes/foo', login_user=None, headers=None)
            self.assertStatus('400 Bad Request')
            get_mailbox_func.assert_not_called()
            get_mailbox_func.reset_mock()

    def test_put_mailboxes(self):
        with mock.patch.object(self.esafe_controller, 'get_mailboxes', return_value=[self.test_mailbox_1]) as get_mailbox_func, \
                mock.patch.object(self.esafe_controller, 'open_box', return_value=self.test_mailbox_1) as open_box_func, \
                mock.patch.object(self.users_controller, 'load_user_by_apartment_id', return_value=self.test_user_1) as get_user_func:
            # Auth: normal user
            json_body = {'open': True}
            status, headers, response = self.PUT('/api/v1/mailboxes/32', login_user=self.test_user_1, headers=None, body=json.dumps(json_body))
            self.assertStatus('200 OK')
            self.assertBody(json.dumps(MailboxSerializer.serialize(self.test_mailbox_1)))
            get_mailbox_func.assert_called_once_with(rebus_id=32)
            get_mailbox_func.reset_mock()
            open_box_func.assert_called_once_with(32)
            open_box_func.reset_mock()
            get_user_func.assert_called_once_with(1)
            get_user_func.reset_mock()

            # Auth: no Auth
            json_body = {'open': True}
            status, headers, response = self.PUT('/api/v1/mailboxes/32', login_user=None, headers=None, body=json.dumps(json_body))
            self.assertStatus('401 Unauthorized')
            get_mailbox_func.assert_not_called()
            get_mailbox_func.reset_mock()
            open_box_func.assert_not_called()
            open_box_func.reset_mock()
            get_user_func.assert_not_called()
            get_user_func.reset_mock()

            # Auth: wrong user
            json_body = {'open': True}
            status, headers, response = self.PUT('/api/v1/mailboxes/32', login_user=self.test_user_2, headers=None, body=json.dumps(json_body))
            self.assertStatus('401 Unauthorized')
            get_mailbox_func.assert_called_once_with(rebus_id=32)
            get_mailbox_func.reset_mock()
            open_box_func.assert_not_called()
            open_box_func.reset_mock()
            get_user_func.assert_called_once_with(1)
            get_user_func.reset_mock()

            # Auth: admin user
            json_body = {'open': True}
            status, headers, response = self.PUT('/api/v1/mailboxes/32', login_user=self.test_admin, headers=None, body=json.dumps(json_body))
            self.assertStatus('200 OK')
            self.assertBody(json.dumps(MailboxSerializer.serialize(self.test_mailbox_1)))
            get_mailbox_func.assert_called_once_with(rebus_id=32)
            get_mailbox_func.reset_mock()
            open_box_func.assert_called_once_with(32)
            open_box_func.reset_mock()
            get_user_func.assert_not_called()
            get_user_func.reset_mock()

