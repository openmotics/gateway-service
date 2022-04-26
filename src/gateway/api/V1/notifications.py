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
from gateway.api.V1.webservice import ApiResponse, RestAPIEndpoint, expose, \
    openmotics_api_v1
from ioc import INJECTED, Inject
from gateway.events import GatewayEvent
from cloud.events import EventSender

logger = logging.getLogger(__name__)

if False:  # MyPy
    from typing import Dict, List, Any
    from gateway.dto import UserDTO
    from gateway.authentication_controller import AuthenticationToken


@expose
class Notifications(RestAPIEndpoint):
    API_ENDPOINT = '/api/notifications'

    @Inject
    def __init__(self, event_sender=INJECTED):
        # type: (EventSender) -> None
        super(Notifications, self).__init__()
        self.event_sender = event_sender
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.route_dispatcher.connect('list', '',
                                      controller=self, action='list',
                                      conditions={'method': ['GET']})

    @openmotics_api_v1(auth=True)
    def list(self):
        return ApiResponse(body=[])


@expose
class PluginNotification(RestAPIEndpoint):
    API_ENDPOINT = '/plugin/notification'

    @Inject
    def __init__(self, event_sender=INJECTED):
        # type: (EventSender) -> None
        super(PluginNotification, self).__init__()
        self.event_sender = event_sender
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.route_dispatcher.connect('create', '',
                                      controller=self, action='create',
                                      conditions={'method': ['POST', 'OPTIONS']})

    @openmotics_api_v1(auth=True, expect_body_type='JSON')
    def create(self, request_body):
        """
        {"source": "plugin", "plugin": "DummyPlugin", "topic": "warning", "message": "Something happened", "type": "USER"}
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
                            "required": ["source", "plugin", "topic", "message"],
                            "properties": {
                                "source": {"const": "plugin"},
                                "plugin": {"type": "string"},
                                "topic": {"type": "string"},
                                "message": {"type": "string"},
                                "type": {"type": "string"}
                            }
                        }
                    ]
                }
            }
        }
        # validate(request_body, schema)
        source, topic, message = request_body['source'], request_body['topic'], request_body['message']
        type = request_body.get('type', 'USER')
        plugin = request_body.get('plugin')
        gateway_event = GatewayEvent(event_type=GatewayEvent.Types.NOTIFICATION,
                                     data={'source': source,
                                           'plugin': plugin,
                                           'type': type,
                                           'topic': topic,
                                           'message': message})
        self.event_sender.enqueue_event(gateway_event)
        return ApiResponse(body={})  # TODO
