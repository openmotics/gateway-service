# Copyright (C) 2018 OpenMotics BV
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
A container class for events send over the OM bus by OpenMotics services
"""


class OMBusEvents(object):
    CLOUD_REACHABLE = 'CLOUD_REACHABLE'
    CLIENT_CERTS_CHANGED = 'CLIENT_CERTS_CHANGED'
    VPN_OPEN = 'VPN_OPEN'
    METRICS_INTERVAL_CHANGE = 'METRICS_INTERVAL_CHANGE'
    CLIENT_DISCOVERY = 'CLIENT_DISCOVERY'
    CONNECTIVITY = 'CONNECTIVITY'
    TIME_CHANGED = 'TIME_CHANGED'
