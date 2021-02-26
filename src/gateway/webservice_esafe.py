from __future__ import absolute_import
import cherrypy
import ujson as json

import logging

from ioc import INJECTED, Inject, Injectable, Singleton
from gateway.esafe.esafe_user_controller import EsafeUserController
from gateway.api.serializers.esafe import EsafeUserSerializer, EsafeApartmentSerializer


logger = logging.getLogger("openmotics")


if False:  # MyPy
    from gateway.webservice import WebService, WebInterface
    from typing import Optional, List, Dict


# ----------------------------
# eSafe Authentication
# ----------------------------

class EsafeUserAuth:
    USER = 'USER'
    ADMIN = 'ADMIN'
    TECHNICIAN = 'TECHNICIAN'
    COURIER = 'COURIER'


def esafe_api(auth=None):
    def wrapper(func):
        if auth is not None:
            # Esafe auth here...
            pass
        return func
    return wrapper

# ----------------------------
# eSafe API
# ----------------------------

class EsafeRestAPIEndpoint(object):
    API_ENDPOINT = None  # type: Optional[str]

    @Inject
    def __init__(self, esafe_user_controller=INJECTED):
        # type: (EsafeUserController) -> None
        self.user_controller = esafe_user_controller


    def GET(self):
        raise NotImplementedError

    def POST(self):
        raise NotImplementedError

    def PUT(self):
        raise NotImplementedError

    def DELETE(self):
        raise NotImplementedError

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return 'Esafe Rest Endpoint class: "{}"'.format(self.__class__.__name__)


@cherrypy.expose
class EsafeUsers(EsafeRestAPIEndpoint):
    API_ENDPOINT = '/api/v1/users'

    @esafe_api(auth=None)
    def GET(self, user_id=None):
        if user_id is None:
            users = self.user_controller.load_users()
            # users_dto = [EsafeUserMapper.orm_to_dto(user) for user in users]
            users_serial = [EsafeUserSerializer.serialize(user) for user in users]
            return json.dumps({'users': users_serial})


        user = self.user_controller.load_user(user_id=user_id)
        if user is None:
            cherrypy.response.status = 404
            return json.dumps({})
        user_serial = EsafeUserSerializer.serialize(user)
        return json.dumps(user_serial)


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
class EsafeApartment(EsafeRestAPIEndpoint):
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


@Injectable.named('web_service_esafe')
@Singleton
class WebServiceEsafe(object):
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

