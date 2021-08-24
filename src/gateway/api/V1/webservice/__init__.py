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
V1 Webservice Init file
"""

from gateway.api.V1.webservice.api_response import ApiResponse
from gateway.api.V1.webservice.base_api import RestAPIEndpoint, expose
from gateway.api.V1.webservice.webservice import openmotics_api_v1, WebServiceV1, AuthenticationLevel, LoginMethod

