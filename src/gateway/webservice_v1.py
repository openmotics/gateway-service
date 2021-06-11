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
import datetime

from ioc import INJECTED, Inject, Injectable, Singleton
from gateway.api.serializers import ApartmentSerializer, UserSerializer, DeliverySerializer, \
    SystemDoorbellConfigSerializer, SystemRFIDConfigSerializer, SystemRFIDSectorBlockConfigSerializer, \
    SystemTouchscreenConfigSerializer, SystemGlobalConfigSerializer, SystemActivateUserConfigSerializer, \
    RfidSerializer
from gateway.dto import ApartmentDTO, DeliveryDTO
from gateway.exceptions import *
from gateway.models import User, Delivery
from gateway.user_controller import UserController
from gateway.webservice import params_handler, params_parser

if False:  # MyPy
    from gateway.apartment_controller import ApartmentController
    from gateway.delivery_controller import DeliveryController
    from gateway.authentication_controller import AuthenticationToken
    from gateway.rfid_controller import RfidController
    from gateway.system_config_controller import SystemConfigController
    from gateway.webservice import WebService
    from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

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
            status = 403
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
        contents = str(data).encode() if data is not None else None
        timings['serialization'] = 'Serialization', time.time() - serialization_start
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.headers['Server-Timing'] = ','.join(['{0}={1}; "{2}"'.format(key, value[1] * 1000, value[0])
                                                               for key, value in timings.items()])
        cherrypy.response.status = status
        return contents
    return wrapper


def authentication_handler_v1(pass_token=False, pass_role=False, throw_error=True, allowed_user_roles=None):
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
        if throw_error:
            if checked_token is None:
                raise UnAuthorizedException('Unauthorized API call')
            if allowed_user_roles is not None and checked_token.user.role not in allowed_user_roles:
                raise UnAuthorizedException('User role is not allowed for this API call: Allowed: {}, Got: {}'.format(allowed_user_roles, checked_token.user.role))
        if pass_token is True:
            request.params['auth_token'] = checked_token
        if pass_role is True:
            if checked_token is not None:
                request.params['auth_role'] = checked_token.user.role
            else:
                request.params['auth_role'] = None
    except UnAuthorizedException as ex:
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.status = 401  # Unauthorized
        contents = ex.message
        cherrypy.response.body = contents.encode()
        # do not handle the request, just return the unauthorized message
        request.handler = None

def params_handler_v1(expect_body_type=None, **kwargs):
    """ Converts/parses/loads specified request params. """
    request = cherrypy.request
    response = cherrypy.response
    try:
        if request.method in request.methods_with_bodies:
            body = request.body.read()
            if body:
                parsed_body = body
                if expect_body_type == 'JSON':
                    try:
                        parsed_body = json.loads(body)
                    except Exception:
                        raise ParseException('Could not parse the json body type')
                elif expect_body_type == 'NONE':
                    raise ParseException('Received a body, but no body is required')
                elif expect_body_type == 'RAW':
                    pass
                request.params['request_body'] = parsed_body
            else:
                if expect_body_type is not None:
                    raise WrongInputParametersException('No body has been passed to the request')
    except (ParseException, WrongInputParametersException) as ex:
        response.status = 400
        contents = ex.message
        response.body = contents.encode()
        request.handler = None
        return
    except Exception:
        response.status = 406  # No Acceptable
        contents = 'Generic Error: invalid_body'
        response.body = contents.encode()
        request.handler = None
        return
    try:
        params_parser(request.params, kwargs)
    except ValueError:
        response.status = 400  # No Acceptable
        contents = WrongInputParametersException.DESC
        response.body = contents.encode()
        request.handler = None


# Assign the v1 authentication handler
cherrypy.tools.authenticated_v1 = cherrypy.Tool('before_handler', authentication_handler_v1)
cherrypy.tools.params_v1 = cherrypy.Tool('before_handler', params_handler_v1)


