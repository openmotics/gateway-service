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
system configuration api description
"""

import cherrypy
import logging
import ujson as json

from ioc import INJECTED, Inject
from gateway.api.serializers import SystemRFIDConfigSerializer,\
    SystemRFIDSectorBlockConfigSerializer,\
    SystemDoorbellConfigSerializer,\
    SystemTouchscreenConfigSerializer,\
    SystemGlobalConfigSerializer,\
    SystemActivateUserConfigSerializer
from gateway.exceptions import StateException
from gateway.models import User
from gateway.system_config_controller import SystemConfigController
from gateway.api.V1.webservice.webservice import RestAPIEndpoint, openmotics_api_v1, expose

if False:  # MyPy
    from typing import Dict

logger = logging.getLogger(__name__)


@expose
class SystemConfiguration(RestAPIEndpoint):
    API_ENDPOINT = '/api/v1/system'

    @Inject
    def __init__(self, system_config_controller=INJECTED):
        # type: (SystemConfigController) -> None
        super(SystemConfiguration, self).__init__()
        self.system_config_controller = system_config_controller
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        # --- GET ---
        self.route_dispatcher.connect('get_doorbell_config', '/configuration/doorbell',
                                      controller=self, action='get_doorbell_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_rfid_config', '/configuration/rfid',
                                      controller=self, action='get_rfid_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_rfid_sector_block_config', '/configuration/rfid_sector_block',
                                      controller=self, action='get_rfid_sector_block_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_touchscreen_config', '/configuration/touchscreen',
                                      controller=self, action='get_touchscreen_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_global_config', '/configuration/global',
                                      controller=self, action='get_global_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_activate_user_config', '/configuration/activate_user',
                                      controller=self, action='get_activate_user_config',
                                      conditions={'method': ['GET']})
        self.route_dispatcher.connect('get_esafe_serial', '/serial',
                                      controller=self, action='get_esafe_serial',
                                      conditions={'method': ['GET']})
        # --- PUT ---
        self.route_dispatcher.connect('put_doorbell_delivery', '/configuration/doorbell',
                                      controller=self, action='put_doorbell_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_rfid_config', '/configuration/rfid',
                                      controller=self, action='put_rfid_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_rfid_sector_block_delivery', '/configuration/rfid_sector_block',
                                      controller=self, action='put_rfid_sector_block_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_touchscreen_delivery', '/touchscreen/calibrate',
                                      controller=self, action='put_touchscreen_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_global_delivery', '/configuration/global',
                                      controller=self, action='put_global_config',
                                      conditions={'method': ['PUT']})
        self.route_dispatcher.connect('put_activate_user_delivery', '/configuration/activate_user',
                                      controller=self, action='put_activate_user_config',
                                      conditions={'method': ['PUT']})

    @openmotics_api_v1(auth=False)
    def get_doorbell_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_doorbell_config()
        config_serial = SystemDoorbellConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER], expect_body_type='JSON')
    def put_doorbell_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemDoorbellConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_doorbell_config(config_dto)
        return

    @openmotics_api_v1(auth=False)
    def get_rfid_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_rfid_config()
        config_serial = SystemRFIDConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER], expect_body_type='JSON')
    def put_rfid_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemRFIDConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_rfid_config(config_dto)
        return

    @openmotics_api_v1(auth=False)
    def get_rfid_sector_block_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_rfid_sector_block_config()
        config_serial = SystemRFIDSectorBlockConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER], expect_body_type='JSON')
    def put_rfid_sector_block_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemRFIDSectorBlockConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_rfid_sector_block_config(config_dto)
        return

    @openmotics_api_v1(auth=False)
    def get_touchscreen_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_touchscreen_config()
        config_serial = SystemTouchscreenConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER])
    def put_touchscreen_config(self):
        # type: () -> None
        try:
            self.system_config_controller.save_touchscreen_config()
        except Exception as ex:
            raise RuntimeError('Could not calibrate the touchscreen: {}'.format(ex))
        return

    @openmotics_api_v1(auth=False)
    def get_global_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_global_config()
        config_serial = SystemGlobalConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER], expect_body_type='JSON')
    def put_global_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemGlobalConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_global_config(config_dto)
        return

    @openmotics_api_v1(auth=False)
    def get_activate_user_config(self):
        # type: () -> str
        config_dto = self.system_config_controller.get_activate_user_config()
        config_serial = SystemActivateUserConfigSerializer.serialize(config_dto)
        return json.dumps(config_serial)

    @openmotics_api_v1(auth=True, allowed_user_roles=[User.UserRoles.ADMIN, User.UserRoles.TECHNICIAN, User.UserRoles.SUPER], expect_body_type='JSON')
    def put_activate_user_config(self, request_body):
        # type: (Dict) -> None
        config_dto = SystemActivateUserConfigSerializer.deserialize(request_body)
        self.system_config_controller.save_activate_user_config(config_dto)
        return

    @openmotics_api_v1(auth=False)
    def get_esafe_serial(self):
        # type: () -> str
        serial = self.system_config_controller.get_esafe_serial()
        if serial is None:
            raise StateException('Cannot fetch the eSafe serial')
        return json.dumps({'serial': serial})
