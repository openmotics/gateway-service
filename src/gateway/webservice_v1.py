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
from decorator import decorator
from enum import Enum
import logging
import ujson as json
import time

from ioc import INJECTED, Inject, Injectable, Singleton
from gateway.authentication_controller import AuthenticationToken, AuthenticationController, LoginMethod
from gateway.exceptions import ItemDoesNotExistException, UnAuthorizedException, \
    GatewayException, ForbiddenException, ParseException, \
    InvalidOperationException, WrongInputParametersException, \
    TimeOutException, NotImplementedException
from gateway.user_controller import UserController
from gateway.webservice import params_parser

if False:  # MyPy
    from gateway.webservice import WebService
    from typing import Optional, List, Dict, Any, Type, Callable

logger = logging.getLogger(__name__)


# ------------------------
#  api decorator
# ------------------------


# api decorator -> Use @decorator to not loose the function arguments
@decorator
def _openmotics_api_v1(f, *args, **kwargs):
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
        data = 'General Error occurred during api call: {}: {}'.format(type(ex).__name__, ex)
        logger.error(data)
        import traceback
        print(traceback.print_exc())

    # start the serialization timing
    timings['process'] = ('Processing', time.time() - start)
    serialization_start = time.time()

    # check if custom response object is returned, If this is true, no error has occurred
    if isinstance(data, V1ApiResponse):
        status = data.status_code
        for header_name, header_value in data.response_headers.items():
            cherrypy.response.headers[header_name] = header_value
        if 'Content-Type' not in data.response_headers:
            cherrypy.response.headers['Content-Type'] = 'application/json'
        response_body = data.body
    else:
        response_body = data
        cherrypy.response.headers['Content-Type'] = 'application/json'

    # encode response data
    contents = str(response_body).encode() if response_body is not None else None
    # end the serialization timing
    timings['serialization'] = 'Serialization', time.time() - serialization_start

    # Set the server timing header
    cherrypy.response.headers['Server-Timing'] = ','.join(['{0}={1}; "{2}"'.format(key, value[1] * 1000, value[0])
                                                           for key, value in timings.items()])
    cherrypy.response.status = status
    return contents


class AuthenticationLevel(Enum):
    NONE = 'none'  # Not authenticated at all on any level
    HIGH = 'high'  # Authenticated with username/password or having X-API-Secret or both


@Inject
def check_authentication_security_level(checked_token, required_level=None, authentication_controller=INJECTED):
    # type: (AuthenticationToken, Optional[AuthenticationLevel], AuthenticationController) -> AuthenticationLevel
    api_secret = cherrypy.request.headers.get('X-API-Secret')
    level = AuthenticationLevel.NONE
    if authentication_controller.check_api_secret(api_secret):
        level = AuthenticationLevel.HIGH
    if checked_token is not None and checked_token.login_method == LoginMethod.PASSWORD:
        level = AuthenticationLevel.HIGH
    if required_level is not None and level != required_level and required_level == AuthenticationLevel.HIGH:
        raise UnAuthorizedException('Authentication level "HIGH" required')
    return level


def _get_authentication_token_from_request():
    request = cherrypy.request
    token = None
    # check if token is passed with the params
    if 'token' in request.params:
        token = request.params.pop('token')
    # check if the token is passed as a Bearer token in the headers
    if token is None:
        header = request.headers.get('Authorization')
        if header is not None and 'Bearer ' in header:
            token = header.replace('Bearer ', '')
    # check if the token is passed as a web-socket Bearer token
    if token is None:
        header = request.headers.get('Sec-WebSocket-Protocol')
        if header is not None and 'authorization.bearer.' in header:
            unpadded_base64_token = header.replace('authorization.bearer.', '')
            base64_token = unpadded_base64_token + '=' * (-len(unpadded_base64_token) % 4)
            try:
                token = base64.decodestring(base64_token).decode('utf-8')
            except Exception:
                pass
    return token


def authentication_handler_v1(pass_token=False, pass_role=False, auth=False, auth_level=AuthenticationLevel.NONE, allowed_user_roles=None, pass_security_level=False):
    request = cherrypy.request
    if request.method == 'OPTIONS':
        return
    try:
        token = _get_authentication_token_from_request()
        auth_controller = request.handler.callable.__self__.authentication_controller  # type: AuthenticationController
        # Fetch the checkToken function that is placed under the main webservice or under the plugin webinterface.
        check_token = auth_controller.check_token
        checked_token = check_token(token)  # type: Optional[AuthenticationToken]

        # check the security level for this call
        if auth:
            if checked_token is None:
                raise UnAuthorizedException('Unauthorized API call: No login information')
            if allowed_user_roles is not None and checked_token.user.role not in allowed_user_roles:
                raise UnAuthorizedException('User role is not allowed for this API call: Allowed: {}, Got: {}'.format(allowed_user_roles, checked_token.user.role))
        checked_auth_level = check_authentication_security_level(checked_token, auth_level)

        # Pass the appropriate data to the api call
        if pass_token is True:
            request.params['auth_token'] = checked_token
        if pass_role is True:
            request.params['auth_role'] = checked_token.user.role if checked_token is not None else None
        if pass_security_level is True:
            request.params['auth_security_level'] = checked_auth_level
    except UnAuthorizedException as ex:
        cherrypy.response.status = 401  # Unauthorized
        contents = ex.message
        cherrypy.response.body = contents.encode()
        # do not handle the request, just return the unauthorized message
        request.handler = None


