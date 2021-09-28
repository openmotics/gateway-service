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
from __future__ import absolute_import

import cherrypy
import copy
import json
import time
import unittest

import mock

from gateway.authentication_controller import AuthenticationToken, LoginMethod, AuthenticationController
from gateway.dto import DeliveryDTO, UserDTO
from esafe.rebus.rebus_controller import RebusController
from gateway.exceptions import *
from gateway.delivery_controller import DeliveryController
from gateway.user_controller import UserController
from gateway.api.V1.deliveries import Deliveries

from ioc import SetTestMode, SetUpTestInjections

from .base import BaseCherryPyUnitTester


class ApiDeliveriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.auth_controller = mock.Mock(AuthenticationController)
        self.user_controller = mock.Mock(UserController)
        self.delivery_controller = mock.Mock(DeliveryController)
        self.rebus_controller = mock.Mock(RebusController)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        SetUpTestInjections(user_controller=self.user_controller, delivery_controller=self.delivery_controller, rebus_controller=self.rebus_controller)
        self.web = Deliveries()

        self.test_admin_1 = UserDTO(
            id=10,
            username='admin',
            role='ADMIN'
        )
        self.test_admin_1.set_password('test')

        self.test_technician_1 = UserDTO(
            id=20,
            username='technician',
            role='TECHNICIAN'
        )
        self.test_technician_1.set_password('test')

        self.test_user_1 = UserDTO(
            id=30,
            username='user_1',
            role='USER'
        )
        self.test_user_1.set_password('test')

        self.test_user_2 = UserDTO(
            id=31,
            username='user_2',
            role='USER'
        )
        self.test_user_2.set_password('test')

        self.test_courier_1 = UserDTO(
            id=40,
            username='courier',
            role='COURIER'
        )
        self.test_courier_1.set_password('test')

        self.all_users = [
            self.test_technician_1,
            self.test_admin_1,
            self.test_user_1,
            self.test_user_2,
            self.test_courier_1
        ]

        self.user_mapper = {x.id: x for x in self.all_users}
        self.user_mapper[None] = None  # When user is none, return none
        self.user_mapper[9999] = None  # None existing user

        # some test deliveries
        self.test_delivery_1 = DeliveryDTO(
            id=1,
            type='DELIVERY',
            parcelbox_rebus_id=1,
            user_pickup=self.test_user_1
        )

        self.test_delivery_2 = DeliveryDTO(
            id=2,
            type='DELIVERY',
            parcelbox_rebus_id=2,
            user_pickup=self.test_user_2
        )

        self.test_return_1 = DeliveryDTO(
            id=3,
            type='RETURN',
            parcelbox_rebus_id=10,
            user_delivery=self.test_user_2,
            user_pickup=self.test_courier_1
        )

        self.deliveries = [self.test_delivery_1, self.test_delivery_2]
        self.returns = [self.test_return_1]
        self.all_deliveries = self.deliveries + self.returns

        # setup some users that will be used throughout the tests
        self.login_admin = UserDTO(
            id=0,
            username='ADMIN',
            role='ADMIN',
            pin_code='0000',
            apartment=None,
            accepted_terms=1
        )

        self.login_user = UserDTO(
            id=1,
            username='User 1',
            role='USER',
            pin_code='1111',
            apartment=None,
            language='en',
            accepted_terms=1
        )

    # ----------------------------------------------------------------
    # --- HELPERS
    # ----------------------------------------------------------------

    def verify_delivery_in_output(self, delivery_dto, response):
        resp_dict = json.loads(response)

        if isinstance(resp_dict, dict):
            resp_dict = [resp_dict]

        for delivery_dict in resp_dict:
            if 'return_pickup_code' in delivery_dict:
                del delivery_dict['return_pickup_code']
            if 'user_id_pickup' in delivery_dict:
                delivery_dict['user_pickup'] = self.user_mapper[delivery_dict['user_id_pickup']]
                del delivery_dict['user_id_pickup']
            if 'user_id_delivery' in delivery_dict:
                if delivery_dict['user_id_delivery'] is not None:
                    delivery_dict['user_delivery'] = self.user_mapper[delivery_dict['user_id_delivery']]
                del delivery_dict['user_id_delivery']
            delivery_response_dto = DeliveryDTO(**delivery_dict)
            if delivery_dto == delivery_response_dto:
                return
        self.fail('Could not find the delivery: \n{} \nin the output: \n{}'.format(delivery_dto, resp_dict))

    def verify_delivery_not_in_output(self, delivery_dto, response):
        resp_dict = json.loads(response)

        if isinstance(resp_dict, dict):
            resp_dict = [resp_dict]

        for delivery_dict in resp_dict:
            if 'return_pickup_code' in delivery_dict:
                del delivery_dict['return_pickup_code']
            self.translate_dict_to_dto_input(delivery_dict)
            delivery_response_dto = DeliveryDTO(**delivery_dict)
            if delivery_dto == delivery_response_dto:
                self.fail('Could not find the delivery: \n{} \nin the output: \n{}'.format(delivery_dto, resp_dict))

    def translate_dict_to_dto_input(self, delivery_dict, take_copy=False):
        if take_copy:
            delivery_dict_copy = copy.deepcopy(delivery_dict)
        else:
            # just pass on the delivery 
            delivery_dict_copy = delivery_dict
            
        if 'user_id_pickup' in delivery_dict_copy:
            delivery_dict_copy['user_pickup'] = self.user_mapper[delivery_dict_copy['user_id_pickup']]
            del delivery_dict_copy['user_id_pickup']
        if 'user_id_delivery' in delivery_dict_copy:
            if delivery_dict_copy['user_id_delivery'] is not None:
                delivery_dict_copy['user_delivery'] = self.user_mapper[delivery_dict_copy['user_id_delivery']]
            del delivery_dict_copy['user_id_delivery']
        return delivery_dict_copy

    def get_dto_from_serial(self, delivery_dict):
        if 'return_pickup_code' in delivery_dict:
            del delivery_dict['return_pickup_code']
        delivery_dict_copy = self.translate_dict_to_dto_input(delivery_dict, take_copy=True)
        return DeliveryDTO(**delivery_dict_copy)

    # ----------------------------------------------------------------
    # --- GET
    # ----------------------------------------------------------------

    def test_get_delivery_list(self):
        with mock.patch.object(self.delivery_controller, 'load_deliveries', return_value=self.all_deliveries):
            auth_token = AuthenticationToken(self.login_admin, 'test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_deliveries(auth_token=auth_token)
            for delivery in self.all_deliveries:
                self.verify_delivery_in_output(delivery, response)

    def test_get_delivery_list_normal_user(self):
        with mock.patch.object(self.delivery_controller, 'load_deliveries', return_value=self.all_deliveries):
            auth_token = AuthenticationToken(self.test_user_1, 'test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_deliveries(auth_token=auth_token)
            for delivery in [self.test_delivery_1]:
                self.verify_delivery_in_output(delivery, response)
            for delivery in [self.test_delivery_2, self.test_return_1]:
                self.verify_delivery_not_in_output(delivery, response)

    def test_get_delivery_list_courier(self):
        with mock.patch.object(self.delivery_controller, 'load_deliveries', return_value=self.all_deliveries):
            auth_token = AuthenticationToken(self.test_courier_1, 'test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_deliveries(auth_token=auth_token)
            for delivery in [self.test_delivery_1, self.test_delivery_2]:
                self.verify_delivery_not_in_output(delivery, response)
            for delivery in [self.test_return_1]:
                self.verify_delivery_in_output(delivery, response)

    def test_get_delivery(self):
        with mock.patch.object(self.delivery_controller, 'load_deliveries', return_value=self.all_deliveries):
            auth_token = AuthenticationToken(self.login_admin, 'test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_deliveries(auth_token=auth_token)
            for delivery in self.all_deliveries:
                self.verify_delivery_in_output(delivery, response)

    def test_get_delivery_specific_user(self):
        with mock.patch.object(self.delivery_controller, 'load_deliveries', return_value=self.all_deliveries):
            auth_token = AuthenticationToken(self.test_user_1, 'test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_deliveries(auth_token=auth_token)
            for delivery in [self.test_delivery_1]:
                self.verify_delivery_in_output(delivery, response)
            for delivery in [self.test_return_1, self.test_delivery_2]:
                self.verify_delivery_not_in_output(delivery, response)

    def test_get_delivery_history(self):
        with mock.patch.object(self.delivery_controller, 'load_deliveries', return_value=[self.test_delivery_1]) as load_deliveries_func:
            auth_token = AuthenticationToken(self.test_user_1, 'test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_delivery_history(auth_token=auth_token, user_id=self.test_user_1.id, before_id=0, pagesize=2)
            load_deliveries_func.assert_called_once_with(user_id=self.test_user_1.id, history=True, before_id=0, limit=2, delivery_type=None)
            for delivery in [self.test_delivery_1]:
                self.verify_delivery_in_output(delivery, response)
            for delivery in [self.test_return_1, self.test_delivery_2]:
                self.verify_delivery_not_in_output(delivery, response)

    def test_get_delivery_history_filter(self):
        with mock.patch.object(self.delivery_controller, 'load_deliveries', return_value=[self.test_delivery_1]) as load_deliveries_func:
            auth_token = AuthenticationToken(self.test_user_1, 'test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.get_delivery_history(auth_token=auth_token, user_id=self.test_user_1.id, before_id=0, pagesize=2, delivery_type='DELIVERY')
            load_deliveries_func.assert_called_once_with(user_id=self.test_user_1.id, history=True, before_id=0, limit=2, delivery_type='DELIVERY')
            for delivery in [self.test_delivery_1]:
                self.verify_delivery_in_output(delivery, response)
            for delivery in [self.test_return_1, self.test_delivery_2]:
                self.verify_delivery_not_in_output(delivery, response)

    # ----------------------------------------------------------------
    # --- POST
    # ----------------------------------------------------------------

    def verify_delivery_created(self, delivery_to_create, response):
        resp_dict = json.loads(response)
        for field in delivery_to_create:
            self.assertIn(field, resp_dict)
            delivery_to_create_field = delivery_to_create[field]
            resp_delivery_field = resp_dict[field]
            self.assertEqual(delivery_to_create_field, resp_delivery_field)

    def test_create_delivery_basic(self):
        delivery_to_create = {
            'type': 'DELIVERY',
            'courier_firm': 'TEST',
            'parcelbox_rebus_id': 5,
            'user_id_pickup': self.test_user_1.id
        }
        with mock.patch.object(self.delivery_controller, 'save_delivery') as save_delivery_func, \
                mock.patch.object(self.user_controller, 'load_user', return_value=self.test_user_1):
            delivery_dto_to_save = self.get_dto_from_serial(delivery_to_create)
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.login_admin, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_delivery(auth_token=auth_token,
                                              request_body=delivery_to_create)
            save_delivery_func.assert_called_once_with(delivery_dto_to_save)
            self.verify_delivery_created(delivery_to_create, response)

    def test_create_delivery_normal_user(self):
        delivery_to_create = {
            'type': 'DELIVERY',
            'courier_firm': 'TEST',
            'parcelbox_rebus_id': 5,
            'user_id_pickup': self.test_user_1.id
        }
        with mock.patch.object(self.delivery_controller, 'save_delivery') as save_delivery_func, \
                mock.patch.object(self.user_controller, 'load_user', return_value=self.test_user_1):
            delivery_dto_to_save = self.get_dto_from_serial(delivery_to_create)
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.test_user_1, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_delivery(auth_token=auth_token,
                                              request_body=delivery_to_create)
            save_delivery_func.assert_called_once_with(delivery_dto_to_save)
            self.verify_delivery_created(delivery_to_create, response)

    def test_create_delivery_other_user(self):
        delivery_to_create = {
            'type': 'DELIVERY',
            'courier_firm': 'TEST',
            'parcelbox_rebus_id': 5,
            'user_id_pickup': self.test_user_1.id
        }
        with mock.patch.object(self.delivery_controller, 'save_delivery') as save_delivery_func, \
                mock.patch.object(self.user_controller, 'load_user', return_value=self.test_user_1):
            delivery_dto_to_save = self.get_dto_from_serial(delivery_to_create)
            save_delivery_func.return_value = delivery_dto_to_save
            # save an user with other credentials. this is allowed
            auth_token = AuthenticationToken(user=self.test_user_2, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_delivery(auth_token=auth_token,
                                              request_body=delivery_to_create)
            save_delivery_func.assert_called_once_with(delivery_dto_to_save)
            self.verify_delivery_created(delivery_to_create, response)

    def test_create_delivery_no_auth(self):
        delivery_to_create = {
            'type': 'DELIVERY',
            'courier_firm': 'TEST',
            'parcelbox_rebus_id': 5,
            'user_id_pickup': self.test_user_1.id
        }
        with mock.patch.object(self.delivery_controller, 'save_delivery') as save_delivery_func, \
                mock.patch.object(self.user_controller, 'load_user', return_value=self.test_user_1):
            delivery_dto_to_save = self.get_dto_from_serial(delivery_to_create)
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = None
            response = self.web.post_delivery(auth_token=auth_token,
                                              request_body=delivery_to_create)
            save_delivery_func.assert_called_once_with(delivery_dto_to_save)
            self.verify_delivery_created(delivery_to_create, response)

    def test_create_delivery_return_no_delivery_user(self):
        delivery_to_create = {
            'type': 'RETURN',
            'courier_firm': 'TEST',
            'parcelbox_rebus_id': 5,
            'user_id_pickup': self.test_user_1.id
        }
        with mock.patch.object(self.delivery_controller, 'save_delivery') as save_delivery_func, \
                mock.patch.object(self.user_controller, 'load_user', return_value=self.test_user_1):
            delivery_dto_to_save = self.get_dto_from_serial(delivery_to_create)
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.login_admin, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_delivery(auth_token=auth_token,
                                              request_body=json.dumps(delivery_to_create))
            # assert that there is an response with parse exception
            self.assertIn(ParseException.bytes_message(), response)
            save_delivery_func.assert_not_called()

    def test_create_delivery_wrong_type(self):
        delivery_to_create = {
            'type': 'TEST',
            'courier_firm': 'TEST',
            'parcelbox_rebus_id': 5,
            'user_id_pickup': self.test_user_1.id
        }
        with mock.patch.object(self.delivery_controller, 'save_delivery') as save_delivery_func, \
                mock.patch.object(self.user_controller, 'load_user', return_value=self.test_user_1):
            delivery_dto_to_save = self.get_dto_from_serial(delivery_to_create)
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.login_admin, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_delivery(auth_token=auth_token,
                                              request_body=json.dumps(delivery_to_create))
            # assert that there is an response with parse exception
            self.assertIn(ParseException.bytes_message(), response)
            save_delivery_func.assert_not_called()

    def test_create_delivery_no_parcelbox_id(self):
        delivery_to_create = {
            'type': 'TEST',
            'courier_firm': 'TEST',
            'user_id_pickup': self.test_user_1.id
        }
        with mock.patch.object(self.delivery_controller, 'save_delivery') as save_delivery_func, \
                mock.patch.object(self.user_controller, 'load_user', return_value=self.test_user_1):
            delivery_dto_to_save = self.get_dto_from_serial(delivery_to_create)
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.login_admin, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_delivery(auth_token=auth_token,
                                              request_body=json.dumps(delivery_to_create))
            # assert that there is an response with parse exception
            self.assertIn(ParseException.bytes_message(), response)
            save_delivery_func.assert_not_called()

    def test_create_delivery_wrong_user_id(self):
        delivery_to_create = {
            'type': 'DELIVERY',
            'courier_firm': 'TEST',
            'parcelbox_rebus_id': 5,
            'user_id_pickup': 9999
        }
        with mock.patch.object(self.delivery_controller, 'save_delivery') as save_delivery_func, \
                mock.patch.object(self.user_controller, 'user_id_exists', return_value=False):
            delivery_dto_to_save = self.get_dto_from_serial(delivery_to_create)
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.login_admin, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_delivery(auth_token=auth_token,
                                              request_body=json.dumps(delivery_to_create))
            # assert that there is an response with parse exception
            self.assertIn(ParseException.bytes_message(), response)
            save_delivery_func.assert_not_called()

    def test_create_delivery_empty(self):
        delivery_to_create = {}
        with mock.patch.object(self.delivery_controller, 'save_delivery') as save_delivery_func, \
                mock.patch.object(self.user_controller, 'load_user', return_value=self.test_user_1):
            delivery_dto_to_save = self.get_dto_from_serial(delivery_to_create)
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.login_admin, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.post_delivery(auth_token=auth_token,
                                              request_body=json.dumps(delivery_to_create))
            # assert that there is an response with parse exception
            self.assertIn(ParseException.bytes_message(), response)
            save_delivery_func.assert_not_called()

    # ----------------------------------------------------------------
    # --- PUT
    # ----------------------------------------------------------------

    def assert_delivery_picked_up(self, response):
        # type: (str) -> None
        resp_dict = json.loads(response)
        delivery_dto = self.get_dto_from_serial(resp_dict)
        self.assertIsNotNone(delivery_dto.timestamp_pickup)

    def test_pickup_delivery_admin_auth(self):
        with mock.patch.object(self.delivery_controller, 'pickup_delivery') as save_delivery_func, \
                mock.patch.object(self.delivery_controller, 'load_delivery', return_value=self.test_delivery_1):
            delivery_dto_to_save = self.test_delivery_1
            delivery_dto_to_save.timestamp_pickup = DeliveryController.current_timestamp_to_string_format()
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.login_admin, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.put_delivery_pickup(delivery_id=self.test_delivery_1.id, auth_token=auth_token)
            self.assert_delivery_picked_up(response)

    def test_pickup_delivery_user_auth(self):
        with mock.patch.object(self.delivery_controller, 'pickup_delivery') as save_delivery_func, \
                mock.patch.object(self.delivery_controller, 'load_delivery', return_value=self.test_delivery_1):
            delivery_dto_to_save = self.test_delivery_1
            delivery_dto_to_save.timestamp_pickup = DeliveryController.current_timestamp_to_string_format()
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.test_delivery_1.user_pickup, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.put_delivery_pickup(delivery_id=self.test_delivery_1.id, auth_token=auth_token)
            self.assert_delivery_picked_up(response)

    def test_pickup_delivery_other_user_auth(self):
        with mock.patch.object(self.delivery_controller, 'pickup_delivery') as save_delivery_func, \
                mock.patch.object(self.delivery_controller, 'load_delivery', return_value=self.test_delivery_1):
            delivery_dto_to_save = self.test_delivery_1
            delivery_dto_to_save.timestamp_pickup = DeliveryController.current_timestamp_to_string_format()
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.test_user_2, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.put_delivery_pickup(delivery_id=self.test_delivery_1.id, auth_token=auth_token)
            self.assertIn(UnAuthorizedException.bytes_message(), response)

    def test_pickup_delivery_non_existing_package(self):
        with mock.patch.object(self.delivery_controller, 'pickup_delivery') as save_delivery_func, \
                mock.patch.object(self.delivery_controller, 'load_delivery', return_value=None):
            delivery_dto_to_save = self.test_delivery_1
            delivery_dto_to_save.timestamp_pickup = DeliveryController.current_timestamp_to_string_format()
            save_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.test_user_2, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.put_delivery_pickup(delivery_id=37, auth_token=auth_token)
            self.assertIn(ItemDoesNotExistException.bytes_message(), response)

    def test_pickup_return(self):
        with mock.patch.object(self.delivery_controller, 'pickup_delivery') as pickup_delivery_func, \
                mock.patch.object(self.delivery_controller, 'load_delivery', return_value=self.test_return_1):
            delivery_dto_to_save = self.test_return_1
            delivery_dto_to_save.timestamp_pickup = DeliveryController.current_timestamp_to_string_format()
            pickup_delivery_func.return_value = delivery_dto_to_save
            auth_token = AuthenticationToken(user=self.test_user_2, token='test-token', expire_timestamp=int(time.time() + 3600), login_method=LoginMethod.PASSWORD)
            response = self.web.put_delivery_pickup(delivery_id=self.test_return_1.id, auth_token=auth_token)
            self.assert_delivery_picked_up(response)


class DeliveryApiCherryPyTest(BaseCherryPyUnitTester):
    def setUp(self):
        super(DeliveryApiCherryPyTest, self).setUp()
        self.delivery_controller = mock.Mock(DeliveryController)
        SetUpTestInjections(delivery_controller=self.delivery_controller)
        self.web = Deliveries()
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

        self.test_delivery_1 = DeliveryDTO(
            id=1,
            type='DELIVERY',
            parcelbox_rebus_id=1,
            user_pickup=self.test_user_1
        )

    def test_post_no_body(self):
        with mock.patch.object(self.delivery_controller, 'pickup_delivery') as save_delivery_func, \
                mock.patch.object(self.delivery_controller, 'load_delivery', return_value=self.test_delivery_1):
            delivery_dto_to_save = self.test_delivery_1
            delivery_dto_to_save.timestamp_pickup = DeliveryController.current_timestamp_to_string_format()
            save_delivery_func.return_value = delivery_dto_to_save
            status, headers, response = self.POST('/api/v1/deliveries', login_user=None, body=None)
            self.assertIn(WrongInputParametersException.bytes_message(), response)

    def test_put_no_auth(self):
        with mock.patch.object(self.delivery_controller, 'pickup_delivery') as save_delivery_func, \
                mock.patch.object(self.delivery_controller, 'load_delivery', return_value=self.test_delivery_1):
            delivery_dto_to_save = self.test_delivery_1
            delivery_dto_to_save.timestamp_pickup = DeliveryController.current_timestamp_to_string_format()
            save_delivery_func.return_value = delivery_dto_to_save
            status, headers, response = self.PUT('/api/v1/deliveries/1/pickup', login_user=None, body=None)
            self.assertIn(UnAuthorizedException.bytes_message(), response)
