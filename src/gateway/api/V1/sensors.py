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
from gateway.api.V1.serializers.sensor import SensorApiSerializer
from gateway.api.V1.webservice import ApiResponse, RestAPIEndpoint, expose, \
    openmotics_api_v1
from gateway.dto.sensor import SensorDTO, SensorSourceDTO
from gateway.exceptions import ItemDoesNotExistException
from gateway.models import Database, Ventilation
from gateway.sensor_controller import SensorController
from ioc import INJECTED, Inject

logger = logging.getLogger(__name__)

if False:  # MyPy
    from typing import Dict, List, Any
    from gateway.dto import UserDTO
    from gateway.authentication_controller import AuthenticationToken

@expose
class Sensors(RestAPIEndpoint):
    API_ENDPOINT = '/api/sensors'

    @Inject
    def __init__(self, sensor_controller=INJECTED):
        # type: (SensorController) -> None
        super(Sensors, self).__init__()
        self.sensor_controller = sensor_controller
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.route_dispatcher.connect('list', '',
                                      controller=self, action='list',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('sync', '/sync',
                                      controller=self, action='sync',
                                      conditions={'method': ['GET']})

    @openmotics_api_v1(auth=True)
    def list(self):
        return ApiResponse(body=[])

    @openmotics_api_v1(auth=True)
    def sync(self):
        sensors = self.sensor_controller.load_sensors()
        data = [SensorApiSerializer.serialize(sensor) for sensor in sensors]
        return ApiResponse(body=data)


@expose
class PluginSensor(RestAPIEndpoint):
    API_ENDPOINT = '/plugin/sensor'

    @Inject
    def __init__(self, sensor_controller=INJECTED):
        # type: (SensorController) -> None
        super(PluginSensor, self).__init__()
        self.sensor_controller = sensor_controller
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.route_dispatcher.connect('register', '/register',
                                      controller=self, action='register',
                                      conditions={'method': ['POST', 'OPTIONS']})

    @openmotics_api_v1(auth=True, expect_body_type='JSON')
    def register(self, request_body):
        """
        {"source": "plugin", "plugin": "DummyPlugin", "external_id": "AAAAAA", "physical_quantity": "temperature", "config": {}}
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
                            "required": ["source", "plugin", "external_id", "physical_quantity"],
                            "properties": {
                                "source": {"const": "plugin"},
                                "plugin": {"type": "string"},
                                "external_id": {"type": "string"},
                                "physical_quantity": {"type": "string"},
                                "config": {"type": "object"}
                            }
                        }
                    ]
                }
            }
        }
        # validate(request_body, schema)
        try:
            source = SensorSourceDTO(request_body['source'])
            if source.type == 'plugin':
                source.name = request_body['plugin']
            external_id, physical_quantity = request_body['external_id'], request_body['physical_quantity']
            config = request_body.get('config', {})
            sensor = self.sensor_controller.register_sensor(source, external_id, physical_quantity, config)
            return ApiResponse(body=SensorApiSerializer.serialize(sensor))
        except Exception:
            logger.error('Failed to register %s', request_body)
            raise