def params_handler_v1(expect_body_type=None, check_for_missing=True, **kwargs):
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
                elif expect_body_type is None:
                    raise ParseException('Received a body, but no body is required')
                elif expect_body_type == 'RAW':
                    pass
                else:
                    raise ValueError('Unexpected value for `expect_body_type`: {}'.format(expect_body_type))
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
    except ValueError as ex:
        response.status = 400  # No Acceptable
        contents = WrongInputParametersException.DESC
        contents += ': {}'.format(ex)
        response.body = contents.encode()
        request.handler = None
    if check_for_missing and not set(kwargs).issubset(set(request.params)):
        response.status = 400
        contents = WrongInputParametersException.DESC
        contents += ': Missing parameters'
        response.body = contents.encode()
        request.handler = None


# Assign the v1 authentication handler
cherrypy.tools.authenticated_v1 = cherrypy.Tool('before_handler', authentication_handler_v1)
cherrypy.tools.params_v1 = cherrypy.Tool('before_handler', params_handler_v1)


# Decorator to be used in the RestAPIEndpoint subclasses for defining how the api is exposed
def openmotics_api_v1(_func=None, check=None, check_for_missing=False, auth=False, auth_level=AuthenticationLevel.NONE, pass_token=False, pass_role=False,
                      allowed_user_roles=None, expect_body_type=None, pass_security_level=False):
    # type: (Callable[..., Any], Dict[Any, Any], bool, bool, AuthenticationLevel, bool, bool, List[Any], Optional[str], bool) -> Callable[..., Any]
    def decorator_openmotics_api_v1(func):
        # First layer decorator: Error handling
        func = _openmotics_api_v1(func)

        # Second layer decorator: Authentication
        func = cherrypy.tools.authenticated_v1(pass_token=pass_token,
                                               pass_role=pass_role,
                                               allowed_user_roles=allowed_user_roles,
                                               pass_security_level=pass_security_level,
                                               auth=auth,
                                               auth_level=auth_level
                                               )(func)

        # Third layer decorator: Check parameters
        _check = None
        if check is not None:
            check['expect_body_type'] = expect_body_type
            check['check_for_missing'] = check_for_missing
        else:
            _check = {'expect_body_type': expect_body_type, 'check_for_missing': False}  # default check_for_missing to false when there is nothing to check
        func = cherrypy.tools.params_v1(**(check or _check))(func)

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
    def __init__(self, user_controller=INJECTED, authentication_controller=INJECTED):
        # type: (UserController, AuthenticationController) -> None
        self.user_controller = user_controller
        self.authentication_controller = authentication_controller

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


class V1ApiResponse(object):

    def __init__(self, status_code=200, response_headers=None, body=None):
        # type: (int, Optional[Dict[str, str]], Optional[Any]) -> None
        self.status_code = status_code
        self.response_headers = response_headers if response_headers is not None else {}
        self.body = body

    def __str__(self):
        return '<V1 API Response: {{Status Code: {}, Response Headers: {}, Body: {}}}>'.format(self.status_code, self.response_headers, self.body)

    def __eq__(self, other):
        if not isinstance(other, V1ApiResponse):
            return False
        return self.status_code == other.status_code and \
               self.response_headers == other.response_headers and \
               self.body == other.body


@Inject
def expose(cls, api_endpoint_register=INJECTED):
    """
    Decorator to expose a RestAPIEndpoint subclass
    This will register the api class to the V1 webservice
    """
    if not issubclass(cls, RestAPIEndpoint):
        raise GatewayException('Cannot expose a non "RestAPIEndpoint" subclass')
    api_endpoint_register.register(cls)
    return cls


@Injectable.named('api_endpoint_register')
@Singleton
class APIEndpointRegister(object):
    """ A class that will hold all the endpoints. This is to not have to include the complete webservice when registering an api"""

    def __init__(self):
        self.endpoints = []

    def register(self, api):
        # type: (Type[RestAPIEndpoint]) -> None
        logger.info("Registering a new API: {:<20} @ {}".format(api.__name__, api.API_ENDPOINT))
        self.endpoints.append(api)

    def __len__(self):
        return len(self.endpoints)

    def __next__(self):
        return next(self.endpoints)

    def __iter__(self):
        return iter(self.endpoints)

    def __getitem__(self, item):
        if not isinstance(item, int):
            raise TypeError('Wrong type if item passed: Need a integer')
        return self.endpoints[item]


@Injectable.named('web_service_v1')
@Singleton
class WebServiceV1(object):
    def __init__(self, web_service=INJECTED, api_endpoint_register=INJECTED):
        # type: (WebService, APIEndpointRegister) -> None
        logger.debug('Creating V1 webservice')
        self.web_service = web_service
        self.endpoints = api_endpoint_register

    def start(self):
        logger.info('Starting the V1 webservice: {}'.format(self))
        self.add_api_tree()

    def stop(self):
        """ No use for the stop function at the moment """
        pass

    def set_web_service(self, web_service):
        # type: (WebService) -> None
        self.web_service = web_service

    def add_api_tree(self):
        mounts = []
        if self.endpoints is None:
            raise AttributeError('No endpoints defined at this stage, could not add them to the api tree')
        for endpoint in self.endpoints:
            # creating an instance of the class
            endpoint = endpoint()
            logger.debug('Mounting api endpoint: {}'.format(endpoint))
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

    def __str__(self):
        return '<Webservice V1: Endpoints: {}>'.format([endpoint.__name__ for endpoint in self.endpoints])

    def __repr__(self):
        return self.__str__()