def openmotics_api_v1(_func=None, check=None, auth=False, pass_token=False, pass_role=False, allowed_user_roles=None, expect_body_type=None):
    def decorator_openmotics_api_v1(func):
        func = _openmotics_api_v1(func)  # First layer decorator
        if auth is True:
            # Second layer decorator
            func = cherrypy.tools.authenticated_v1(pass_token=pass_token, pass_role=pass_role, allowed_user_roles=allowed_user_roles)(func)
        elif pass_token or pass_role:
            func = cherrypy.tools.authenticated_v1(pass_token=pass_token, pass_role=pass_role, allowed_user_roles=allowed_user_roles, throw_error=False)(func)
        if check is not None:
            check['expect_body_type'] = expect_body_type
        func = cherrypy.tools.params_v1(**(check or {'expect_body_type': expect_body_type}))(func)
        return func
    if _func is None:
        return decorator_openmotics_api_v1
    else:
        return decorator_openmotics_api_v1(_func)


# ----------------------------
# REST API
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
        if auth_role is None or auth_role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            users = self._user_controller.load_users(roles=[User.UserRoles.USER], include_inactive=include_inactive)
        else:
            users = self._user_controller.load_users(roles=[role], include_inactive=include_inactive)

        users_serial = [UserSerializer.serialize(user) for user in users]
        return json.dumps(users_serial)

    @openmotics_api_v1(auth=False, pass_role=True)
    def get_user(self, user_id, auth_role=None):
        # return the requested user
        if user_id is None:
            raise WrongInputParametersException('Could not get the user_id from the request')
        user = self._user_controller.load_user(user_id=user_id)
        if user is None:
            raise ItemDoesNotExistException('User with id {} does not exists'.format(user_id))
        # Filter the users when no role is provided or when the role is not admin
        if auth_role is None or auth_role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
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

        user_dto.username = uuid.uuid4().hex
        # add a custom user code
        user_dto.pin_code = str(self._user_controller.generate_new_pin_code()).rjust(UserController.PinCodeLength[user_dto.role], '0')
        # Generate a random password as a dummy to fill in the gap
        random_password = uuid.uuid4().hex
        user_dto.set_password(random_password)

        # Authenticated as a technician or admin, creating the user
        if auth_role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            # if the user is not an admin or technician, check if the user to create is a COURIER
            if user_dto.role != User.UserRoles.COURIER:
                raise UnAuthorizedException('As a normal user, you can only create a COURIER user')

        try:
            user_dto_saved = self._user_controller.save_user(user_dto)
        except RuntimeError as e:
            raise WrongInputParametersException('The user could not be saved: {}'.format(e))
        user_dto_serial = UserSerializer.serialize(user_dto_saved)
        # explicitly add the pin code when a new user is created, this way, the generated pin code is known to the user when created.
        user_dto_serial['pin_code'] = user_dto.pin_code
        return json.dumps(user_dto_serial)

    @openmotics_api_v1(auth=False, pass_role=False, expect_body_type='JSON')
    def post_activate_user(self, user_id, request_body):
        # request to activate a certain user
        request_code = request_body.get('code') or request_body.get('rfid_tag')
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

    @openmotics_api_v1(auth=True, pass_role=False, pass_token=True, expect_body_type='JSON')
    def put_update_user(self, user_id, auth_token=None, request_body=None, **kwargs):
        user_json = request_body
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            if auth_token.user.id != user_id:
                raise UnAuthorizedException('As a non admin or technician user, you cannot change another user')

        # check if the pin code or rfid tag is changed
        if 'pin_code' in user_json or 'rfid' in user_json:
            api_secret = kwargs.get('X-API-Secret')
            if api_secret is None:
                raise UnAuthorizedException('Cannot change the pin code or rfid data without the api secret')
            if not self._user_controller.authentication_controller.check_api_secret(api_secret):
                raise UnAuthorizedException('The api secret is not valid')

        # user_dto_orig = self._user_controller.load_user(user_id, clear_password=False)
        user_dto_orig = self._user_controller.load_user(user_id)
        user_dto = UserSerializer.deserialize(user_json)
        for field in ['first_name', 'last_name', 'pin_code', 'language', 'apartment']:
            if field in user_dto.loaded_fields:
                setattr(user_dto_orig, field, getattr(user_dto, field))
        saved_user = self._user_controller.save_user(user_dto_orig)
        saved_user.clear_password()
        return json.dumps(UserSerializer.serialize(saved_user))

    @openmotics_api_v1(auth=False, pass_role=False, pass_token=True)
    def delete_user(self, user_id, auth_token=None):
        user_to_delete_dto = self._user_controller.load_user(user_id)
        if user_to_delete_dto is None:
            raise ItemDoesNotExistException('Cannot delete an user that does not exists')

        if auth_token is None:
            if user_to_delete_dto.role != User.UserRoles.COURIER:
                raise UnAuthorizedException('As a non logged in user, you only can delete a Courier type')
        else:
            if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
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

    @openmotics_api_v1(auth=True, pass_role=False, pass_token=False,
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN],
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
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN],
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
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN],
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
                       allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN],
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

    @openmotics_api_v1(auth=True, pass_role=True, pass_token=False)
    def delete_apartment(self, apartment_id, auth_role=None):
        if auth_role is None:
            raise UnAuthorizedException('Authentication is needed when updating an apartment')
        if auth_role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            raise UnAuthorizedException('You need to be logged in as an admin or technician to update an apartment')
        apartment_dto = ApartmentDTO(id=apartment_id)
        self.apartment_controller.delete_apartment(apartment_dto)
        return 'OK'


