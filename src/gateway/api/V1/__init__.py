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
V1 api init file
"""

from gateway.api.V1.apartments import Apartments
from gateway.api.V1.authentication import Authentication
from gateway.api.V1.deliveries import Deliveries
from gateway.api.V1.doorbell import Doorbell
from gateway.api.V1.mailbox import MailBox
from gateway.api.V1.parcelbox import ParcelBox
from gateway.api.V1.rfid import Rfid
from gateway.api.V1.system_config import SystemConfiguration
from gateway.api.V1.users import Users