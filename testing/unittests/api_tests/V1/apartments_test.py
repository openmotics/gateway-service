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
import json

import mock

import debug_ignore
from gateway.dto import ApartmentDTO, UserDTO
from gateway.exceptions import *
from gateway.apartment_controller import ApartmentController
from gateway.webservice_v1 import Apartments

from .base_test import BaseCherryPyUnitTester

from ioc import SetTestMode, SetUpTestInjections


class ApiApartmentsTests(BaseCherryPyUnitTester):

    @debug_ignore.debugmethod
    def setUp(self):
        super(ApiApartmentsTests, self).setUp()

        # some test apartments
        self.test_apartment_1 = ApartmentDTO(
            id=1,
            name='Test-Apartment-1',
            mailbox_rebus_id=1,
            doorbell_rebus_id=1
        )
        self.test_apartment_2 = ApartmentDTO(
            id=2,
            name='Test-Apartment-2',
            mailbox_rebus_id=2,
            doorbell_rebus_id=2
        )

        self.test_apartment_3 = ApartmentDTO(
            id=3,
            name=None,
            mailbox_rebus_id=1,
            doorbell_rebus_id=1
        )

        self.complete_apartments = [self.test_apartment_1, self.test_apartment_2]
        self.incomplete_apartments = [self.test_apartment_3]
        self.all_apartments = self.complete_apartments + self.incomplete_apartments
        # setup some users that will be used throughout the tests
        self.admin_user = UserDTO(
            id=0,
            username='ADMIN',
            role='ADMIN',
            pin_code='0000',
            apartment=None,
            accepted_terms=1
        )

        self.normal_user_1 = UserDTO(
            id=1,
            username='User 1',
            role='USER',
            pin_code='1111',
            apartment=None,
            language='English',
            accepted_terms=1
        )

        self.apartment_controller = mock.Mock(ApartmentController)
        SetUpTestInjections(apartment_controller=self.apartment_controller)
        self.web = Apartments()
        cherrypy.tree.mount(root=self.web,
                            script_name=self.web.API_ENDPOINT,
                            config={'/':  {'request.dispatch': self.web.route_dispatcher}})

    # ----------------------------------------------------------------
    # --- HELPERS
    # ----------------------------------------------------------------

    def verify_apartment_in_output(self, apartment_dto, response):
        resp_dict = json.loads(response)

        if isinstance(resp_dict, dict):
            resp_dict = [resp_dict]

        for apartment_dict in resp_dict:
            apartment_dto_response = ApartmentDTO(**apartment_dict)
            if apartment_dto == apartment_dto_response:
                return

        self.fail('Could not find the apartment: \n{} \nin the output: \n{}'.format(apartment_dto, resp_dict))

    def verify_apartment_not_in_output(self, apartment_dto, response):
        resp_dict = json.loads(response)

        if isinstance(resp_dict, dict):
            resp_dict = [resp_dict]

        for apartment_dict in resp_dict:
            apartment_dto_response = ApartmentDTO(**apartment_dict)
            if apartment_dto == apartment_dto_response:
                self.fail('Could find the apartment: \n{} \nin the output: \n{}'.format(apartment_dto, resp_dict))
        return

    # ----------------------------------------------------------------
    # --- GET
    # ----------------------------------------------------------------

    def test_get_apartment_list(self):
        with mock.patch.object(self.apartment_controller, 'load_apartments', return_value=self.all_apartments):
            status, headers, body = self.GET('/api/v1/apartments', login_user=None)
            self.assertStatus('200 OK')
            for apartment in self.all_apartments:
                self.verify_apartment_in_output(apartment, body)

    def test_get_apartment(self):
        with mock.patch.object(self.apartment_controller, 'load_apartment', return_value=self.test_apartment_1):
            status, headers, body = self.GET('/api/v1/apartments/1', login_user=None)
            self.verify_apartment_in_output(self.test_apartment_1, body)
            self.verify_apartment_not_in_output(self.test_apartment_2, body)

    # ----------------------------------------------------------------
    # --- POST
    # ----------------------------------------------------------------

    def verify_apartment_created(self, apartment_to_create, response):
        resp_dict = json.loads(response)
        for field in apartment_to_create:
            self.assertIn(field, resp_dict)
            apartment_to_create_field = apartment_to_create[field]
            resp_apartment_field = resp_dict[field]
            self.assertEqual(apartment_to_create_field, resp_apartment_field)

    def test_create_apartment_only_name(self):
        apartment_to_create = {
            'name': 'Test',
            'mailbox_rebus_id': 37,
            'doorbell_rebus_id': 38,
        }
        with mock.patch.object(self.apartment_controller, 'save_apartment') as save_apartment_func:
            apartment_dto_to_save = ApartmentDTO(**apartment_to_create)
            save_apartment_func.return_value = apartment_dto_to_save
            body = json.dumps(apartment_to_create)
            status, headers, body = self.POST('/api/v1/apartments', login_user=self.admin_user, body=body)
            save_apartment_func.assert_called_once_with(apartment_dto_to_save)
            self.verify_apartment_created(apartment_to_create, body)

    def test_create_apartment_empty(self):
        apartment_to_create = {}
        with mock.patch.object(self.apartment_controller, 'save_apartment') as save_apartment_func:
            exception_message = 'TEST_EXCEPTION'
            save_apartment_func.side_effect = ValueError(exception_message)
            status, headers, body = self.POST('/api/v1/apartments', login_user=self.admin_user, body=json.dumps(apartment_to_create))
            self.assertTrue(bytes(exception_message.encode('utf-8')) in body)

    def test_create_apartment_empty_list(self):
        apartment_to_create = []
        with mock.patch.object(self.apartment_controller, 'save_apartment') as save_apartment_func:
            exception_message = 'TEST_EXCEPTION'
            save_apartment_func.side_effect = ValueError(exception_message)
            status, headers, body = self.POST('/api/v1/apartments/list', login_user=self.admin_user, body=json.dumps(apartment_to_create))
            self.assertEqual(b'[]', body)

    def test_create_apartment_no_body(self):
        with mock.patch.object(self.apartment_controller, 'save_apartment') as save_apartment_func:
            exception_message = 'TEST_EXCEPTION'
            save_apartment_func.side_effect = RuntimeError(exception_message)
            status, headers, body = self.POST('/api/v1/apartments', login_user=self.admin_user, body=None)
            self.assertTrue(WrongInputParametersException.bytes_message() in body)

    def test_create_apartment_no_body_list(self):
        with mock.patch.object(self.apartment_controller, 'save_apartment') as save_apartment_func:
            exception_message = 'TEST_EXCEPTION'
            save_apartment_func.side_effect = RuntimeError(exception_message)
            status, headers, body = self.POST('/api/v1/apartments/list', login_user=self.admin_user, body=None)
            self.assertTrue(WrongInputParametersException.bytes_message() in body)

    def test_create_apartment_not_allowed(self):
        apartment_to_create = {
            'name': 'Test',
            'mailbox_rebus_id': 37,
            'doorbell_rebus_id': 38,
        }
        with mock.patch.object(self.apartment_controller, 'save_apartment') as save_apartment_func:
            apartment_dto_to_save = ApartmentDTO(**apartment_to_create)
            save_apartment_func.return_value = apartment_dto_to_save
            status, headers, body = self.POST('/api/v1/apartments', login_user=self.normal_user_1, body=json.dumps(apartment_to_create))
            self.assertTrue(UnAuthorizedException.bytes_message() in body)

    def test_create_apartment_id_filled_in(self):
        apartment_to_create = {
            'id': 5,
            'name': 'Test',
            'mailbox_rebus_id': 37,
            'doorbell_rebus_id': 38,
        }
        with mock.patch.object(self.apartment_controller, 'save_apartment') as save_apartment_func:
            apartment_dto_to_save = ApartmentDTO(**apartment_to_create)
            save_apartment_func.return_value = apartment_dto_to_save
            status, headers, body = self.POST('/api/v1/apartments', login_user=self.admin_user, body=json.dumps(apartment_to_create))
            self.assertTrue(WrongInputParametersException.bytes_message() in body)

    def test_create_apartment_id_filled_in_list(self):
        apartment_to_create = [{
            'id': 5,
            'name': 'Test',
            'mailbox_rebus_id': 37,
            'doorbell_rebus_id': 38,
        }]
        with mock.patch.object(self.apartment_controller, 'save_apartment') as save_apartment_func:
            apartment_dto_to_save = ApartmentDTO(**apartment_to_create[0])
            save_apartment_func.return_value = apartment_dto_to_save
            status, headers, body = self.POST('/api/v1/apartments/list', login_user=self.admin_user, body=json.dumps(apartment_to_create))
            self.assertTrue(WrongInputParametersException.bytes_message() in body)

    # ----------------------------------------------------------------
    # --- PUT
    # ----------------------------------------------------------------

    def test_update_apartment(self):
        apartment_to_update = {
            'name': 'Updated_name',
            'mailbox_rebus_id': 37,
            'doorbell_rebus_id': 38,
        }
        # Change the apartment so that it will be correctly loaded
        self.test_apartment_1.name = apartment_to_update['name']
        with mock.patch.object(self.apartment_controller, 'update_apartment', return_value=self.test_apartment_1) as update_apartment_func:
            status, headers, body = self.PUT('/api/v1/apartments/1', login_user=self.admin_user, body=json.dumps(apartment_to_update))
            resp_dict = json.loads(body)
            apartment_dto_response = ApartmentDTO(**resp_dict)
            self.assertEqual(self.test_apartment_1, apartment_dto_response)

    def test_update_apartment_wrong_permission(self):
        apartment_to_update = {
            'name': 'Updated_name',
            'mailbox_rebus_id': 37,
            'doorbell_rebus_id': 38,
        }
        # Change the apartment so that it will be correctly loaded
        self.test_apartment_1.name = apartment_to_update['name']
        with mock.patch.object(self.apartment_controller, 'update_apartment', return_value=self.test_apartment_1) as update_apartment_func:
            status, headers, body = self.PUT('/api/v1/apartments/1', login_user=self.normal_user_1, body=json.dumps(apartment_to_update))
            self.assertTrue(UnAuthorizedException.bytes_message() in body)

    def test_update_apartment_empty_body(self):
        with mock.patch.object(self.apartment_controller, 'update_apartment', return_value=self.test_apartment_1) as update_apartment_func:
            status, headers, body = self.PUT('/api/v1/apartments/1', login_user=self.admin_user, body=None)
            self.assertTrue(WrongInputParametersException.bytes_message() in body)

    # ----------------------------------------------------------------
    # --- DELETE
    # ----------------------------------------------------------------

    def test_delete_apartment(self):
        with mock.patch.object(self.apartment_controller, 'delete_apartment') as delete_apartment_func:
            status, headers, body = self.DELETE('/api/v1/apartments/2', login_user=self.admin_user)
            self.assertEqual(b'OK', body)

    def test_delete_apartment_unauthorized(self):
        with mock.patch.object(self.apartment_controller, 'delete_apartment') as delete_apartment_func:
            status, headers, body = self.DELETE('/api/v1/apartments/2', login_user=self.normal_user_1)
            self.assertTrue(UnAuthorizedException.bytes_message() in body)