class Deliveries(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/deliveries'

    @Inject
    def __init__(self, delivery_controller=INJECTED):
        # type: (DeliveryController) -> None
        super(Deliveries, self).__init__()
        self.delivery_controller = delivery_controller
        # Set a custom route dispatcher in the class so that you have full
        # control over how the routes are defined.
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_deliveries', '',
                                      controller=self, action='get_deliveries',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_delivery', '/:delivery_id',
                                      controller=self, action='get_delivery',
                                      conditions={'method': ['GET']})
        # --- POST ---
        self.route_dispatcher.connect('post_delivery', '',
                                      controller=self, action='post_delivery',
                                      conditions={'method': ['POST']})
        # --- PUT ---
        self.route_dispatcher.connect('put_delivery_pickup', '/:delivery_id/pickup',
                                      controller=self, action='put_delivery_pickup',
                                      conditions={'method': ['PUT']})

    @openmotics_api_v1(auth=True, pass_token=True)
    def get_deliveries(self, auth_token):
        # type: (AuthenticationToken) -> str
        role = auth_token.user.role
        user_id = auth_token.user.id

        # get all the deliveries
        deliveries = self.delivery_controller.load_deliveries()  # type: List[DeliveryDTO]

        # filter the deliveries for only the user id when they are not technician or admin
        if role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            deliveries = [delivery for delivery in deliveries if user_id in [delivery.user_id_delivery, delivery.user_id_pickup]]

        deliveries_serial = [DeliverySerializer.serialize(delivery) for delivery in deliveries]
        return json.dumps(deliveries_serial)

    @openmotics_api_v1(auth=True, pass_token=True)
    def get_delivery(self, delivery_id, auth_token):
        # type: (int, AuthenticationToken) -> str
        delivery = self.delivery_controller.load_delivery(delivery_id)
        if delivery is None:
            raise ItemDoesNotExistException('Could not find the delivery with id: {}'.format(delivery_id))
        user_id = auth_token.user.id
        user_role = auth_token.user.role
        if user_role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            if user_id not in [delivery.user_id_delivery, delivery.user_id_pickup]:
                raise UnAuthorizedException('You are not allowed to request this delivery')
        deliveries_serial = DeliverySerializer.serialize(delivery)
        return json.dumps(deliveries_serial)

    @openmotics_api_v1(auth=False, pass_token=True, expect_body_type='JSON')
    def post_delivery(self, auth_token=None, request_body=None):
        try:
            delivery_dto = DeliverySerializer.deserialize(request_body)
        except Exception as ex:
            raise ParseException('Could not create a valid delivery from the passed json data: {}'.format(ex))
        if delivery_dto.type == Delivery.DeliveryType.RETURN:
            if auth_token is None or auth_token.user.role == User.UserRoles.COURIER:
                raise UnAuthorizedException('To create a return delivery, you need to be logged in as USER, ADMIN or TECHNICIAN')

        saved_delivery = self.delivery_controller.save_delivery(delivery_dto)
        if saved_delivery is None:
            raise RuntimeError('Unexpected error: Delivery is None when save_delivery is called')
        saved_delivery_serial = DeliverySerializer.serialize(saved_delivery)
        return json.dumps(saved_delivery_serial)

    @openmotics_api_v1(auth=True, pass_token=True)
    def put_delivery_pickup(self, delivery_id, auth_token):
        # type: (int, AuthenticationToken) -> str
        delivery_dto = self.delivery_controller.load_delivery(delivery_id)
        if delivery_dto is None:
            raise ItemDoesNotExistException('Cannot pickup a delivery that does not exists: id: {}'.format(delivery_id))

        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            auth_user_id = auth_token.user.id
            if auth_user_id not in [delivery_dto.user_id_delivery, delivery_dto.user_id_pickup]:
                raise UnAuthorizedException('Cannot pick up a package that is not yours when you are not admin or technician')

        delivery_dto_returned = self.delivery_controller.pickup_delivery(delivery_id)
        if delivery_dto_returned is None:
            raise RuntimeError('Unexpected error: Delivery is None when pickup_delivery is called')
        delivery_serial = DeliverySerializer.serialize(delivery_dto_returned)
        return json.dumps(delivery_serial)


