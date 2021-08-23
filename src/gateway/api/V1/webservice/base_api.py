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
Base Rest API endpoint
"""

from __future__ import absolute_import

from ioc import INJECTED, Inject
from gateway.authentication_controller import AuthenticationController
from gateway.exceptions import GatewayException, NotImplementedException
from gateway.user_controller import UserController

if False:  # MyPy
    from typing import Optional


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
