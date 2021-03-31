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

if False:  # MyPy
    from gateway.authentication_controller import AuthenticationToken
    from gateway.webservice import WebService
    from typing import Optional, List, Dict

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


def authentication_handler_v1(pass_token=False, pass_role=False):
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
        if checked_token is None:
            raise UnAuthorizedException('Unauthorized API call')
        if pass_token is True:
            request.params['token'] = checked_token
        if pass_role is True:
            request.params['role'] = checked_token.user.role
    except UnAuthorizedException as ex:
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.status = 401  # Unauthorized
        contents = ex.message
        cherrypy.response.body = contents.encode()
        # do not handle the request, just return the unauthorized message
        request.handler = None


# Assign the v1 authentication handler
cherrypy.tools.authenticated_v1 = cherrypy.Tool('before_handler', authentication_handler_v1)


def openmotics_api_v1(_func=None, auth=False, pass_token=False, pass_role=False):
    def decorator_openmotics_api_v1(func):
        updated_func = func
        updated_func = _openmotics_api_v1(updated_func)  # First layer decorator
        if auth is True:
            # Second layer decorator
            updated_func = cherrypy.tools.authenticated_v1(pass_token=pass_token, pass_role=pass_role)(updated_func)
        return updated_func
    if _func is None:
        return decorator_openmotics_api_v1
    else:
        return decorator_openmotics_api_v1(_func)


# ----------------------------
# eSafe API
# ----------------------------

class RestAPIEndpoint(object):
    API_ENDPOINT = None  # type: Optional[str]

    @Inject
    def __init__(self, user_controller=INJECTED):
        # type: () -> None
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


@cherrypy.expose
class Users(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/users'

    @openmotics_api_v1(auth=True, pass_role=True)
    def GET(self, role, user_id=None):
        # return all users
        if user_id is None:
            users = self._user_controller.load_users()
            users_serial = [UserSerializer.serialize(user) for user in users]
            return json.dumps(users_serial)

        # return the requested user
        user = self._user_controller.load_user(user_id=user_id)
        if user is None:
            cherrypy.response.status = 404
            return json.dumps({})
        user_serial = UserSerializer.serialize(user)
        return json.dumps(user_serial)

    @openmotics_api_v1(auth=True, pass_token=True, pass_role=True)
    def POST(self, testpar=None):
        request_body = cherrypy.request.body.read(int(cherrypy.request.headers['Content-Length']))
        if request_body is None:
            return json.dumps({'user': 'Pass a user body with your post request'})
        else:
            return request_body

    def PUT(self, user_json=None):
        if user_json is None:
            return json.dumps({'user': 'Pass a user body with your post request'})
        else:
            return json.dumps(user_json)

    def DELETE(self, user_json=None):
        return 'ok'


@cherrypy.expose
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
        # type: (List[EsafeRestAPIEndpoint], Optional[WebService]) -> None
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