class SystemConfiguration(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/system'

    @Inject
    def __init__(self, system_config_controller=INJECTED):
        # type: (SystemConfigController) -> None
        super(SystemConfiguration, self).__init__()
        self.system_config_controller = system_config_controller
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_doorbell_config', '/configuration/doorbell',
                                      controller=self, action='get_doorbell_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_rfid_config', '/configuration/rfid',
                                      controller=self, action='get_rfid_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_rfid_sector_block_config', '/configuration/rfid_sector_block',
                                      controller=self, action='get_rfid_sector_block_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_touchscreen_config', '/configuration/touchscreen',
                                      controller=self, action='get_touchscreen_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_global_config', '/configuration/global',
                                      controller=self, action='get_global_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_activate_user_config', '/configuration/activate_user',
                                      controller=self, action='get_activate_user_config',
                                      conditions={'method': ['GET']})
        # --- PUT ---
        self.route_dispatcher.connect('put_doorbell_delivery', '/configuration/doorbell',
                                      controller=self, action='put_doorbell_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_rfid_delivery', '/configuration/rfid',
                                      controller=self, action='put_rfid_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_rfid_sector_block_delivery', '/configuration/rfid_sector_block',
                                      controller=self, action='put_rfid_sector_block_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_touchscreen_delivery', '/touchscreen/calibrate',
                                      controller=self, action='put_touchscreen_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_global_delivery', '/configuration/global',
                                      controller=self, action='put_global_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_activate_user_delivery', '/configuration/activate_user',
                                      controller=self, action='put_activate_user_config',
                                      conditions={'method': ['PUT']})

    @openmotics_api_v1(auth=False)
    def get_doorbell_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_doorbell_config()
        config_serial = SystemDoorbellConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN], expect_body_type='JSON')
    def put_doorbell_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemDoorbellConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_doorbell_config(config_dto)
        return

    @openmotics_api_v1(auth=False)
    def get_rfid_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_rfid_config()
        config_serial = SystemRFIDConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN], expect_body_type='JSON')
    def put_rfid_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemRFIDConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_rfid_config(config_dto)
        return

    @openmotics_api_v1(auth=False)
    def get_rfid_sector_block_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_rfid_sector_block_config()
        config_serial = SystemRFIDSectorBlockConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN], expect_body_type='JSON')
    def put_rfid_sector_block_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemRFIDSectorBlockConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_rfid_sector_block_config(config_dto)
        return

    @openmotics_api_v1(auth=False)
    def get_touchscreen_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_touchscreen_config()
        config_serial = SystemTouchscreenConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN])
    def put_touchscreen_config(self):
        # type: () -> None
        try:
            self.system_config_controller.save_touchscreen_config()
        except Exception as ex:
            raise RuntimeError('Could not calibrate the touchscreen: {}'.format(ex))
        return

    @openmotics_api_v1(auth=False)
    def get_global_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_global_config()
        config_serial = SystemGlobalConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN], expect_body_type='JSON')
    def put_global_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemGlobalConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_global_config(config_dto)
        return

    @openmotics_api_v1(auth=False)
    def get_activate_user_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_activate_user_config()
        config_serial = SystemActivateUserConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN], expect_body_type='JSON')
    def put_activate_user_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemActivateUserConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_activate_user_config(config_dto)
        return


