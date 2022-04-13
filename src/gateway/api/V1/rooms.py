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
from gateway.exceptions import ItemDoesNotExistException
from gateway.models import Database, Ventilation
from gateway.room_controller import RoomController
from ioc import INJECTED, Inject

logger = logging.getLogger(__name__)

if False:  # MyPy
    from typing import Dict, List, Any
    from gateway.dto import UserDTO
    from gateway.authentication_controller import AuthenticationToken

@expose
class Rooms(RestAPIEndpoint):
    API_ENDPOINT = '/api/rooms'

    @Inject
    def __init__(self, room_controller=INJECTED):
        # type: (RoomController) -> None
        super(Rooms, self).__init__()
        self.room_controller = room_controller
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.route_dispatcher.connect('list', '',
                                      controller=self, action='list',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('retrieve', '/:room_id',
                                      controller=self, action='retrieve',
                                      conditions={'method': ['GET']})

    @openmotics_api_v1(auth=True)
    def list(self):
        rooms = self.room_controller.load_rooms()
        data = [{'id': room.id, 'name': room.name} for room in rooms]
        return ApiResponse(body=data)

    @openmotics_api_v1(auth=True, check={'room_id': int})
    def retrieve(self, room_id):
        room = self.room_controller.load_room(room_id)
        data = {'id': room.id, 'name': room.name}
        return ApiResponse(body=data)
