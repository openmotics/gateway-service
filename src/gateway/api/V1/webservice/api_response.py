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
API Response object
"""

import ujson as json

if False:  # MyPy
    from typing import Optional, Dict, Any


class ApiResponse(object):

    def __init__(self, status_code=200, response_headers=None, body=None, is_json=True):
        # type: (int, Optional[Dict[str, str]], Optional[Any], bool) -> None
        self.status_code = status_code
        self.response_headers = response_headers if response_headers is not None else {}
        if is_json and body is not None:
            self.response_headers['Content-Type'] = 'application/json'
            self.body = json.dumps(body)  # type: Any
        else:
            self.body = body

    def __str__(self):
        return '<V1 API Response: {{Status Code: {}, Response Headers: {}, Body: {}}}>'.format(self.status_code, self.response_headers, self.body)

    def __eq__(self, other):
        if not isinstance(other, ApiResponse):
            return False
        return self.status_code == other.status_code and \
               self.response_headers == other.response_headers and \
               self.body == other.body

