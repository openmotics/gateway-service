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

""" Includes the WebService_v1 class """

from __future__ import absolute_import
import base64
import uuid

import cherrypy
import logging
import ujson as json
import time

from ioc import INJECTED, Inject, Injectable, Singleton
from gateway.api.serializers.apartment import ApartmentSerializer
from gateway.api.serializers.user import UserSerializer
from gateway.dto import ApartmentDTO
from gateway.exceptions import *
from gateway.models import User
from gateway.webservice import params_handler

if False:  # MyPy
    from gateway.apartment_controller import ApartmentController
    from gateway.authentication_controller import AuthenticationToken
    from gateway.user_controller import UserController
    from gateway.webservice import WebService
    from typing import Optional, List

logger = logging.getLogger("openmotics")

# ------------------------
#  api decorator
# ------------------------

# api decorator
def _openmotics_api_v1(f):
    def wrapper(*args, **kwargs):
        start = time.time()
        timings = {}
        status = 200  # OK
        try:
            data = f(*args, **kwargs)
        except cherrypy.HTTPError as ex:
            status = ex.status
            data = ex._message
        except UnAuthorizedException as ex:
            status = 401
            data = ex.message
        except ForbiddenException as ex:
            status = 400
            data = ex.message
        except ItemDoesNotExistException as ex:
            status = 404
            data = ex.message
        except WrongInputParametersException as ex:
            status = 400
            data = ex.message
        except ParseException as ex:
            status = 400
            data = ex.message
        except TimeOutException as ex:
            status = 500
            data = ex.message
        except InvalidOperationException as ex:
            status = 409
            data = ex.message
        except NotImplementedException as ex:
            status = 503
            data = ex.message
        except Exception as ex:
            status = 500
            data = ex
            logger.error('General Error occurred during api call: {}'.format(data))
            import traceback
            print(traceback.print_exc())

        timings['process'] = ('Processing', time.time() - start)
        serialization_start = time.time()
        contents = str(data)
        timings['serialization'] = 'Serialization', time.time() - serialization_start
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.headers['Server-Timing'] = ','.join(['{0}={1}; "{2}"'.format(key, value[1] * 1000, value[0])
                                                               for key, value in timings.items()])
        cherrypy.response.status = status
        return contents.encode()
    return wrapper


def authentication_handler_v1(pass_token=False, pass_role=False, throw_error=True):
    request = cherrypy.request
    if request.method == 'OPTIONS':
        return
    try:
        token = None
        # check if token is passed with the params
        if 'token' in request.params:
            token = request.params.pop('token')
        # check if the token is passed as a Bearer token in the headers
        if token is None:
            header = request.headers.get('Authorization')
            if header is not None and 'Bearer ' in header:
                token = header.replace('Bearer ', '')
        # check if hte token is passed as a web-socket Bearer token
        if token is None:
            header = request.headers.get('Sec-WebSocket-Protocol')
            if header is not None and 'authorization.bearer.' in header:
                unpadded_base64_token = header.replace('authorization.bearer.', '')
                base64_token = unpadded_base64_token + '=' * (-len(unpadded_base64_token) % 4)
                try:
                    token = base64.decodestring(base64_token).decode('utf-8')
                except Exception:
                    pass
        _self = request.handler.callable.__self__
        # Fetch the checkToken function that is placed under the main webservice or under the plugin webinterface.
        check_token = _self._user_controller.authentication_controller.check_token
        checked_token = check_token(token)  # type: Optional[AuthenticationToken]
        if checked_token is None and throw_error:
            raise UnAuthorizedException('Unauthorized API call')
        if pass_token is True:
            request.params['token'] = checked_token
        if pass_role is True:
            if checked_token is not None:
                request.params['role'] = checked_token.user.role
            else:
                request.params['role'] = None
    except UnAuthorizedException as ex:
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.status = 401  # Unauthorized
        contents = ex.message
        cherrypy.response.body = contents.encode()
        # do not handle the request, just return the unauthorized message
        request.handler = None


# Assign the v1 authentication handler
cherrypy.tools.authenticated_v1 = cherrypy.Tool('before_handler', authentication_handler_v1)
cherrypy.tools.params_v1 = cherrypy.Tool('before_handler', params_handler)


