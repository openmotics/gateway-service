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
from __future__ import absolute_import

import logging
import uuid

import cherrypy

from gateway.api.V1.schema import SCHEMA
from gateway.api.V1.serializers.ventilation import VentilationConfigSerializer, \
    VentilationApiSerializer
from gateway.api.V1.webservice import ApiResponse, RestAPIEndpoint, expose, \
    openmotics_api_v1
from gateway.dto.ventilation import VentilationDTO, VentilationSourceDTO
from gateway.exceptions import ItemDoesNotExistException
from gateway.models import Database, Ventilation
from gateway.ventilation_controller import VentilationController
from ioc import INJECTED, Inject

logger = logging.getLogger(__name__)

if False:  # MyPy
    from typing import Dict, List, Any
    from gateway.dto import UserDTO
    from gateway.authentication_controller import AuthenticationToken

@expose
class VentilationUnits(RestAPIEndpoint):
    API_ENDPOINT = '/api/ventilation/units'

    @Inject
    def __init__(self, ventilation_controller=INJECTED):
        # type: (VentilationController) -> None
        super(VentilationUnits, self).__init__()
        self.ventilation_controller = ventilation_controller
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.route_dispatcher.connect('list', '',
                                      controller=self, action='list',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('retrieve', '/:ventilation_id',
                                      controller=self, action='retrieve',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('update', '/:ventilation_id',
                                      controller=self, action='update',
                                      conditions={'method': ['PUT', 'OPTIONS']})
        self.route_dispatcher.connect('sync', '/sync',
                                      controller=self, action='sync',
                                      conditions={'method': ['GET']})

    @openmotics_api_v1(auth=True)
    def list(self):
        units = self.ventilation_controller.load_ventilations()
        data = [VentilationConfigSerializer.serialize(unit) for unit in units]
        return ApiResponse(body=data)

    @openmotics_api_v1(auth=True, check={'ventilation_id': int})
    def retrieve(self, ventilation_id):
        unit = self.ventilation_controller.load_ventilation(ventilation_id)
        return ApiResponse(body=VentilationConfigSerializer.serialize(unit))

    @openmotics_api_v1(auth=True, expect_body_type='JSON', check={'ventilation_id': int})
    def update(self, ventilation_id, request_body):
        request_body.update({'id': ventilation_id})
        # validate(request_body, SCHEMA['ventilation_unit'])
        unit = VentilationConfigSerializer.deserialize(request_body)
        unit = self.ventilation_controller.save_ventilation(unit)
        return ApiResponse(body=VentilationConfigSerializer.serialize(unit))

    @openmotics_api_v1(auth=True)
    def sync(self):
        units = self.ventilation_controller.load_ventilations()
        data = [VentilationApiSerializer.serialize(unit) for unit in units]
        return ApiResponse(body=data)


@expose
class PluginVentilation(RestAPIEndpoint):
    API_ENDPOINT = '/plugin/ventilation'

    @Inject
    def __init__(self, ventilation_controller=INJECTED):
        # type: (VentilationController) -> None
        super(PluginVentilation, self).__init__()
        self.ventilation_controller = ventilation_controller
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.route_dispatcher.connect('register', '/register',
                                      controller=self, action='register',
                                      conditions={'method': ['POST', 'OPTIONS']})

    @openmotics_api_v1(auth=True, expect_body_type='JSON')
    def register(self, request_body):
        """
        {"source": "plugin", "plugin": "DummyPlugin", "external_id": "AAAAAA", "config": {}}
        """
        schema = {
            "type": "object",
            "required": ["source"],
            "properties": {
                "source": {
                    "enum": ["plugin"]
                }
            },
            "dependencies": {
                "source": {
                    "oneOf": [
                        {
                            "required": ["source", "plugin", "external_id"],
                            "properties": {
                                "source": {"const": "plugin"},
                                "plugin": {"type": "string"},
                                "external_id": {"type": "string"},
                                "config": {"type": "object"}
                            }
                        }
                    ]
                }
            }
        }
        # validate(request_body, schema)
        try:
            source = VentilationSourceDTO(request_body['source'])
            if source.type == 'plugin':
                source.name = request_body['plugin']
            external_id = request_body['external_id']
            config = request_body.get('config', {})
            unit = self.ventilation_controller.register_ventilation(source, external_id, config)
            return ApiResponse(body=VentilationApiSerializer.serialize(unit))
        except Exception:
            logger.error('Failed to register %s', request_body)
            raise
