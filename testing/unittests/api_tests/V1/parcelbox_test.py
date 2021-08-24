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
Parcelbox API tests
"""
from __future__ import absolute_import

import cherrypy
import ujson as json

import mock
from mock import call

from gateway.dto import UserDTO, ParcelBoxDTO, ApartmentDTO, DeliveryDTO
from gateway.delivery_controller import DeliveryController
from esafe.rebus.rebus_controller import RebusController
from gateway.exceptions import WrongInputParametersException
from gateway.api.serializers import ParcelBoxSerializer
from gateway.api.V1.parcelbox import ParcelBox

from ioc import SetUpTestInjections

from .base import BaseCherryPyUnitTester


class ParcelboxApiCherryPyTest(BaseCherryPyUnitTester):
    def setUp(self):
        self.delivery_controller = mock.Mock(DeliveryController)
        SetUpTestInjections(delivery_controller=self.delivery_controller)
        self.rebus_controller = mock.Mock(RebusController)
        SetUpTestInjections(rebus_controller=self.rebus_controller)
        super(ParcelboxApiCherryPyTest, self).setUp()
        self.web = ParcelBox()
        cherrypy.tree.mount(root=self.web,
                            script_name=self.web.API_ENDPOINT,
                            config={'/':  {'request.dispatch': self.web.route_dispatcher}})

        self.test_apartment_1 = ApartmentDTO(
            id=1,
            name='test_apartment_1',
            mailbox_rebus_id=None,
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

        self.test_parcelbox_1 = ParcelBoxDTO(id=32, label='32', is_open=False, size=ParcelBoxDTO.Size.S, available=True, height=200, width=300)
        self.test_parcelbox_2 = ParcelBoxDTO(id=48, label='48', is_open=True, size=ParcelBoxDTO.Size.M, available=True, height=300, width=300)
        self.test_parcelbox_3 = ParcelBoxDTO(id=64, label='64', is_open=True, size=ParcelBoxDTO.Size.XL, available=False, height=400, width=300)

        self.all_parcelboxes = [self.test_parcelbox_1, self.test_parcelbox_2, self.test_parcelbox_3]

        self.test_delivery = DeliveryDTO(
            id=1,
            type='DELIVERY',
            timestamp_delivery='some_timestamp',
            user_delivery=None,
            user_pickup=self.test_user_1,
            timestamp_pickup=None,
            courier_firm='TNT',
            parcelbox_rebus_id=32
        )

    def test_get_parcelboxes(self):
        with mock.patch.object(self.rebus_controller, 'get_parcelboxes', return_value=self.all_parcelboxes) as get_parcelbox_func:
            # Auth: normal user
            status, headers, response = self.GET('/api/v1/parcelboxes', login_user=self.test_user_1, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps([ParcelBoxSerializer.serialize(parcelbox) for parcelbox in self.all_parcelboxes]))
            get_parcelbox_func.assert_called_once_with(size=None, available=None)
            get_parcelbox_func.reset_mock()

            # Auth: No auth
            status, headers, response = self.GET('/api/v1/parcelboxes', login_user=None, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps([ParcelBoxSerializer.serialize(parcelbox) for parcelbox in self.all_parcelboxes]))
            get_parcelbox_func.assert_called_once_with(size=None, available=None)
            get_parcelbox_func.reset_mock()

            # Filter on size
            status, headers, response = self.GET('/api/v1/parcelboxes?size=M', login_user=self.test_admin, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps([ParcelBoxSerializer.serialize(parcelbox) for parcelbox in self.all_parcelboxes]))
            get_parcelbox_func.assert_called_once_with(size='M', available=None)
            get_parcelbox_func.reset_mock()

            # filter on size (lower case)
            status, headers, response = self.GET('/api/v1/parcelboxes?size=m', login_user=self.test_admin, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps([ParcelBoxSerializer.serialize(parcelbox) for parcelbox in self.all_parcelboxes]))
            get_parcelbox_func.assert_called_once_with(size='m', available=None)
            get_parcelbox_func.reset_mock()

            # filter on available
            status, headers, response = self.GET('/api/v1/parcelboxes?size=m&available=true', login_user=self.test_admin, headers=None)
            self.assertStatus('200 OK')
            get_parcelbox_func.assert_called_once_with(size='m', available=True)
            get_parcelbox_func.reset_mock()

            with mock.patch.object(self.delivery_controller, 'load_deliveries_filter', return_value=[self.test_delivery]) as get_deliveries_func:
                status, headers, response = self.GET('/api/v1/parcelboxes?size=m&available=true&show_deliveries=true', login_user=self.test_admin, headers=None)
                self.assertStatus('200 OK')
                get_parcelbox_func.assert_called_once_with(size='m', available=True)
                get_parcelbox_func.reset_mock()
                delivery_calls = [call(delivery_parcelbox_rebus_id=self.test_parcelbox_1.id),
                                  call(delivery_parcelbox_rebus_id=self.test_parcelbox_2.id),
                                  call(delivery_parcelbox_rebus_id=self.test_parcelbox_3.id)]
                get_deliveries_func.assert_has_calls(delivery_calls, any_order=False)
                get_deliveries_func.reset_mock()

                # Fail when requested with non super credentials and requesting delivery data
                status, headers, response = self.GET('/api/v1/parcelboxes?size=m&available=true&show_deliveries=true', login_user=self.test_user_1, headers=None)
                self.assertStatus('401 Unauthorized')
                get_parcelbox_func.assert_called_once_with(size='m', available=True)
                get_parcelbox_func.reset_mock()
                get_deliveries_func.assert_not_called()
                get_deliveries_func.reset_mock()


        with mock.patch.object(self.rebus_controller, 'get_parcelboxes', return_value=[self.test_parcelbox_1]) as get_parcelbox_func:
            # Request one specific parcelbox
            status, headers, response = self.GET('/api/v1/parcelboxes/32', login_user=None, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps(ParcelBoxSerializer.serialize(self.test_parcelbox_1)))
            get_parcelbox_func.assert_called_once_with(rebus_id=32)
            get_parcelbox_func.reset_mock()

        with mock.patch.object(self.rebus_controller, 'get_parcelboxes', return_value=[]) as get_parcelbox_func:
            # non existing parcelbox
            status, headers, response = self.GET('/api/v1/parcelboxes/33', login_user=None, headers=None)
            self.assertStatus('404 Not Found')
            get_parcelbox_func.assert_called_once_with(rebus_id=33)
            get_parcelbox_func.reset_mock()

            # with non integer rebus_id
            status, headers, response = self.GET('/api/v1/parcelboxes/foo', login_user=None, headers=None)
            self.assertStatus('400 Bad Request')
            get_parcelbox_func.assert_not_called()
            get_parcelbox_func.reset_mock()

    def test_put_parcelboxes(self):
        with mock.patch.object(self.rebus_controller, 'get_parcelboxes', return_value=[self.test_parcelbox_1]) as get_parcelbox_func, \
                mock.patch.object(self.rebus_controller, 'open_box', return_value=self.test_parcelbox_1) as open_box_func, \
                mock.patch.object(self.delivery_controller, 'load_deliveries', return_value=[self.test_delivery]) as load_delivery_func, \
                mock.patch.object(self.delivery_controller, 'load_deliveries_filter', return_value=[self.test_delivery]) as load_delivery_func_filter:
            # Auth: normal user
            json_body = {'open': True}
            status, headers, response = self.PUT('/api/v1/parcelboxes/32', login_user=self.test_user_1, headers=None, body=json.dumps(json_body))
            self.assertStatus('200 OK')
            self.assertBody(json.dumps(ParcelBoxSerializer.serialize(self.test_parcelbox_1)))
            get_parcelbox_func.assert_called_once_with(rebus_id=32)
            get_parcelbox_func.reset_mock()
            open_box_func.assert_called_once_with(32)
            open_box_func.reset_mock()
            load_delivery_func.assert_called_once_with(user_id=self.test_user_1.id)
            load_delivery_func.reset_mock()
            load_delivery_func_filter.assert_not_called()
            load_delivery_func_filter.reset_mock()

            # Auth: no Auth
            json_body = {'open': True}
            status, headers, response = self.PUT('/api/v1/parcelboxes/32', login_user=None, headers=None, body=json.dumps(json_body))
            self.assertStatus('401 Unauthorized')
            get_parcelbox_func.assert_not_called()
            get_parcelbox_func.reset_mock()
            open_box_func.assert_not_called()
            open_box_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()

            # Auth: wrong user
            json_body = {'open': True}
            load_delivery_func.return_value = []
            status, headers, response = self.PUT('/api/v1/parcelboxes/32', login_user=self.test_user_2, headers=None, body=json.dumps(json_body))
            self.assertStatus('401 Unauthorized')
            get_parcelbox_func.assert_called_once_with(rebus_id=32)
            get_parcelbox_func.reset_mock()
            open_box_func.assert_not_called()
            open_box_func.reset_mock()
            load_delivery_func.assert_called_once_with(user_id=self.test_user_2.id)
            load_delivery_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()

            # Auth: admin user
            json_body = {'open': True}
            status, headers, response = self.PUT('/api/v1/parcelboxes/32', login_user=self.test_admin, headers=None, body=json.dumps(json_body))
            self.assertStatus('200 OK')
            self.assertBody(json.dumps(ParcelBoxSerializer.serialize(self.test_parcelbox_1)))
            get_parcelbox_func.assert_called_once_with(rebus_id=32)
            get_parcelbox_func.reset_mock()
            open_box_func.assert_called_once_with(32)
            open_box_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()

            # random box
            status, headers, response = self.PUT('/api/v1/parcelboxes/open?size=m', login_user=self.test_user_1, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps(ParcelBoxSerializer.serialize(self.test_parcelbox_1)))
            get_parcelbox_func.assert_called_once_with(available=True, size='m')
            get_parcelbox_func.reset_mock()
            open_box_func.assert_called_once_with(self.test_parcelbox_1.id)
            open_box_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()

            # random box
            status, headers, response = self.PUT('/api/v1/parcelboxes/open?size=m', login_user=None, headers=None)
            self.assertStatus('200 OK')
            self.assertBody(json.dumps(ParcelBoxSerializer.serialize(self.test_parcelbox_1)))
            get_parcelbox_func.assert_called_once_with(available=True, size='m')
            get_parcelbox_func.reset_mock()
            open_box_func.assert_called_once_with(self.test_parcelbox_1.id)
            open_box_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()

            # random box, with no known size
            get_parcelbox_func.return_value = []
            status, headers, response = self.PUT('/api/v1/parcelboxes/open?size=foo', login_user=None, headers=None)
            self.assertStatus('409 Conflict')
            get_parcelbox_func.assert_called_once_with(available=True, size='foo')
            get_parcelbox_func.reset_mock()
            open_box_func.assert_not_called()
            open_box_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()

            # random box, no size provided
            get_parcelbox_func.return_value = []
            status, headers, response = self.PUT('/api/v1/parcelboxes/open', login_user=None, headers=None)
            self.assertStatus('400 Bad Request')
            self.assertBody(WrongInputParametersException.bytes_message() + b': Missing parameters')
            get_parcelbox_func.assert_not_called()
            get_parcelbox_func.reset_mock()
            open_box_func.assert_not_called()
            open_box_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()
            load_delivery_func.assert_not_called()
            load_delivery_func.reset_mock()

