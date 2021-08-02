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
Apartments api description
"""

import cherrypy
import logging
import ujson as json

from ioc import INJECTED, Inject
from gateway.api.serializers import ApartmentSerializer
from gateway.apartment_controller import ApartmentController
from gateway.dto import ApartmentDTO
from gateway.exceptions import WrongInputParametersException, UnAuthorizedException, ItemDoesNotExistException
from gateway.models import User
from gateway.webservice_v1 import RestAPIEndpoint, openmotics_api_v1, expose

logger = logging.getLogger(__name__)


@expose
class Apartments(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/apartments'

    @Inject
    def __init__(self, apartment_controller=INJECTED):
        # type: (ApartmentController) -> None
        super(Apartments, self).__init__()
        self.apartment_controller = apartment_controller
        # Set a custom route dispatcher in the class so that you have full
        # control over how the routes are defined.
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_apartment', '',
                                      controller=self, action='get_apartments',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_apartment', '/:apartment_id',
                                      controller=self, action='get_apartment',
                                      conditions={'method': ['GET']})
        # --- POST ---
        self.route_dispatcher.connect('post_apartment', '',
                                      controller=self, action='post_apartment',
                                      conditions={'method': ['POST']})
        self.route_dispatcher.connect('post_apartment_list', '/list',
                                      controller=self, action='post_apartments',
                                      conditions={'method': ['POST']})
        # --- PUT ---
        self.route_dispatcher.connect('put_apartments', '',
                                      controller=self, action='put_apartments',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_apartment', '/:apartment_id',
                                      controller=self, action='put_apartment',
                                      conditions={'method': ['PUT']})
        # --- DELETE ---
        self.route_dispatcher.connect('delete_apartment', '/:apartment_id',
                                      controller=self, action='delete_apartment',
                                      conditions={'method': ['DELETE']})

    @openmotics_api_v1(auth=False, pass_role=False, pass_token=False)
    def get_apartments(self):
        apartments = self.apartment_controller.load_apartments()
        apartments_serial = []
        for apartment in apartments:
            apartments_serial.append(ApartmentSerializer.serialize(apartment))
        return json.dumps(apartments_serial)

    @openmotics_api_v1(auth=False, pass_role=False, pass_token=False)
    def get_apartment(self, apartment_id):
        apartment_dto = self.apartment_controller.load_apartment(apartment_id)
        if apartment_dto is None:
            raise ItemDoesNotExistException('Apartment with id {} does not exists'.format(apartment_id))
        apartment_serial = ApartmentSerializer.serialize(apartment_dto)
        return json.dumps(apartment_serial)

    @openmotics_api_v1(auth=True, pass_role=False, pass_token=False,
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER],
                       expect_body_type='JSON')
    def post_apartments(self, request_body):
        to_create_apartments = []
        for apartment in request_body:
            apartment_dto = ApartmentSerializer.deserialize(apartment)
            if 'id' in apartment_dto.loaded_fields:
                raise WrongInputParametersException('The apartments cannot have an ID set when creating a new apartment')
            if apartment_dto is None:
                raise WrongInputParametersException('Could not parse the json body: Could not parse apartment: {}'.format(apartment))
            to_create_apartments.append(apartment_dto)

        apartments_serial = []
        for apartment in to_create_apartments:
            apartment_dto = self.apartment_controller.save_apartment(apartment)
            apartments_serial.append(ApartmentSerializer.serialize(apartment_dto))
        return json.dumps(apartments_serial)

    @openmotics_api_v1(auth=True, pass_role=False, pass_token=False,
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER],
                       expect_body_type='JSON')
    def post_apartment(self, request_body=None):
        apartment_deserialized = ApartmentSerializer.deserialize(request_body)
        apartment_dto = self.apartment_controller.save_apartment(apartment_deserialized)
        if 'id' in apartment_dto.loaded_fields:
            raise WrongInputParametersException('The apartments cannot have an ID set when creating a new apartment')
        if apartment_dto is None:
            raise ItemDoesNotExistException('Could not create the apartment: Could not load after creation')
        apartment_serial = ApartmentSerializer.serialize(apartment_dto)
        return json.dumps(apartment_serial)

    @openmotics_api_v1(auth=True, pass_role=False, pass_token=False,
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER],
                       expect_body_type='JSON')
    def put_apartment(self, apartment_id, request_body):
        try:
            apartment_dto = ApartmentSerializer.deserialize(request_body)
            apartment_dto.id = apartment_id
        except Exception:
            raise WrongInputParametersException('Could not parse the json body into an apartment object')
        apartment_dto = self.apartment_controller.update_apartment(apartment_dto)
        return json.dumps(ApartmentSerializer.serialize(apartment_dto))

    @openmotics_api_v1(auth=True, pass_role=False, pass_token=False,
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER],
                       expect_body_type='JSON')
    def put_apartments(self, request_body):
        apartments_to_update = []
        for apartment in request_body:
            apartment_dto = ApartmentSerializer.deserialize(apartment)
            if 'id' not in apartment_dto.loaded_fields or apartment_dto.id is None:
                raise WrongInputParametersException('The ID is needed to know which apartment to update.')
            apartments_to_update.append(apartment_dto)

        updated_apartments = []
        for apartment in apartments_to_update:
            apartment_dto = self.apartment_controller.update_apartment(apartment)
            updated_apartments.append(apartment_dto)
        return json.dumps([ApartmentSerializer.serialize(apartment_dto) for apartment_dto in updated_apartments])

    @openmotics_api_v1(auth=True, pass_role=True,
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER])
    def delete_apartment(self, apartment_id):
        apartment_dto = ApartmentDTO(id=apartment_id)
        self.apartment_controller.delete_apartment(apartment_dto)
        return 'OK'
