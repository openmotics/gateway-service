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
import cherrypy
import logging
import ujson as json
import time

from ioc import INJECTED, Inject, Injectable, Singleton
from gateway.api.serializers.apartment import ApartmentSerializer
from gateway.api.serializers.user import UserSerializer
from gateway.exceptions import *
from gateway.models import User
from gateway.webservice import params_handler

if False:  # MyPy
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
    exposed = True
    API_ENDPOINT = None  # type: Optional[str]

    @Inject
    def __init__(self, user_controller=INJECTED):
        # type: (UserController) -> None
        self._user_controller = user_controller
        pass


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

    def get_users(self, **kwargs):
        role = kwargs.get('role')
        users = self._user_controller.load_users()
        # Filter the users when no role is provided or when the role is not admin
        if role is None or role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            users = [user for user in users if user.role in [User.UserRoles.USER]]
        users_serial = [UserSerializer.serialize(user) for user in users]
        return json.dumps(users_serial)

    def get_user(self, **kwargs):
        # return the requested user
        user_id = kwargs.get('user_id')
        if user_id is None:
            raise WrongInputParametersException('Could not get the user_id from the request')
        role = kwargs.get('role')
        user = self._user_controller.load_user(user_id=user_id)
        if user is None:
            raise ItemDoesNotExistException('User with id {} does not exists'.format(user_id))
        # Filter the users when no role is provided or when the role is not admin
        if role is None or role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            if user.role in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
                raise UnAuthorizedException('Cannot request an admin or technician user when not authenticated as one')
        user_serial = UserSerializer.serialize(user)
        return json.dumps(user_serial)

    def get_available_code(self, **kwargs):
        api_secret = kwargs.get('X-API-Secret')
        if api_secret is None:
            raise UnAuthorizedException('Cannot create a new available code without the X-API-Secret')
        elif not self._user_controller.authentication_controller.check_api_secret(api_secret):
            raise UnAuthorizedException('X-API-Secret is incorrect')
        return str(self._user_controller.generate_new_pin_code())

    @openmotics_api_v1(auth=False, pass_role=True)
    def GET(self, *args, **kwargs):
        if not args:  # empty, just return all the users
            return self.get_users(**kwargs)
        elif len(args) == 1 and args[0].isdigit():
            kwargs['user_id'] = int(args[0])
            return self.get_user(**kwargs)
        elif len(args) == 1 and args[0] == 'available_code':
            return self.get_available_code(**kwargs)

    # ===========================================================================

    def post_user(self, **kwargs):
        # Authentication:
        # only ADMIN & TECHNICIAN can create new USER, ADMIN, TECHNICIAN user types,
        # anyone can create a new COURIER
        request_body = kwargs.get('request_body')
        role = kwargs.get('role')
        if request_body is None:
            raise WrongInputParametersException('The request body is empty')
        try:
            user_json = json.loads(request_body)
            tmp_password = None
            if 'password' in user_json:
                tmp_password = user_json['password']
                del user_json['password']
            user_dto = UserSerializer.deserialize(user_json)
            if tmp_password is not None:
                user_dto.set_password(tmp_password)

            if 'pin_code' in user_dto.loaded_fields:
                user_dto.pin_code = None
                user_dto.loaded_fields.remove('pin_code')
        except Exception:
            raise ParseException('Could not parse the user json input')

        # Authenticated as a technician or admin, creating the user
        if role not in [User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN]:
            # if the user is not an admin or technician, check if the user to create is a COURIER
            if user_dto.role != User.UserRoles.COURIER:
                raise UnAuthorizedException('As a normal user, you can only create a COURIER user')

        try:
            self._user_controller.save_user(user_dto)
        except RuntimeError as e:
            raise WrongInputParametersException('The user could not be saved: {}'.format(e))
        return UserSerializer.serialize(user_dto)

    def post_activate_user(self, **kwargs):
        # request to activate a certain user
        user_id = kwargs.get('user_id')
        request_body = kwargs.get('request_body')
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

    @openmotics_api_v1(auth=False, pass_role=True)
    def POST(self, *args, **kwargs):
        if not args:  # empty, just create a new user
            return self.post_user(**kwargs)
        elif len(args) == 2 and args[0] == 'activate':
            kwargs['user_id'] = int(args[1])
            return self.post_activate_user(**kwargs)

    def put_update_user(self, **kwargs):
        request_body = kwargs.get('request_body')
        token = kwargs.get('token')
        if token is None:
            raise UnAuthorizedException('Cannot change a user without being logged in')
        user_id = kwargs.get('user_id')
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

        user_dto = UserSerializer.deserialize(user_json)
        user_dto.id = user_id
        self._user_controller.update_user(user_dto)
        user_loaded = self._user_controller.load_user(user_id)
        return UserSerializer.serialize(user_loaded)

    @openmotics_api_v1(auth=False, pass_role=True, pass_token=True)
    def PUT(self, *args, **kwargs):
        if not args:  # empty, just return all the users
            raise ItemDoesNotExistException('No user ID is present in the request')
        elif len(args) == 1 and args[0].isdigit():
            kwargs['user_id'] = int(args[0])
            return self.put_update_user(**kwargs)

    def delete_user(self, **kwargs):
        token = kwargs.get('token')
        user_id = kwargs.get('user_id')

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
        return

    @openmotics_api_v1(auth=False, pass_role=True, pass_token=True)
    def DELETE(self, *args, **kwargs):
        if not args:  # empty, just return all the users
            raise ItemDoesNotExistException('No user ID is present in the request')
        elif len(args) == 1 and args[0].isdigit():
            kwargs['user_id'] = int(args[0])
            return self.delete_user(**kwargs)
        else:
            raise ItemDoesNotExistException('endpoint does not exist')


class Apartment(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/apartments'

    def GET(self):
        return json.dumps({'apartment': 'testApartment'})

    def POST(self, list=None):
        request_body = cherrypy.request.body.read(int(cherrypy.request.headers['Content-Length']))
        if request_body is None:
            return json.dumps({'apartment': 'Pass a apartment body with your post request', 'testparam': list})
        else:
            request_body = json.loads(request_body)
            return json.dumps({'body': request_body, 'testparam': list})


@Injectable.named('web_service_v1')
@Singleton
class WebServiceV1(object):
    def __init__(self, esafe_endpoints=INJECTED, web_service=INJECTED):
        # type: (List[RestAPIEndpoint], Optional[WebService]) -> None
        self.web_service = web_service
        self.esafe_endpoints = esafe_endpoints

    def start(self):
        self.add_api_tree()

    def stop(self):
        pass

    def set_web_service(self, web_service):
        # type: (WebService) -> None
        self.web_service = web_service

    def add_api_tree(self):
        mounts = []
        if self.esafe_endpoints is None:
            raise AttributeError('No esafe endpoints defined at this stage, could not add them to the api tree')
        for endpoint in self.esafe_endpoints:
            if endpoint.API_ENDPOINT is None:
                logger.error('Could not add endpoint {}: No "ENDPOINT" variable defined in the endpoint object.'.format(endpoint))
                continue
            root = endpoint
            script_name = endpoint.API_ENDPOINT
            config = {
                '/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}
            }
            mounts.append({
                'root': root,
                'script_name': script_name,
                'config': config
            })
        self.web_service.update_tree(mounts)
