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
Users api description
"""

import cherrypy
import logging
import ujson as json
import uuid

from gateway.api.serializers import UserSerializer
from gateway.exceptions import WrongInputParametersException, UnAuthorizedException, ItemDoesNotExistException, NotImplementedException
from gateway.models import User
from gateway.user_controller import UserController
from gateway.webservice_v1 import RestAPIEndpoint, openmotics_api_v1, expose, AuthenticationLevel, V1ApiResponse

logger = logging.getLogger(__name__)


@expose
class Users(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/users'

    def __init__(self):
        # type: () -> None
        super(Users, self).__init__()
        # Set a custom route dispatcher in the class so that you have full
        # control over how the routes are defined.
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_users', '',
                                      controller=self, action='get_users',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_user', '/:user_id',
                                      controller=self, action='get_user',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_available_code', '/available_code',
                                      controller=self, action='get_available_code',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_pin_code', '/:user_id/pin',
                                      controller=self, action='get_pin_code',
                                      conditions={'method': ['GET']})
        # --- POST ---
        self.route_dispatcher.connect('post_user', '',
                                      controller=self, action='post_user',
                                      conditions={'method': ['POST']})
        self.route_dispatcher.connect('post_activate_user', '/:user_id/activate',
                                      controller=self, action='post_activate_user',
                                      conditions={'method': ['POST']})
        # --- PUT ---
        self.route_dispatcher.connect('put_user', '/:user_id',
                                      controller=self, action='put_update_user',
                                      conditions={'method': ['PUT']})
        # --- DELETE ---
        self.route_dispatcher.connect('delete_user', '/:user_id',
                                      controller=self, action='delete_user',
                                      conditions={'method': ['DELETE']})

    @openmotics_api_v1(auth=False, pass_role=True, check={'role': str, 'include_inactive': bool})
    def get_users(self, auth_role=None, role=None, include_inactive=False):
        if auth_role is None or auth_role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            users = self.user_controller.load_users(roles=[User.UserRoles.USER], include_inactive=include_inactive)
        else:
            roles = [role] if role is not None else None
            users = self.user_controller.load_users(roles=roles, include_inactive=include_inactive)

        users_serial = [UserSerializer.serialize(user) for user in users]
        return json.dumps(users_serial)

    @openmotics_api_v1(auth=False, pass_role=True)
    def get_user(self, user_id, auth_role=None):
        # return the requested user
        if user_id is None:
            raise WrongInputParametersException('Could not get the user_id from the request')
        user = self.user_controller.load_user(user_id=user_id)
        if user is None:
            raise ItemDoesNotExistException('User with id {} does not exists'.format(user_id))
        # Filter the users when no role is provided or when the role is not admin
        if auth_role is None or auth_role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            if user.role in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
                raise UnAuthorizedException('Cannot request an admin or technician user when not authenticated as one')
        user_serial = UserSerializer.serialize(user)
        return json.dumps(user_serial)

    @openmotics_api_v1(auth=False, auth_level=AuthenticationLevel.HIGH, check={'role': str})
    def get_available_code(self, role):
        roles = [x for x in User.UserRoles.__dict__ if not x.startswith('_')]
        if role not in roles:
            raise WrongInputParametersException('Role needs to be one of {}'.format(roles))
        new_code = self.user_controller.generate_new_pin_code(UserController.PinCodeLength[role])
        return json.dumps({'code': new_code})

    @openmotics_api_v1(auth=True, auth_level=AuthenticationLevel.HIGH, check={'user_id': int},
                       allowed_user_roles=[User.UserRoles.SUPER, User.UserRoles.ADMIN])
    def get_pin_code(self, user_id):
        # type: (int) -> str
        # Authentication: When SUPER, ADMIN or TECHNICIAN, you can request all the pin codes
        user_dto = self.user_controller.load_user(user_id)
        if user_dto is None:
            raise ItemDoesNotExistException('Cannot request the pin code for user_id: {}: User does not exists'.format(user_id))
        return json.dumps({'pin_code': user_dto.pin_code})

    @openmotics_api_v1(auth=False, pass_role=True, expect_body_type='JSON')
    def post_user(self, auth_role, request_body):
        # Authentication:
        # only ADMIN & TECHNICIAN can create new USER, ADMIN, TECHNICIAN user types,
        # anyone can create a new COURIER
        tmp_password = None
        if 'role' not in request_body:
            raise WrongInputParametersException('The role is required to pass when creating a user')
        if 'password' in request_body:
            tmp_password = request_body['password']
            del request_body['password']
        try:
            user_dto = UserSerializer.deserialize(request_body)
        except RuntimeError as ex:
            raise WrongInputParametersException('Could not deserialize user json format: {}'.format(ex))
        if tmp_password is not None:
            user_dto.set_password(tmp_password)

        if 'pin_code' in user_dto.loaded_fields:
            user_dto.pin_code = None
            user_dto.loaded_fields.remove('pin_code')

        if user_dto.username is None:
            user_dto.username = str(uuid.uuid4())
        # add a custom user code
        user_dto.pin_code = str(self.user_controller.generate_new_pin_code(UserController.PinCodeLength[user_dto.role]))
        user_dto.accepted_terms = True
        # Generate a random password as a dummy to fill in the gap
        random_password = uuid.uuid4().hex
        user_dto.set_password(random_password)

        # Authenticated as a technician or admin, creating the user
        if auth_role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            # if the user is not an admin or technician, check if the user to create is a COURIER
            if user_dto.role != User.UserRoles.COURIER:
                raise UnAuthorizedException('As a normal user, you can only create a COURIER user')

        try:
            user_dto_saved = self.user_controller.save_user(user_dto)
        except RuntimeError as e:
            raise WrongInputParametersException('The user could not be saved: {}'.format(e))
        user_dto_serial = UserSerializer.serialize(user_dto_saved)
        # explicitly add the pin code when a new user is created, this way, the generated pin code is known to the user when created.
        user_dto_serial['pin_code'] = user_dto.pin_code
        return json.dumps(user_dto_serial)

    @openmotics_api_v1(auth=False, pass_role=False, expect_body_type='JSON')
    def post_activate_user(self, user_id, request_body):
        # request to activate a certain user
        request_code = request_body.get('pin_code') or request_body.get('rfid_tag')
        if request_code is None:
            raise WrongInputParametersException('when activating, a pin code or rfid tag is expected.')

        user_dto = self.user_controller.load_user(user_id)
        is_rfid = 'rfid_tag' in request_code
        if not is_rfid and request_code != user_dto.pin_code:
            raise UnAuthorizedException('pin code is not correct to authenticate the user')
        elif is_rfid:
            # TODO: Add the rfid check
            raise NotImplementedException('Rfid token check not implemented yet')
        # if all checks are passed, activate the user
        self.user_controller.activate_user(user_id)
        return 'OK'

    @openmotics_api_v1(auth=True, pass_role=False, pass_token=True, pass_security_level=True, expect_body_type='JSON', check={'user_id': int})
    def put_update_user(self, user_id, auth_token, auth_security_level, request_body=None):
        user_json = request_body
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
            if auth_token.user.id != user_id:
                raise UnAuthorizedException('As a non admin or technician user, you cannot change another user. Requested user_id: {}, authenticated as: {}'.format(user_id, auth_token.user.id))

        # check if the pin code or rfid tag is changed
        if 'pin_code' in user_json or 'rfid' in user_json:
            if auth_security_level is not AuthenticationLevel.HIGH:
                raise UnAuthorizedException('Cannot change the pin code or rfid data: You need a HIGH security level')

        user_dto_orig = self.user_controller.load_user(user_id, clear_password=False)
        user_dto = UserSerializer.deserialize(user_json)
        # only allow a subset of fields to be altered
        for field in ['first_name', 'last_name', 'pin_code', 'language', 'apartment', 'email']:
            if field in user_dto.loaded_fields:
                setattr(user_dto_orig, field, getattr(user_dto, field))
        saved_user = self.user_controller.save_user(user_dto_orig)
        saved_user.clear_password()
        return json.dumps(UserSerializer.serialize(saved_user))

    @openmotics_api_v1(auth=False, pass_role=False, pass_token=True)
    def delete_user(self, user_id, auth_token=None):
        user_to_delete_dto = self.user_controller.load_user(user_id)
        if user_to_delete_dto is None:
            raise ItemDoesNotExistException('Cannot delete an user that does not exists')

        if auth_token is None:
            if user_to_delete_dto.role != User.UserRoles.COURIER:
                raise UnAuthorizedException('As a non logged in user, you only can delete a Courier type')
        else:
            if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER]:
                raise UnAuthorizedException('As a non admin or technician user, you cannot delete another user')

        self.user_controller.remove_user(user_to_delete_dto)
        return V1ApiResponse(status_code=204, response_headers=None, body=None)