class Rfid(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/rfid'

    @Inject
    def __init__(self, rfid_controller=INJECTED):
        # type: (RfidController) -> None
        super(Rfid, self).__init__()
        self.rfid_controller = rfid_controller
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_rfids', '',
                                      controller=self, action='get_rfids',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_rfid', '/:rfid_id',
                                      controller=self, action='get_rfid',
                                      conditions={'method': ['GET']})
        # --- PUT ---
        self.route_dispatcher.connect('put_start_add', '/add_new/start',
                                      controller=self, action='put_start_add',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_cancel_add', '/add_new/cancel',
                                      controller=self, action='put_cancel_add',
                                      conditions={'method': ['PUT']})
        # --- DELETE ---
        self.route_dispatcher.connect('delete_rfid', '/:rfid_id',
                                      controller=self, action='delete_rfid',
                                      conditions={'method': ['DELETE']})

    @openmotics_api_v1(auth=True, pass_token=True)
    def get_rfids(self, auth_token=None):
        rfids = self.rfid_controller.load_rfids()

        # filter the rfids if the role is not a super user
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            rfids = [rfid for rfid in rfids if rfid.user.id == auth_token.user.id]

        rfids_serial = [RfidSerializer.serialize(rfid) for rfid in rfids]
        return json.dumps(rfids_serial)

    @openmotics_api_v1(auth=True, pass_token=True)
    def get_rfid(self, rfid_id, auth_token=None):
        rfid = self.rfid_controller.load_rfid(rfid_id)

        if rfid is None:
            raise ItemDoesNotExistException('RFID tag with id {} does not exists'.format(rfid_id))

        # filter the rfids if the role is not a super user
        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            if rfid.user.id != auth_token.user.id:
                raise UnAuthorizedException('As a non admin or technician, you cannot request an rfid that is not yours')

        rfid_serial = RfidSerializer.serialize(rfid)
        return json.dumps(rfid_serial)

    @openmotics_api_v1(auth=True, pass_token=True, expect_body_type='JSON')
    def put_start_add(self, rfid_id, auth_token, request_body):
        raise NotImplementedException("start add new rfid not implemented")

    @openmotics_api_v1(auth=True, pass_token=True, expect_body_type='NONE')
    def put_cancel_add(self, rfid_id, auth_token):
        raise NotImplementedException("start add new rfid not implemented")

    @openmotics_api_v1(auth=True, pass_token=True)
    def delete_rfid(self, rfid_id, auth_token=None):
        # first fetch the rfid tag to check if it exists and if the deletion is authorized
        rfid = self.rfid_controller.load_rfid(rfid_id)
        if rfid is None:
            raise ItemDoesNotExistException("Cannot delete RFID: tag with id '{}' does not exist".format(rfid_id))

        if auth_token.user.role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            if rfid.user.id != auth_token.user.id:
                raise UnAuthorizedException('As a non admin or technician, you cannot delete an rfid that is not yours')

        self.rfid_controller.delete_rfid(rfid_id)
        return 'OK'


@Injectable.named('web_service_v1')
@Singleton
class WebServiceV1(object):
    def __init__(self, web_service=INJECTED):
        # type: (Optional[WebService]) -> None
        self.web_service = web_service
        self.endpoints = [
            Users(),
            Apartments(),
            Deliveries(),
            SystemConfiguration(),
            Rfid()
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
            raise AttributeError('No endpoints defined at this stage, could not add them to the api tree')
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