def openmotics_api_v1(_func=None, check=None, auth=False, pass_token=False, pass_role=False):
    def decorator_openmotics_api_v1(func):
        func = _openmotics_api_v1(func)  # First layer decorator
        if auth is True:
            # Second layer decorator
            func = cherrypy.tools.authenticated_v1(pass_token=pass_token, pass_role=pass_role)(func)
        elif pass_token or pass_role:
            func = cherrypy.tools.authenticated_v1(pass_token=pass_token, pass_role=pass_role, throw_error=False)(func)
        func = cherrypy.tools.params(**(check or {}))(func)
        return func
    if _func is None:
        return decorator_openmotics_api_v1
    else:
        return decorator_openmotics_api_v1(_func)


# ----------------------------
# eSafe API
# ----------------------------

class RestAPIEndpoint(object):
    exposed = True  # Cherrypy specific flag to set the class as exposed
    API_ENDPOINT = None  # type: Optional[str]

    @Inject
    def __init__(self, user_controller=INJECTED):
        # type: (UserController) -> None
        self._user_controller = user_controller

    def GET(self):
        raise NotImplementedException

    def POST(self):
        raise NotImplementedException

    def PUT(self):
        raise NotImplementedException

    def DELETE(self):
        raise NotImplementedException

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return 'Rest Endpoint class: "{}"'.format(self.__class__.__name__)


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
        # --- POST ---
        self.route_dispatcher.connect('post_user', '',
                                      controller=self, action='post_user',
                                      conditions={'method': ['POST']})
        self.route_dispatcher.connect('post_activate_user', '/activate/:user_id',
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

    @openmotics_api_v1(auth=False, pass_role=True)
    def get_users(self, role=None):
        users = self._user_controller.load_users()
        # Filter the users when no role is provided or when the role is not admin
        if role is None or role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            users = [user for user in users if user.role in [User.UserRoles.USER]]
        users_serial = [UserSerializer.serialize(user) for user in users]
        return json.dumps(users_serial)

    @openmotics_api_v1(auth=False, pass_role=True)
    def get_user(self, user_id, role=None):
        # return the requested user
        if user_id is None:
            raise WrongInputParametersException('Could not get the user_id from the request')
        user = self._user_controller.load_user(user_id=user_id)
        if user is None:
            raise ItemDoesNotExistException('User with id {} does not exists'.format(user_id))
        # Filter the users when no role is provided or when the role is not admin
        if role is None or role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            if user.role in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
                raise UnAuthorizedException('Cannot request an admin or technician user when not authenticated as one')
        user_serial = UserSerializer.serialize(user)
        return json.dumps(user_serial)

    @openmotics_api_v1(auth=False, pass_role=False)
    def get_available_code(self):
        api_secret = cherrypy.request.headers.get('X-API-Secret')
        if api_secret is None:
            raise UnAuthorizedException('Cannot create a new available code without the X-API-Secret')
        elif not self._user_controller.authentication_controller.check_api_secret(api_secret):
            raise UnAuthorizedException('X-API-Secret is incorrect')
        return str(self._user_controller.generate_new_pin_code())

    @openmotics_api_v1(auth=False, pass_role=True)
    def post_user(self, role=None, request_body=None):
        # Authentication:
        # only ADMIN & TECHNICIAN can create new USER, ADMIN, TECHNICIAN user types,
        # anyone can create a new COURIER
        if request_body is None:
            raise WrongInputParametersException('The request body is empty')
        try:
            user_json = json.loads(request_body)
        except Exception:
            raise ParseException('Could not parse the user json input')
        tmp_password = None
        if 'role' not in user_json:
            raise WrongInputParametersException('The role is required to pass when creating a user')
        if 'password' in user_json:
            tmp_password = user_json['password']
            del user_json['password']
        user_dto = UserSerializer.deserialize(user_json)
        if tmp_password is not None:
            user_dto.set_password(tmp_password)

        if 'pin_code' in user_dto.loaded_fields:
            user_dto.pin_code = None
            user_dto.loaded_fields.remove('pin_code')

        user_dto.username = uuid.uuid4().hex
        # add a custom user code
        user_dto.pin_code = str(self._user_controller.generate_new_pin_code())
        # Generate a random password as a dummy to fill in the gap
        random_password = uuid.uuid4().hex
        user_dto.set_password(random_password)

        # Authenticated as a technician or admin, creating the user
        if role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            # if the user is not an admin or technician, check if the user to create is a COURIER
            if user_dto.role != User.UserRoles.COURIER:
                raise UnAuthorizedException('As a normal user, you can only create a COURIER user')

        try:
            user_dto_saved = self._user_controller.save_user(user_dto)
        except RuntimeError as e:
            raise WrongInputParametersException('The user could not be saved: {}'.format(e))
        return json.dumps(UserSerializer.serialize(user_dto_saved))

    @openmotics_api_v1(auth=False, pass_role=False)
    def post_activate_user(self, user_id, request_body=None):
        # request to activate a certain user
        if request_body is None:
            raise WrongInputParametersException('Body expected when calling the activate function')

        try:
            body_json = json.loads(request_body)
        except Exception:
            raise ParseException('Could not parse the user json input')

        request_code = body_json.get('code') or body_json.get('rfid_tag')
        if request_code is None:
            raise WrongInputParametersException('when activating, a pin code or rfid tag is expected.')

        user_dto = self._user_controller.load_user(user_id)
        is_rfid = 'rfid_tag' in request_code
        if not is_rfid and request_code != user_dto.pin_code:
            raise UnAuthorizedException('pin code is not correct to authenticate the user')
        elif is_rfid:
            # TODO: Add the rfid check
            raise NotImplementedException('Rfid token check not implemented yet')
        # if all checks are passed, activate the user
        self._user_controller.activate_user(user_id)
        return 'OK'

    @openmotics_api_v1(auth=False, pass_role=False, pass_token=True)
    def put_update_user(self, user_id, token=None, request_body=None, **kwargs):
        if token is None:
            raise UnAuthorizedException('Cannot change a user without being logged in')
        if request_body is None:
            raise WrongInputParametersException('The request body is empty')
        try:
            user_json = json.loads(request_body)
        except Exception:
            raise ParseException('Could not parse the user json input')

        if token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            if token.user.id != user_id:
                raise UnAuthorizedException('As a non admin or technician user, you cannot change another user')

        # check if the pin code or rfid tag is changed
        if 'pin_code' in user_json or 'rfid' in user_json:
            api_secret = kwargs.get('X-API-Secret')
            if api_secret is None:
                raise UnAuthorizedException('Cannot change the pin code or rfid data without the api secret')
            if not self._user_controller.authentication_controller.check_api_secret(api_secret):
                raise UnAuthorizedException('The api secret is not valid')

        user_dto_orig = self._user_controller.load_user(user_id)
        user_dto = UserSerializer.deserialize(user_json)
        for field in ['first_name', 'last_name', 'pin_code', 'language', 'apartment']:
            if field in user_dto.loaded_fields:
                setattr(user_dto_orig, field, getattr(user_dto, field))
        self._user_controller.save_user(user_dto_orig)
        user_loaded = self._user_controller.load_user(user_id)
        return json.dumps(UserSerializer.serialize(user_loaded))

    @openmotics_api_v1(auth=False, pass_role=False, pass_token=True)
    def delete_user(self, user_id, token=None):
        user_to_delete_dto = self._user_controller.load_user(user_id)
        if user_to_delete_dto is None:
            raise ItemDoesNotExistException('Cannot delete an user that does not exists')

        if token is None:
            if user_to_delete_dto.role != User.UserRoles.COURIER:
                raise UnAuthorizedException('As a non logged in user, you only can delete a Courier type')
        else:
            if token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
                raise UnAuthorizedException('As a non admin or technician user, you cannot delete another user')

        self._user_controller.remove_user(user_to_delete_dto)
        return 'OK'


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

    @openmotics_api_v1(auth=True, pass_role=True, pass_token=False)
    def post_apartments(self, request_body=None, role=None):
        if role is None:
            raise UnAuthorizedException('Authentication is needed when creating an apartment')
        if role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            raise UnAuthorizedException('You need to be logged in as an admin or technician to create an apartment')

        if request_body is None:
            raise WrongInputParametersException('Body is empty')

        try:
            body_dict = json.loads(request_body)
        except Exception:
            raise WrongInputParametersException('Could not parse the json body')

        # First save the apartments in a list to create them later
        # this will prevent that some apartments are created when there is a parse error in the middle of the json structure
        to_create_apartments = []
        for apartment in body_dict:
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

    @openmotics_api_v1(auth=True, pass_role=True, pass_token=False)
    def post_apartment(self, request_body=None, role=None):
        if role is None:
            raise UnAuthorizedException('Authentication is needed when creating an apartment')
        if role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            raise UnAuthorizedException('You need to be logged in as an admin or technician to create an apartment')

        if request_body is None:
            raise WrongInputParametersException('Body is empty')

        try:
            body_dict = json.loads(request_body)
        except Exception:
            raise WrongInputParametersException('Could not parse the json body')
        apartment_deserialized = ApartmentSerializer.deserialize(body_dict)
        apartment_dto = self.apartment_controller.save_apartment(apartment_deserialized)
        if 'id' in apartment_dto.loaded_fields:
            raise WrongInputParametersException('The apartments cannot have an ID set when creating a new apartment')
        if apartment_dto is None:
            raise ItemDoesNotExistException('Could not create the apartment: Could not load after creation')
        apartment_serial = ApartmentSerializer.serialize(apartment_dto)
        return json.dumps(apartment_serial)

    @openmotics_api_v1(auth=True, pass_role=True, pass_token=False)
    def put_apartment(self, apartment_id, request_body=None, role=None):
        if role is None:
            raise UnAuthorizedException('Authentication is needed when updating an apartment')
        if role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            raise UnAuthorizedException('You need to be logged in as an admin or technician to update an apartment')

        if request_body is None:
            raise WrongInputParametersException('Body is empty')

        try:
            body_dict = json.loads(request_body)
            apartment_dto = ApartmentSerializer.deserialize(body_dict)
            apartment_dto.id = apartment_id
        except Exception:
            raise WrongInputParametersException('Could not parse the json body')
        apartment_dto = self.apartment_controller.update_apartment(apartment_dto)
        return json.dumps(ApartmentSerializer.serialize(apartment_dto))

    @openmotics_api_v1(auth=True, pass_role=True, pass_token=False)
    def put_apartments(self, request_body=None, role=None):
        if role is None:
            raise UnAuthorizedException('Authentication is needed when updating an apartment')
        if role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            raise UnAuthorizedException('You need to be logged in as an admin or technician to update an apartment')

        if request_body is None:
            raise WrongInputParametersException('Body is empty')

        apartments_to_update = []
        try:
            body_dict = json.loads(request_body)
        except Exception:
            raise WrongInputParametersException('Could not parse the json body')
        for apartment in body_dict:
            apartment_dto = ApartmentSerializer.deserialize(apartment)
            if 'id' not in apartment_dto.loaded_fields or apartment_dto.id is None:
                raise WrongInputParametersException('The ID is needed to know which apartment to update.')
            apartments_to_update.append(apartment_dto)

        updated_apartments = []
        for apartment in apartments_to_update:
            apartment_dto = self.apartment_controller.update_apartment(apartment)
            updated_apartments.append(apartment_dto)
        return json.dumps([ApartmentSerializer.serialize(apartment_dto) for apartment_dto in updated_apartments])

    @openmotics_api_v1(auth=True, pass_role=True, pass_token=False)
    def delete_apartment(self, apartment_id, role=None):
        if role is None:
            raise UnAuthorizedException('Authentication is needed when updating an apartment')
        if role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            raise UnAuthorizedException('You need to be logged in as an admin or technician to update an apartment')
        apartment_dto = ApartmentDTO(id=apartment_id)
        self.apartment_controller.delete_apartment(apartment_dto)
        return 'OK'


@Injectable.named('web_service_v1')
@Singleton
class WebServiceV1(object):
    def __init__(self, web_service=INJECTED):
        # type: (Optional[WebService]) -> None
        self.web_service = web_service
        self.endpoints = [
            Users(),
            Apartments()
        ]

    def start(self):
        self.add_api_tree()

    def stop(self):
        pass

    def set_web_service(self, web_service):
        # type: (WebService) -> None
        self.web_service = web_service

    def add_api_tree(self):
        mounts = []
        if self.endpoints is None:
            raise AttributeError('No esafe endpoints defined at this stage, could not add them to the api tree')
        for endpoint in self.endpoints:
            if endpoint.API_ENDPOINT is None:
                logger.error('Could not add endpoint {}: No "ENDPOINT" variable defined in the endpoint object.'.format(endpoint))
                continue
            root = endpoint
            script_name = endpoint.API_ENDPOINT
            dispatcher = getattr(endpoint, 'route_dispatcher', cherrypy.dispatch.MethodDispatcher())
            config = {
                '/': {'request.dispatch': dispatcher}
            }
            mounts.append({
                'root': root,
                'script_name': script_name,
                'config': config
            })
        self.web_service.update_tree(mounts)
