# Copyright (C) 2016 OpenMotics BV
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
""" Includes the WebService class """


from __future__ import absolute_import

import binascii
import hashlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

import cherrypy
import msgpack
import requests
import six
import ujson as json
from cherrypy.lib.static import serve_file
from decorator import decorator
from peewee import DoesNotExist
from six.moves.urllib.parse import urlparse, urlunparse

import constants
import gateway
from gateway.api.serializers import GroupActionSerializer, InputSerializer, \
    ModuleSerializer, OutputSerializer, OutputStateSerializer, \
    PulseCounterSerializer, RoomSerializer, ScheduleSerializer, \
    SensorSerializer, ShutterGroupSerializer, ShutterSerializer, \
    ThermostatSerializer, VentilationSerializer, VentilationStatusSerializer, \
    ThermostatGroupStatusSerializer, ThermostatGroupSerializer, \
    ThermostatAircoStatusSerializer, PumpGroupSerializer, \
    GlobalRTD10Serializer, RTD10Serializer, GlobalFeedbackSerializer
from gateway.dto import RoomDTO, ScheduleDTO, UserDTO, ModuleDTO, ThermostatDTO, \
    GlobalRTD10DTO
from gateway.enums import ShutterEnums, UserEnums
from gateway.exceptions import UnsupportedException
from gateway.hal.master_controller import CommunicationFailure
from gateway.maintenance_communicator import InMaintenanceModeException
from gateway.mappers.thermostat import ThermostatMapper
from gateway.models import Database, Feature, Config
from gateway.websockets import EventsSocket, MaintenanceSocket, \
    MetricsSocket, OMPlugin, OMSocketTool
from ioc import INJECTED, Inject, Injectable, Singleton
from platform_utils import Hardware, Platform, System
from power.power_communicator import InAddressModeException
from serial_utils import CommunicationTimedOutException
from toolbox import Toolbox

if False:  # MYPY
    from typing import Dict, Optional, Any, List, Literal
    from bus.om_bus_client import MessageClient
    from gateway.gateway_api import GatewayApi
    from gateway.group_action_controller import GroupActionController
    from gateway.hal.frontpanel_controller import FrontpanelController
    from gateway.input_controller import InputController
    from gateway.maintenance_controller import MaintenanceController
    from gateway.metrics_collector import MetricsCollector
    from gateway.metrics_controller import MetricsController
    from gateway.module_controller import ModuleController
    from gateway.output_controller import OutputController
    from gateway.pulse_counter_controller import PulseCounterController
    from gateway.room_controller import RoomController
    from gateway.scheduling import SchedulingController
    from gateway.sensor_controller import SensorController
    from gateway.shutter_controller import ShutterController
    from gateway.thermostat.thermostat_controller import ThermostatController
    from gateway.user_controller import UserController
    from gateway.ventilation_controller import VentilationController
    from plugins.base import PluginController

logger = logging.getLogger("openmotics")


class FloatWrapper(float):
    """ Wrapper for float value that limits the number of digits when printed. """

    def __repr__(self):
        return '%.2f' % self


class BadRequestException(Exception):
    pass


def limit_floats(struct):
    """
    Usage: json.dumps(limit_floats(struct)). This limits the number of digits in the json string.
    :param struct: Structure of which floats will be shortended
    """
    if isinstance(struct, (list, tuple)):
        return [limit_floats(element) for element in struct]
    elif isinstance(struct, dict):
        return dict((key, limit_floats(value)) for key, value in struct.items())
    elif isinstance(struct, float):
        return FloatWrapper(struct)
    else:
        return struct


def error_generic(status, message, *args, **kwargs):
    _ = args, kwargs
    cherrypy.response.headers["Content-Type"] = "application/json"
    cherrypy.response.status = status
    return json.dumps({"success": False, "msg": message})


def error_unexpected():
    cherrypy.response.headers["Content-Type"] = "application/json"
    cherrypy.response.status = 500  # Internal Server Error
    return json.dumps({"success": False, "msg": "unknown_error"})


cherrypy.config.update({'error_page.404': error_generic,
                        'error_page.401': error_generic,
                        'error_page.503': error_generic,
                        'request.error_response': error_unexpected})


def params_parser(params, param_types):
    for key in set(params).intersection(set(param_types)):
        value = params[key]
        if value is None:
            continue
        if isinstance(value, six.string_types) and value.lower() in ['null', 'none', '']:
            params[key] = None
        else:
            if isinstance(param_types[key], list):
                if value not in param_types[key]:
                    raise ValueError('Value has invalid value')
            elif param_types[key] == bool:
                params[key] = str(value).lower() not in ['false', '0', '0.0', 'no']
            elif param_types[key] == 'json':
                params[key] = json.loads(value)
            elif param_types[key] == int:
                # Double convertion. Params come in as strings, and int('0.0') fails, while int(float('0.0')) works as expected
                params[key] = int(float(value))
            else:
                params[key] = param_types[key](value)


def params_handler(**kwargs):
    """ Converts/parses/loads specified request params. """
    request = cherrypy.request
    response = cherrypy.response
    try:
        if request.method in request.methods_with_bodies:
            body = request.body.read()
            if body:
                request.params['request_body'] = body
    except Exception:
        response.headers['Content-Type'] = 'application/json'
        response.status = 406  # No Acceptable
        contents = json.dumps({'success': False, 'msg': 'invalid_body'})
        response.body = contents.encode()
        request.handler = None
        return
    try:
        params_parser(request.params, kwargs)
    except ValueError:
        response.headers['Content-Type'] = 'application/json'
        response.status = 406  # No Acceptable
        contents = json.dumps({'success': False, 'msg': 'invalid_parameters'})
        response.body = contents.encode()
        request.handler = None


def cors_handler():
    if cherrypy.request.method == 'OPTIONS':
        cherrypy.request.handler = None
    cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'
    cherrypy.response.headers['Access-Control-Allow-Headers'] = 'Authorization'
    cherrypy.response.headers['Access-Control-Allow-Methods'] = 'GET'


def authentication_handler(pass_token=False):
    request = cherrypy.request
    if request.method == 'OPTIONS':
        return
    try:
        token = None
        if 'token' in request.params:
            token = request.params.pop('token')
        if token is None:
            header = request.headers.get('Authorization')
            if header is not None and 'Bearer ' in header:
                token = header.replace('Bearer ', '')
        if token is None:
            header = request.headers.get('Sec-WebSocket-Protocol')
            if header is not None and 'authorization.bearer.' in header:
                unpadded_base64_token = header.replace('authorization.bearer.', '')
                base64_token = unpadded_base64_token + '=' * (-len(unpadded_base64_token) % 4)
                try:
                    token = binascii.a2b_base64(base64_token).decode('utf-8')
                except Exception:
                    pass
        _self = request.handler.callable.__self__
        if request.remote.ip != '127.0.0.1':
            check_token = _self._user_controller.check_token if hasattr(_self, '_user_controller') else _self.webinterface.check_token
            if not check_token(token):
                raise RuntimeError()
        if pass_token is True:
            request.params['token'] = token
    except Exception:
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.status = 401  # Unauthorized
        contents = json.dumps({'success': False, 'msg': 'invalid_token'})
        cherrypy.response.body = contents.encode()
        request.handler = None


cherrypy.tools.cors = cherrypy.Tool('before_handler', cors_handler, priority=10)
cherrypy.tools.authenticated = cherrypy.Tool('before_handler', authentication_handler)
cherrypy.tools.params = cherrypy.Tool('before_handler', params_handler)


@decorator
def _openmotics_api(f, *args, **kwargs):
    start = time.time()
    timings = {}
    status = 200  # OK
    try:
        return_data = f(*args, **kwargs)
        data = limit_floats(dict(list({'success': True}.items()) + list(return_data.items())))
    except cherrypy.HTTPError as ex:
        status = ex.status
        data = {'success': False, 'msg': ex._message}
    except (InMaintenanceModeException, InAddressModeException):
        status = 503  # Service Unavailable
        data = {'success': False, 'msg': 'maintenance_mode'}
    except CommunicationTimedOutException:
        logger.error('Communication timeout during API call %s', f.__name__)
        status = 200  # OK
        data = {'success': False, 'msg': 'Internal communication timeout'}
    except CommunicationFailure:
        logger.error('Communication failure during API call %s', f.__name__)
        status = 503  # Service Unavailable
        data = {'success': False, 'msg': 'Internal communication failure'}
    except DoesNotExist as ex:
        class_name = ex.__class__.__name__
        if class_name != 'DoesNotExist' and class_name.endswith('DoesNotExist'):
            class_name = class_name.replace('DoesNotExist', '')
        else:
            class_name = 'Object'
        status = 200  # OK
        logger.error('Could not find the {0}'.format(class_name))
        data = {'success': False, 'msg': '{0} not found'.format(class_name)}
    except UnsupportedException:
        logger.error('Some features for API call %s are unsupported on this device', f.__name__)
        status = 200  # OK
        data = {'success': False, 'msg': 'Unsupported'}
    except Exception as ex:
        logger.exception('Unexpected error during API call %s', f.__name__)
        status = 200  # OK
        data = {'success': False, 'msg': str(ex)}
    timings['process'] = ('Processing', time.time() - start)
    serialization_start = time.time()
    contents = json.dumps(data)
    timings['serialization'] = 'Serialization', time.time() - serialization_start
    cherrypy.response.headers['Content-Type'] = 'application/json'
    cherrypy.response.headers['Server-Timing'] = ','.join(['{0}={1}; "{2}"'.format(key, value[1] * 1000, value[0])
                                                           for key, value in timings.items()])
    if hasattr(f, 'deprecated') and f.deprecated is not None:
        cherrypy.response.headers['Warning'] = 'Warning: 299 - "Deprecated, replaced by: {0}"'.format(f.deprecated)
    cherrypy.response.status = status
    return contents.encode()


def openmotics_api(auth=False, check=None, pass_token=False, plugin_exposed=True, deprecated=None):
    def wrapper(func):
        func.deprecated = deprecated
        func = _openmotics_api(func)
        if auth is True:
            func = cherrypy.tools.authenticated(pass_token=pass_token)(func)
        func = cherrypy.tools.params(**(check or {}))(func)
        func.exposed = True
        func.plugin_exposed = plugin_exposed
        func.check = check
        return func
    return wrapper


def types(**kwargs):
    return kwargs


@Injectable.named('web_interface')
@Singleton
class WebInterface(object):
    """ This class defines the web interface served by cherrypy. """

    @Inject
    def __init__(self, user_controller=INJECTED, gateway_api=INJECTED, maintenance_controller=INJECTED,
                 message_client=INJECTED, scheduling_controller=INJECTED,
                 thermostat_controller=INJECTED, shutter_controller=INJECTED, output_controller=INJECTED,
                 room_controller=INJECTED, input_controller=INJECTED, sensor_controller=INJECTED,
                 pulse_counter_controller=INJECTED, group_action_controller=INJECTED,
                 frontpanel_controller=INJECTED, module_controller=INJECTED, ventilation_controller=INJECTED):
        """
        Constructor for the WebInterface.
        """
        self._user_controller = user_controller  # type: UserController
        self._scheduling_controller = scheduling_controller  # type: SchedulingController
        self._thermostat_controller = thermostat_controller  # type: ThermostatController
        self._shutter_controller = shutter_controller  # type: ShutterController
        self._output_controller = output_controller  # type: OutputController
        self._room_controller = room_controller  # type: RoomController
        self._input_controller = input_controller  # type: InputController
        self._sensor_controller = sensor_controller  # type: SensorController
        self._pulse_counter_controller = pulse_counter_controller  # type: PulseCounterController
        self._group_action_controller = group_action_controller  # type: GroupActionController
        self._frontpanel_controller = frontpanel_controller  # type: Optional[FrontpanelController]
        self._module_controller = module_controller  # type: ModuleController
        self._ventilation_controller = ventilation_controller  # type: VentilationController

        self._gateway_api = gateway_api  # type: GatewayApi
        self._maintenance_controller = maintenance_controller  # type: MaintenanceController
        self._message_client = message_client  # type: Optional[MessageClient]
        self._plugin_controller = None  # type: Optional[PluginController]
        self._metrics_collector = None  # type: Optional[MetricsCollector]
        self._metrics_controller = None  # type: Optional[MetricsController]

        self._ws_metrics_registered = False
        self._power_dirty = False
        self._service_state = False

    def in_authorized_mode(self):
        # type: () -> bool
        if self._frontpanel_controller:
            return self._frontpanel_controller.authorized_mode
        else:
            return False

    def set_service_state(self, state):
        self._service_state = state

    def distribute_metric(self, metric):
        try:
            answers = cherrypy.engine.publish('get-metrics-receivers')
            if not answers:
                return
            receivers = answers.pop()
            for client_id in receivers.keys():
                receiver_info = receivers.get(client_id)
                if receiver_info is None:
                    continue
                try:
                    if cherrypy.request.remote.ip != '127.0.0.1' and not self._user_controller.check_token(receiver_info['token']):
                        raise cherrypy.HTTPError(401, 'invalid_token')
                    sources = self._metrics_controller.get_filter('source', receiver_info['source'])
                    metric_types = self._metrics_controller.get_filter('metric_type', receiver_info['metric_type'])
                    if metric['source'] in sources and metric['type'] in metric_types:
                        receiver_info['socket'].send(msgpack.dumps(metric), binary=True)
                except cherrypy.HTTPError as ex:  # As might be caught from the `check_token` function
                    receiver_info['socket'].close(ex.code, ex.message)
                except Exception as ex:
                    logger.error('Failed to distribute metrics to WebSocket: %s', ex)
                    cherrypy.engine.publish('remove-metrics-receiver', client_id)
        except Exception as ex:
            logger.error('Failed to distribute metrics to WebSockets: %s', ex)

    def send_event_websocket(self, event):
        try:
            answers = cherrypy.engine.publish('get-events-receivers')
            if not answers:
                return
            receivers = answers.pop()
            for client_id in receivers.keys():
                receiver_info = receivers.get(client_id)
                if receiver_info is None:
                    continue
                try:
                    if event.type not in receiver_info['subscribed_types']:
                        continue
                    if cherrypy.request.remote.ip != '127.0.0.1' and not self._user_controller.check_token(receiver_info['token']):
                        raise cherrypy.HTTPError(401, 'invalid_token')
                    receiver_info['socket'].send(msgpack.dumps(event.serialize()), binary=True)
                except cherrypy.HTTPError as ex:  # As might be caught from the `check_token` function
                    receiver_info['socket'].close(ex.code, ex.message)
                except Exception as ex:
                    logger.error('Failed to distribute events to WebSocket: %s', ex)
                    cherrypy.engine.publish('remove-events-receiver', client_id)
        except Exception as ex:
            logger.error('Failed to distribute events to WebSockets: %s', ex)

    def set_plugin_controller(self, plugin_controller):
        """
        Set the plugin controller.

        :type plugin_controller: plugins.base.PluginController
        """
        self._plugin_controller = plugin_controller

    def set_metrics_collector(self, metrics_collector):
        """ Set the metrics collector """
        self._metrics_collector = metrics_collector

    def set_metrics_controller(self, metrics_controller):
        """ Sets the metrics controller """
        self._metrics_controller = metrics_controller

    @cherrypy.expose
    def index(self):
        """
        Index page of the web service (Gateway GUI)
        :returns: Contents of index.html
        :rtype: str
        """
        static_dir = constants.get_static_dir()
        return serve_file(os.path.join(static_dir, 'index.html'), content_type='text/html')

    @openmotics_api(check=types(accept_terms=bool, timeout=int), plugin_exposed=False)
    def login(self, username, password, accept_terms=None, timeout=None):
        """
        Login to the web service, returns a token if successful, returns HTTP status code 401 otherwise.

        :param username: Name of the user.
        :type username: str
        :param password: Password of the user.
        :type password: str
        :param accept_terms: True if the terms are accepted
        :type accept_terms: bool | None
        :param timeout: Optional session timeout. 30d >= x >= 1h
        :type timeout: int
        :returns: Authentication token
        :rtype: str
        """
        user_dto = UserDTO(username=username)
        user_dto.set_password(password)
        success, data = self._user_controller.login(user_dto, accept_terms, timeout)
        if success is True:
            return {'token': data}
        if data == UserEnums.AuthenticationErrors.TERMS_NOT_ACCEPTED:
            return {'next_step': 'accept_terms'}
        raise cherrypy.HTTPError(401, "invalid_credentials")

    @openmotics_api(auth=True, pass_token=True, plugin_exposed=False)
    def logout(self, token):
        """
        Logout from the web service.

        :returns: 'status': 'OK'
        :rtype: str
        """
        self._user_controller.logout(token)
        return {'status': 'OK'}

    @openmotics_api(plugin_exposed=False)
    def create_user(self, username, password):
        """
        Create a new user using a username and a password. Only possible in authorized mode.

        :param username: Name of the user.
        :type username: str
        :param password: Password of the user.
        :type password: str
        """
        if not self.in_authorized_mode():
            raise cherrypy.HTTPError(401, "unauthorized")
        user_dto = UserDTO(username=username,
                           accepted_terms=0)
        user_dto.set_password(password)
        self._user_controller.save_user(user_dto)
        return {}

    @openmotics_api(plugin_exposed=False)
    def get_usernames(self):
        """
        Get the names of the users on the gateway. Only possible in authorized mode.

        :returns: 'usernames': list of usernames (String).
        :rtype: dict
        """
        if not self.in_authorized_mode():
            raise cherrypy.HTTPError(401, "unauthorized")
        users = self._user_controller.load_users()
        usernames = [user.username for user in users]
        return {'usernames': usernames}

    @openmotics_api(plugin_exposed=False)
    def remove_user(self, username):
        """
        Remove a user. Only possible in authorized mode.

        :param username: Name of the user to remove.
        :type username: str
        """
        if not self.in_authorized_mode():
            raise cherrypy.HTTPError(401, "unauthorized")
        user_dto = UserDTO(username=username)
        self._user_controller.remove_user(user_dto)
        return {}

    @openmotics_api(auth=True, plugin_exposed=False)
    def open_maintenance(self):
        """
        Open maintenance mode, return the port of the maintenance socket.

        :returns: 'port': Port on which the maintenance ssl socket is listening (Integer between 6000 and 7000).
        :rtype: dict
        """
        port = self._maintenance_controller.open_maintenace_socket()
        return {'port': port}

    @openmotics_api(auth=True, check=types(power_on=bool))
    def reset_master(self, power_on=True):
        """
        Perform a cold reset on the master.

        :returns: 'status': 'OK'.
        :rtype: dict
        """
        return self._gateway_api.reset_master(power_on=power_on)

    @openmotics_api(auth=True, plugin_exposed=False, check=types(action=str, size=int, data='json'))
    def raw_master_action(self, action, size=None, data=None):
        # type: (str, int, Optional[List[int]]) -> Dict[str,Any]
        """
        Send a raw action to the master.

            POST /raw_master_action action=ST size=13
            {"literal":"","data":[16,16,15,2,0,0,0,0,76,3,143,95,4],"success":true}
        """
        input_data = data if data is None else bytearray(data)
        return self._gateway_api.raw_master_action(action, size, input_data)

    @openmotics_api(auth=True)
    def module_discover_start(self):  # type: () -> Dict[str, str]
        """ Start the module discover mode on the master. """
        self._gateway_api.module_discover_start()
        return {'status': 'OK'}

    @openmotics_api(auth=True)
    def module_discover_stop(self):  # type: () -> Dict[str, str]
        """ Stop the module discover mode on the master. """
        self._gateway_api.module_discover_stop()
        return {'status': 'OK'}

    @openmotics_api(auth=True)
    def module_discover_status(self):  # type: () -> Dict[str, bool]
        """ Gets the status of the module discover mode on the master. """
        return {'running': self._gateway_api.module_discover_status()}

    @openmotics_api(auth=True)
    def get_module_log(self):  # type: () -> Dict[str, List[Dict[str, Any]]]
        """
        Get the log messages from the module discovery mode. This returns the current log
        messages and clear the log messages.
        """
        return {'log': self._gateway_api.get_module_log()}

    @openmotics_api(auth=True)
    def get_modules(self):
        """
        Get a list of all modules attached and registered with the master.

        :returns: Dict with:
        * 'outputs' (list of module types: O,R,D),
        * 'inputs' (list of input module types: I,T,L,C)
        * 'shutters' (List of modules types: S).
        :rtype: dict
        """
        return self._gateway_api.get_modules()

    @openmotics_api(auth=True, check=types(address=str, fields='json'))
    def get_modules_information(self, address=None, fields=None):  # type: (Optional[str], Optional[List[str]]) -> Dict[str, Any]
        """
        Gets an overview of all modules and information
        :param address: Optional address filter
        :param fields: The field of the module information to get, None if all
        """
        return {'modules': {'master': {module_dto.address: ModuleSerializer.serialize(module_dto=module_dto, fields=fields)
                                       for module_dto in self._module_controller.load_master_modules(address)},
                            'energy': {module_dto.address: ModuleSerializer.serialize(module_dto=module_dto, fields=fields)
                                       for module_dto in self._module_controller.load_energy_modules(address)}}}

    @openmotics_api(auth=True, check=types(old_address=str, new_address=str))
    def replace_module(self, old_address, new_address):  # type: (str, str) -> Dict[str, Any]
        old_module, new_module = self._module_controller.replace_module(old_address, new_address)
        return {'old_module': ModuleSerializer.serialize(old_module, fields=None),
                'new_module': ModuleSerializer.serialize(new_module, fields=None)}

    @openmotics_api(auth=True)
    def get_features(self):
        """
        Returns all available features this Gateway supports. This allows to make flexible clients
        """
        features = [
            'metrics',  # Advanced metrics (including metrics over websockets)
            'dirty_flag',  # A dirty flag that can be used to trigger syncs on power & master
            'scheduling',  # Gateway backed scheduling
            'factory_reset',  # The gateway can be complete reset to factory standard
            'isolated_plugins',  # Plugins run in a separate process, so allow fine-graded control
            'websocket_maintenance',  # Maintenance over websockets
            'shutter_positions',  # Shutter positions
            'ventilation',
        ]

        master_version = self._gateway_api.get_master_version()
        if master_version >= (3, 143, 77):
            features.append('default_timer_disabled')
        if master_version >= (3, 143, 79):
            features.append('100_steps_dimmer')
        if master_version >= (3, 143, 88):
            features.append('input_states')

        for name in ('thermostats_gateway',):
            feature = Feature.get_or_none(name=name)
            if feature and feature.enabled:
                features.append(name)

        return {'features': features}

    @openmotics_api(auth=True)
    def get_platform_details(self):  # type: () -> Dict[str, str]
        return {'platform': Platform.get_platform(),
                'operating_system': System.get_operating_system().get('ID', 'unknown'),
                'hardware': Hardware.get_board_type(),
                'mac_address': Hardware.get_mac_address()}

    @openmotics_api(auth=True, check=types(type=int, id=int))
    def flash_leds(self, type, id):  # type: (int, int) -> Dict[str, str]
        """
        Flash the leds on the module for an output/input/sensor.
        :param type: The module type: output/dimmer (0), input (1), sensor/temperatur (2).
        :param id: The id of the output/input/sensor.
        """
        status = self._gateway_api.flash_leds(type, id)
        return {'status': status}

    @openmotics_api(auth=True)
    def get_status(self):
        """
        Get the status of the master.

        :returns: 'time': hour and minutes (HH:MM), 'date': day, month, year (DD:MM:YYYY), \
            'mode': Integer, 'version': a.b.c and 'hw_version': hardware version (Integer).
        :rtype: dict
        """
        return self._gateway_api.get_status()

    @openmotics_api(auth=True)
    def get_input_status(self):
        """
        Get the status of the inputs.

        :returns: 'status': list of dictionaries with the following keys: id, status.
        """
        return {'status': self._gateway_api.get_input_status()}

    @openmotics_api(auth=True, check=types(id=int, is_on=bool))
    def set_input(self, id, is_on):  # type: (int, bool) -> Dict
        """
        Set the status of a virtual input.
        :param id: The id of the input to set
        :param is_on: Whether the input is on (pressed)
        """
        self._gateway_api.set_input_status(id, is_on)
        return {}

    @openmotics_api(auth=True)
    def get_output_status(self):
        """
        Get the status of the outputs.

        :returns: 'status': list of dictionaries with the following keys: id, status, dimmer and ctimer.
        """
        return {'status': [OutputStateSerializer.serialize(output, None)
                           for output in self._output_controller.get_output_statuses()]}

    @openmotics_api(auth=True, check=types(id=int, is_on=bool, dimmer=int, timer=int))
    def set_output(self, id, is_on, dimmer=None, timer=None):  # type: (int, bool, Optional[int], Optional[int]) -> Dict
        """
        Set the status, dimmer and timer of an output.
        :param id: The id of the output to set
        :param is_on: Whether the output should be on
        :param dimmer: The dimmer value to set, None if unchanged
        :param timer: The timer value to set, None if unchanged
        """
        self._output_controller.set_output_status(id, is_on, dimmer, timer)
        return {}

    @openmotics_api(auth=True)
    def set_all_lights_off(self):
        """ Turn all lights off. """
        self._output_controller.set_all_lights(action='OFF')
        return {}

    @openmotics_api(auth=True, check=types(floor=int))
    def set_all_lights_floor_off(self, floor):
        """ Turn all lights on a given floor off. """
        floor = Toolbox.nonify(floor, 255)
        self._output_controller.set_all_lights(action='OFF', floor_id=floor)
        return {}

    @openmotics_api(auth=True, check=types(floor=int))
    def set_all_lights_floor_on(self, floor):
        """ Turn all lights on a given floor on. """
        floor = Toolbox.nonify(floor, 255)
        self._output_controller.set_all_lights(action='ON', floor_id=floor)
        return {}

    @openmotics_api(auth=True)
    def get_last_inputs(self):
        """
        Get the 5 last pressed inputs during the last 5 minutes.

        :returns: 'inputs': list of tuples (input, output).
        :rtype: dict
        """
        # for backwards compatibility reasons a list of input, output tuples is returned
        inputs = [(changed_input, None) for changed_input in self._gateway_api.get_last_inputs()]
        return {'inputs': inputs}

    # Shutters

    @openmotics_api(auth=True)
    def get_shutter_status(self):  # type: () -> Dict[str, Any]
        """
        Get the status of the shutters.
        :returns: 'status': list of dictionaries with the following keys: id, position.
        """
        return self._shutter_controller.get_states()

    @openmotics_api(auth=True, check=types(id=int, position=int))
    def do_shutter_down(self, id, position=None):  # type: (int, Optional[int]) -> Dict[str, str]
        """
        Make a shutter go down. The shutter stops automatically when the down or specified position is reached
        :param id: The id of the shutter.
        :param position: The desired end position
        """
        self._shutter_controller.shutter_down(id, position)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(id=int, position=int))
    def do_shutter_up(self, id, position=None):  # type: (int, Optional[int]) -> Dict[str, str]
        """
        Make a shutter go up. The shutter stops automatically when the up or specified position is reached
        :param id: The id of the shutter.
        :param position: The desired end position
        """
        self._shutter_controller.shutter_up(id, position)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(id=int))
    def do_shutter_stop(self, id):  # type: (int) -> Dict[str, str]
        """
        Make a shutter stop.
        :param id: The id of the shutter.
        """
        self._shutter_controller.shutter_stop(id)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(id=int, position=int))
    def do_shutter_goto(self, id, position):  # type: (int, int) -> Dict[str, str]
        """
        Make a shutter go up or down to the specified position.
        :param id: The id of the shutter.
        :param position: The desired end position
        """
        self._shutter_controller.shutter_goto(id, position)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(id=int, position=int, direction=[ShutterEnums.Direction.UP, ShutterEnums.Direction.DOWN, ShutterEnums.Direction.STOP]))
    def shutter_report_position(self, id, position, direction=None):  # type: (int, int, Optional[str]) -> Dict[str, str]
        """
        Reports the actual position of a shutter
        :param id: The id of the shutter.
        :param position: The actual position
        :param direction: The direction
        """
        self._shutter_controller.report_shutter_position(id, position, direction)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(id=int))
    def shutter_report_lost_position(self, id):  # type: (int) -> Dict[str, str]
        """
        Reports a shutter has lost it's position
        :param id: The id of the shutter.
        """
        self._shutter_controller.report_shutter_lost_position(id)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(id=int))
    def do_shutter_group_down(self, id):  # type: (int) -> Dict[str, str]
        """
        Make a shutter group go down. The shutters stop automatically when the down position is
        reached (after the predefined number of seconds).
        :param id: The id of the shutter group.
        """
        self._shutter_controller.shutter_group_down(id)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(id=int))
    def do_shutter_group_up(self, id):  # type: (int) -> Dict[str, str]
        """
        Make a shutter group go up. The shutters stop automatically when the up position is
        reached (after the predefined number of seconds).
        :param id: The id of the shutter group.
        """
        self._shutter_controller.shutter_group_up(id)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(id=int))
    def do_shutter_group_stop(self, id):  # type: (int) -> Dict[str, str]
        """
        Make a shutter group stop.
        :param id: The id of the shutter group.
        """
        self._shutter_controller.shutter_group_stop(id)
        return {'status': 'OK'}

    # Thermostats

    @openmotics_api(auth=True)
    def get_thermostat_status(self):  # type: () -> Dict[str, Any]
        """ Get the status of the thermostats. """
        return ThermostatGroupStatusSerializer.serialize(thermostat_group_status_dto=self._thermostat_controller.get_thermostat_status())

    @openmotics_api(auth=True, check=types(thermostat=int, temperature=float))
    def set_current_setpoint(self, thermostat, temperature):  # type: (int, float) -> Dict[str, str]
        """ Set the current setpoint of a thermostat. """
        self._thermostat_controller.set_current_setpoint(thermostat, temperature)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(thermostat_on=bool, automatic=bool, setpoint=int, cooling_mode=bool, cooling_on=bool))
    def set_thermostat_mode(self, thermostat_on, automatic=None, setpoint=None, cooling_mode=False, cooling_on=False):
        """
        Set the global mode of the thermostats. Thermostats can be on or off (thermostat_on),
        can be in cooling or heating (cooling_mode), cooling can be turned on or off (cooling_on).
        The automatic and setpoint parameters are here for backwards compatibility and will be
        applied to all thermostats. To control the automatic and setpoint parameters per thermostat
        use the set_per_thermostat_mode call instead.
        """
        self._thermostat_controller.set_thermostat_mode(thermostat_on, cooling_mode, cooling_on, automatic, setpoint)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(thermostat_id=int, automatic=bool, setpoint=int))
    def set_per_thermostat_mode(self, thermostat_id, automatic, setpoint):
        # type: (int, bool, int) -> Dict[str,Any]
        """
        Set the thermostat mode of a given thermostat. Thermostats can be set to automatic or
        manual, in case of manual a setpoint (0 to 5) can be provided.
        """
        self._thermostat_controller.set_per_thermostat_mode(thermostat_id, automatic, setpoint)
        return {'status': 'OK'}

    @openmotics_api(auth=True)
    def get_airco_status(self):
        """ Get the mode of the airco attached to a all thermostats. """
        airco_status_dto = self._thermostat_controller.load_airco_status()
        return ThermostatAircoStatusSerializer.serialize(airco_status_dto)

    @openmotics_api(auth=True, check=types(thermostat_id=int, airco_on=bool))
    def set_airco_status(self, thermostat_id, airco_on):
        """ Set the mode of the airco attached to a given thermostat. """
        self._thermostat_controller.set_airco_status(thermostat_id, airco_on)
        return {'status': 'OK'}

    # Ventilation

    # methods=['GET']
    @openmotics_api(auth=True, check=types(fields='json'))
    def get_ventilation_configurations(self, fields=None):
        # type: (Optional[List[str]]) -> Dict[str, Any]
        ventilation_dtos = self._ventilation_controller.load_ventilations()
        return {'config': [VentilationSerializer.serialize(ventilation_dto, fields)
                           for ventilation_dto in ventilation_dtos]}

    # methods=['GET']
    @openmotics_api(auth=True, check=types(ventilation_id=int, fields='json'))
    def get_ventilation_configuration(self, ventilation_id, fields=None):
        # type: (int, Optional[List[str]]) -> Dict[str, Any]
        ventilation_dto = self._ventilation_controller.load_ventilation(ventilation_id)
        return {'config': VentilationSerializer.serialize(ventilation_dto, fields)}

    # methods=['POST']
    @openmotics_api(auth=True, check=types(config='json'))
    def set_ventilation_configuration(self, config):
        # type: (Dict[str,Any]) -> Dict[str, Any]
        ventilation_dto = VentilationSerializer.deserialize(config)
        self._ventilation_controller.save_ventilation(ventilation_dto)
        return {'config': VentilationSerializer.serialize(ventilation_dto, fields=None)}

    # methods=['GET']
    @openmotics_api(auth=True, check=types(fields='json'))
    def get_ventilation_status(self, fields=None):
        # type: (Optional[List[str]]) -> Dict[str, Any]
        status = self._ventilation_controller.get_status()
        return {'status': [VentilationStatusSerializer.serialize(status_dto, fields)
                           for status_dto in status]}

    # methods=['PUT']
    @openmotics_api(auth=True, check=types(status='json'))
    def set_ventilation_status(self, status):
        # type: (Dict[str,Any]) -> Dict[str, Any]
        """
        Update the current ventilation status, used by plugins to report the current
        status of devices.
        """
        status_dto = VentilationStatusSerializer.deserialize(status)
        status_dto = self._ventilation_controller.set_status(status_dto)
        return {'status': VentilationStatusSerializer.serialize(status_dto, fields=None)}

    # methods=['POST']
    @openmotics_api(auth=True, check=types(ventilation_id=int))
    def set_ventilation_mode_auto(self, ventilation_id):
        # type: (int) -> Dict[str, Any]
        self._ventilation_controller.set_mode_auto(ventilation_id)
        return {}

    # methods=['POST']
    @openmotics_api(auth=True, check=types(ventilation_id=int, level=int, timer=float))
    def set_ventilation_level(self, ventilation_id, level, timer=None):
        # type: (int, int, Optional[float]) -> Dict[str, Any]
        self._ventilation_controller.set_level(ventilation_id, level, timer)
        return {}

    @openmotics_api(auth=True)
    def get_sensor_temperature_status(self):  # type: () -> Dict[str, Any]
        """
        Get the current temperature of all sensors as a list of N values, one for each sensor
        """
        return {'status': self._gateway_api.get_sensors_temperature_status()}

    @openmotics_api(auth=True)
    def get_sensor_humidity_status(self):  # type: () -> Dict[str, Any]
        """
        Get the current humidity of all sensors as a list of N values, one for each sensor
        """
        return {'status': self._gateway_api.get_sensors_humidity_status()}

    @openmotics_api(auth=True)
    def get_sensor_brightness_status(self):  # type: () -> Dict[str, Any]
        """
        Get the current brightness of all sensors as a list of N values, one for each sensor
        """
        return {'status': self._gateway_api.get_sensors_brightness_status()}

    @openmotics_api(auth=True, check=types(sensor_id=int, temperature=float, humidity=float, brightness=int))
    def set_virtual_sensor(self, sensor_id, temperature, humidity, brightness):
        """
        Set the temperature, humidity and brightness value of a virtual sensor.

        :param sensor_id: The id of the sensor.
        :param temperature: The temperature to set in degrees Celcius
        :param humidity: The humidity to set in percentage
        :param brightness: The brightness to set in percentage
        """
        self._gateway_api.set_virtual_sensor(sensor_id, temperature, humidity, brightness)
        return {}

    @openmotics_api(auth=True)
    def add_virtual_output_module(self):
        # type: () -> Dict[str, Any]
        """ Adds a new virtual output module. """
        self._module_controller.add_virtual_module(ModuleDTO.ModuleType.OUTPUT)
        return {'status': 'OK'}

    @openmotics_api(auth=True)
    def add_virtual_input_module(self):
        # type: () -> Dict[str, Any]
        """ Adds a new virtual input module. """
        self._module_controller.add_virtual_module(ModuleDTO.ModuleType.INPUT)
        return {'status': 'OK'}

    @openmotics_api(auth=True)
    def add_virtual_dim_control_module(self):
        # type: () -> Dict[str, Any]
        """ Adds a new virtual dim control module """
        self._module_controller.add_virtual_module(ModuleDTO.ModuleType.DIM_CONTROL)
        return {'status': 'OK'}

    @openmotics_api(auth=True)
    def add_virtual_sensor_module(self):
        # type: () -> Dict[str, Any]
        """ Adds a new virtual sensor module """
        self._module_controller.add_virtual_module(ModuleDTO.ModuleType.SENSOR)
        return {'status': 'OK'}

    @openmotics_api(auth=True, check=types(action_type=int, action_number=int))
    def do_basic_action(self, action_type, action_number):
        """
        Execute a basic action.

        :param action_type: The type of the action as defined by the master api.
        :type action_type: int
        :param action_number: The number provided to the basic action, its meaning depends on the action_type.
        :type action_number: int
        """
        self._gateway_api.do_basic_action(action_type, action_number)
        return {}

    @openmotics_api(auth=True, check=types(group_action_id=int))
    def do_group_action(self, group_action_id):  # type: (int) -> Dict[str, Any]
        """
        Execute a group action.
        :param group_action_id: The id of the group action
        """
        self._group_action_controller.do_group_action(group_action_id)
        return {}

    @openmotics_api(auth=True, check=types(status=bool))
    def set_master_status_leds(self, status):
        """
        Set the status of the leds on the master.

        :param status: whether the leds should be on (true) or off (false).
        :type status: bool
        """
        return self._gateway_api.set_master_status_leds(status)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def get_full_backup(self):
        """
        Get a backup (tar) of the master eeprom and the sqlite databases.

        :returns: Tar containing 4 files: master.eep, config.db, scheduled.db, power.db and
            eeprom_extensions.db as a string of bytes.
        :rtype: dict
        """
        cherrypy.response.headers['Content-Type'] = 'application/octet-stream'
        return self._gateway_api.get_full_backup()

    @openmotics_api(auth=True, plugin_exposed=False)
    def restore_full_backup(self, backup_data):
        """
        Restore a full backup containing the master eeprom and the sqlite databases.

        :param backup_data: The full backup to restore: tar containing 4 files: master.eep, config.db, \
            scheduled.db, power.db and eeprom_extensions.db as a string of bytes.
        :type backup_data: multipart/form-data encoded bytes.
        :returns: dict with 'output' key.
        :rtype: dict
        """
        data = backup_data.file.read()
        if not data:
            raise RuntimeError('backup_data is empty')
        return self._gateway_api.restore_full_backup(data)

    @cherrypy.expose
    @cherrypy.tools.authenticated()
    def get_master_backup(self):
        """
        Get a backup of the eeprom of the master.

        :returns: This function does not return a dict, unlike all other API functions: it \
            returns a string of bytes (size = 64kb).
        :rtype: bytearray
        """
        cherrypy.response.headers['Content-Type'] = 'application/octet-stream'
        return self._gateway_api.get_master_backup()

    @openmotics_api(auth=True)
    def master_restore(self, data):
        """
        Restore a backup of the eeprom of the master.

        :param data: The eeprom backup to restore.
        :type data: multipart/form-data encoded bytes (size = 64 kb).
        :returns: 'output': array with the addresses that were written.
        :rtype: dict
        """
        data = data.file.read()
        return self._gateway_api.master_restore(data)

    @openmotics_api(auth=True)
    def get_errors(self):
        """
        Get the number of seconds since the last successul communication with the master and
        power modules (master_last_success, power_last_success) and the error list per module
        (input and output modules). The modules are identified by O1, O2, I1, I2, ...

        :returns: 'errors': list of tuples (module, nr_errors), 'master_last_success': UNIX \
            timestamp of the last succesful master communication and 'power_last_success': UNIX \
            timestamp of the last successful power communication.
        :rtype: dict
        """
        try:
            errors = self._gateway_api.master_error_list()
        except Exception:
            # In case of communications problems with the master.
            errors = []

        master_last = self._gateway_api.master_last_success()
        power_last = self._gateway_api.power_last_success()

        return {'errors': errors,
                'master_last_success': master_last,
                'power_last_success': power_last}

    @openmotics_api(auth=True)
    def master_clear_error_list(self):
        """
        Clear the number of errors.
        """
        return self._gateway_api.master_clear_error_list()

    @openmotics_api(auth=True)
    def master_diagnostics(self):
        return {'master_last_success': self._gateway_api.master_last_success(),
                'command_histograms': self._gateway_api.master_command_histograms(),
                'communication_statistics': self._gateway_api.master_communication_statistics()}

    # Output configurations

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_output_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific output_configuration defined by its id.
        :param id: The id of the output_configuration
        :param fields: The fields of the output_configuration to get, None if all
        """
        return {'config': OutputSerializer.serialize(output_dto=self._output_controller.load_output(output_id=id),
                                                     fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_output_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all output_configurations.
        :param fields: The field of the output_configuration to get, None if all
        """
        return {'config': [OutputSerializer.serialize(output_dto=output, fields=fields)
                           for output in self._output_controller.load_outputs()]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_output_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one output_configuration. """
        data = OutputSerializer.deserialize(config)
        self._output_controller.save_outputs([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_output_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple output_configurations. """
        data = [OutputSerializer.deserialize(entry) for entry in config]
        self._output_controller.save_outputs(data)
        return {}

    # Shutter configurations

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_shutter_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific shutter_configuration defined by its id.
        :param id: The id of the shutter_configuration
        :param fields: The fields of the shutter_configuration to get, None if all
        """
        return {'config': ShutterSerializer.serialize(shutter_dto=self._shutter_controller.load_shutter(id),
                                                      fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_shutter_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all shutter_configurations.
        :param fields: The fields of the shutter_configuration to get, None if all
        """
        return {'config': [ShutterSerializer.serialize(shutter_dto=shutter, fields=fields)
                           for shutter in self._shutter_controller.load_shutters()]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_shutter_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one shutter_configuration. """
        data = ShutterSerializer.deserialize(config)
        self._shutter_controller.save_shutters([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_shutter_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple shutter_configurations. """
        data = [ShutterSerializer.deserialize(entry) for entry in config]
        self._shutter_controller.save_shutters(data)
        return {}

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_shutter_group_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific shutter_group_configuration defined by its id.
        :param id: The id of the shutter_group_configuration
        :param fields: The field of the shutter_group_configuration to get, None if all
        """
        return {'config': ShutterGroupSerializer.serialize(shutter_group_dto=self._shutter_controller.load_shutter_group(id),
                                                           fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_shutter_group_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all shutter_group_configurations.
        :param fields: The field of the shutter_group_configuration to get, None if all
        """
        return {'config': [ShutterGroupSerializer.serialize(shutter_group_dto=shutter_group, fields=fields)
                           for shutter_group in self._shutter_controller.load_shutter_groups()]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_shutter_group_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one shutter_group_configuration. """
        data = ShutterGroupSerializer.deserialize(config)
        self._shutter_controller.save_shutter_groups([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_shutter_group_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple shutter_group_configurations. """
        data = [ShutterGroupSerializer.deserialize(entry) for entry in config]
        self._shutter_controller.save_shutter_groups(data)
        return {}

    # Input configuration

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_input_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific input_configuration defined by its id.
        :param id: The id of the input_configuration
        :param fields: The field of the input_configuration to get, None if all
        """
        return {'config': InputSerializer.serialize(input_dto=self._input_controller.load_input(input_id=id),
                                                    fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_input_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all input_configurations.
        :param fields: The field of the input_configuration to get, None if all
        """
        return {'config': [InputSerializer.serialize(input_dto=input_, fields=fields)
                           for input_ in self._input_controller.load_inputs()]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_input_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one input_configuration. """
        data = InputSerializer.deserialize(config)
        self._input_controller.save_inputs([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_input_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple input_configurations. """
        data = [InputSerializer.deserialize(entry) for entry in config]
        self._input_controller.save_inputs(data)
        return {}

    # Heating thermostats

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_thermostat_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific thermostat_configuration defined by its id.
        :param id: The id of the thermostat_configuration
        :param fields: The field of the thermostat_configuration to get, None if all
        """
        try:
            thermostat_dto = self._thermostat_controller.load_heating_thermostat(id)
        except DoesNotExist:
            if id >= 32:
                raise
            mode = 'heating'  # type: Literal['heating']
            thermostat_dto = ThermostatMapper.get_default_dto(thermostat_id=id, mode=mode)
        return {'config': ThermostatSerializer.serialize(thermostat_dto=thermostat_dto,
                                                         fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_thermostat_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all thermostat_configurations.
        :param fields: The field of the thermostat_configuration to get, None if all
        """
        mode = 'heating'  # type: Literal['heating']
        thermostat_dtos = {thermostat.id: thermostat
                           for thermostat in self._thermostat_controller.load_heating_thermostats()}
        all_dtos = []
        for thermostat_id in set(list(thermostat_dtos.keys()) + list(range(32))):
            all_dtos.append(thermostat_dtos.get(thermostat_id, ThermostatMapper.get_default_dto(thermostat_id=thermostat_id,
                                                                                                mode=mode)))
        return {'config': [ThermostatSerializer.serialize(thermostat_dto=thermostat, fields=fields)
                           for thermostat in all_dtos]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_thermostat_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one thermostat_configuration. """
        data = ThermostatSerializer.deserialize(config)
        self._thermostat_controller.save_heating_thermostats([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_thermostat_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple thermostat_configurations. """
        data = [ThermostatSerializer.deserialize(entry) for entry in config]
        self._thermostat_controller.save_heating_thermostats(data)
        return {}

    # Sensor configurations

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_sensor_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific sensor_configuration defined by its id.
        :param id: The id of the sensor_configuration
        :param fields: The field of the sensor_configuration to get, None if all
        """
        return {'config': SensorSerializer.serialize(sensor_dto=self._sensor_controller.load_sensor(sensor_id=id),
                                                     fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_sensor_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all sensor_configurations.
        :param fields: The field of the sensor_configuration to get, None if all
        """
        return {'config': [SensorSerializer.serialize(sensor_dto=sensor, fields=fields)
                           for sensor in self._sensor_controller.load_sensors()]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_sensor_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one sensor_configuration. """
        data = SensorSerializer.deserialize(config)
        self._sensor_controller.save_sensors([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_sensor_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple sensor_configurations. """
        data = [SensorSerializer.deserialize(entry) for entry in config]
        self._sensor_controller.save_sensors(data)
        return {}

    # Heating Pump Group

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_pump_group_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific heating pump_group_configuration defined by its id.
        :param id: The id of the heating pump_group_configuration
        :param fields: The field of the heating pump_group_configuration to get, None if all
        """
        pump_group_dto = self._thermostat_controller.load_heating_pump_group(pump_group_id=id)
        return {'config': PumpGroupSerializer.serialize(pump_group_dto=pump_group_dto,
                                                        fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_pump_group_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all heating pump_group_configurations.
        :param fields: The field of the heating pump_group_configuration to get, None if all
        """
        pump_group_dtos = self._thermostat_controller.load_heating_pump_groups()
        return {'config': [PumpGroupSerializer.serialize(pump_group_dto=pump_group, fields=fields)
                           for pump_group in pump_group_dtos]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_pump_group_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one heating pump_group_configuration. """
        data = PumpGroupSerializer.deserialize(config)
        self._thermostat_controller.save_heating_pump_groups([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_pump_group_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple heating pump_group_configurations. """
        data = [PumpGroupSerializer.deserialize(entry) for entry in config]
        self._thermostat_controller.save_heating_pump_groups(data)
        return {}

    # Cooling thermostats

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_cooling_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific cooling_configuration defined by its id.
        :param id: The id of the cooling_configuration
        :param fields: The field of the cooling_configuration to get, None if all
        """
        try:
            thermostat_dto = self._thermostat_controller.load_cooling_thermostat(id)
        except DoesNotExist:
            if id >= 32:
                raise
            mode = 'cooling'  # type: Literal['cooling']
            thermostat_dto = ThermostatMapper.get_default_dto(thermostat_id=id, mode=mode)
        return {'config': ThermostatSerializer.serialize(thermostat_dto=thermostat_dto,
                                                         fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_cooling_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all cooling_configurations.
        :param fields: The field of the cooling_configuration to get, None if all
        """
        mode = 'cooling'  # type: Literal['cooling']
        thermostat_dtos = {thermostat.id: thermostat
                           for thermostat in self._thermostat_controller.load_cooling_thermostats()}
        all_dtos = []
        for thermostat_id in set(list(thermostat_dtos.keys()) + list(range(32))):
            all_dtos.append(thermostat_dtos.get(thermostat_id, ThermostatMapper.get_default_dto(thermostat_id=thermostat_id,
                                                                                                mode=mode)))
        return {'config': [ThermostatSerializer.serialize(thermostat_dto=thermostat, fields=fields)
                           for thermostat in all_dtos]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_cooling_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one cooling_configuration. """
        data = ThermostatSerializer.deserialize(config)
        self._thermostat_controller.save_cooling_thermostats([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_cooling_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple cooling_configurations. """
        data = [ThermostatSerializer.deserialize(entry) for entry in config]
        self._thermostat_controller.save_cooling_thermostats(data)
        return {}

    # Cooling Pump Groups

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_cooling_pump_group_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific cooling pump_group_configuration defined by its id.
        :param id: The id of the cooling pump_group_configuration
        :param fields: The field of the cooling pump_group_configuration to get, None if all
        """
        return {'config': PumpGroupSerializer.serialize(pump_group_dto=self._thermostat_controller.load_cooling_pump_group(pump_group_id=id),
                                                        fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_cooling_pump_group_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all cooling pump_group_configurations.
        :param fields: The field of the cooling pump_group_configuration to get, None if all
        """
        return {'config': [PumpGroupSerializer.serialize(pump_group_dto=pump_group, fields=fields)
                           for pump_group in self._thermostat_controller.load_cooling_pump_groups()]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_cooling_pump_group_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one cooling pump_group_configuration. """
        data = PumpGroupSerializer.deserialize(config)
        self._thermostat_controller.save_cooling_pump_groups([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_cooling_pump_group_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple cooling pump_group_configurations. """
        data = [PumpGroupSerializer.deserialize(entry) for entry in config]
        self._thermostat_controller.save_cooling_pump_groups(data)
        return {}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_global_rtd10_configuration(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get the global_rtd10_configuration.
        :param fields: The field of the global_rtd10_configuration to get, None if all
        """
        try:
            global_rtd10_dto = self._thermostat_controller.load_global_rtd10()
        except UnsupportedException:
            global_rtd10_dto = GlobalRTD10DTO()  # Backwards compatibility
        return {'config': GlobalRTD10Serializer.serialize(global_rtd10_dto=global_rtd10_dto, fields=fields)}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_global_rtd10_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set the global_rtd10_configuration. """
        data = GlobalRTD10Serializer.deserialize(config)
        self._thermostat_controller.save_global_rtd10(data)
        return {}

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_rtd10_heating_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific rtd10_heating_configuration defined by its id.
        :param fields: The field of the rtd10_heating_configuration to get, None if all
        """
        return {'config': RTD10Serializer.serialize(rtd10_dto=self._thermostat_controller.load_heating_rtd10(id),
                                                    fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_rtd10_heating_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all rtd10_heating_configurations.
        :param fields: The field of the rtd10_heating_configuration to get, None if all
        """
        try:
            return {'config': [RTD10Serializer.serialize(rtd10_dto=rtd10_dto, fields=fields)
                               for rtd10_dto in self._thermostat_controller.load_heating_rtd10s()]}
        except UnsupportedException:
            return {'config': []}  # Backwards compatibility

    @openmotics_api(auth=True, check=types(config='json'))
    def set_rtd10_heating_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one rtd10_heating_configuration. """
        data = RTD10Serializer.deserialize(config)
        self._thermostat_controller.save_heating_rtd10s([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_rtd10_heating_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple rtd10_heating_configurations. """
        data = [RTD10Serializer.deserialize(entry) for entry in config]
        self._thermostat_controller.save_heating_rtd10s(data)
        return {}

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_rtd10_cooling_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific rtd10_cooling_configuration defined by its id.
        :param fields: The field of the rtd10_cooling_configuration to get, None if all
        """
        return {'config': RTD10Serializer.serialize(rtd10_dto=self._thermostat_controller.load_cooling_rtd10(id),
                                                    fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_rtd10_cooling_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all rtd10_cooling_configurations.
        :param fields: The field of the rtd10_cooling_configuration to get, None if all
        """
        try:
            return {'config': [RTD10Serializer.serialize(rtd10_dto=rtd10_dto, fields=fields)
                               for rtd10_dto in self._thermostat_controller.load_cooling_rtd10s()]}
        except UnsupportedException:
            return {'config': []}  # Backwards compatibility

    @openmotics_api(auth=True, check=types(config='json'))
    def set_rtd10_cooling_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one rtd10_cooling_configuration. """
        data = RTD10Serializer.deserialize(config)
        self._thermostat_controller.save_cooling_rtd10s([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_rtd10_cooling_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple rtd10_cooling_configurations. """
        data = [RTD10Serializer.deserialize(entry) for entry in config]
        self._thermostat_controller.save_cooling_rtd10s(data)
        return {}

    # Group Actions

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_group_action_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific group_action_configuration defined by its id.
        :param id: The id of the group_action_configuration
        :param fields: The field of the group_action_configuration to get, None if all
        """
        return {'config': GroupActionSerializer.serialize(group_action_dto=self._group_action_controller.load_group_action(id),
                                                          fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_group_action_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all group_action_configurations.
        :param fields: The field of the group_action_configuration to get, None if all
        """
        return {'config': [GroupActionSerializer.serialize(group_action_dto=group_action, fields=fields)
                           for group_action in self._group_action_controller.load_group_actions()]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_group_action_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one group_action_configuration. """
        data = GroupActionSerializer.deserialize(config)
        self._group_action_controller.save_group_actions([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_group_action_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple group_action_configurations. """
        data = [GroupActionSerializer.deserialize(entry) for entry in config]
        self._group_action_controller.save_group_actions(data)
        return {}

    # Schedules

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_scheduled_action_configuration(self, id, fields=None):
        """
        Get a specific scheduled_action_configuration defined by its id.

        :param id: The id of the scheduled_action_configuration
        :type id: int
        :param fields: The field of the scheduled_action_configuration to get. (None gets all fields)
        :type fields: list
        :returns: 'config': scheduled_action_configuration dict: contains 'id' (Id), 'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        :rtype: dict
        """
        return {'config': self._gateway_api.get_scheduled_action_configuration(id, fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_scheduled_action_configurations(self, fields=None):
        """
        Get all scheduled_action_configurations.

        :param fields: The field of the scheduled_action_configuration to get. (None gets all fields)
        :type fields: list
        :returns: 'config': list of scheduled_action_configuration dict: contains 'id' (Id), 'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        :rtype: dict
        """
        return {'config': self._gateway_api.get_scheduled_action_configurations(fields)}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_scheduled_action_configuration(self, config):
        """
        Set one scheduled_action_configuration.

        :param config: The scheduled_action_configuration to set: scheduled_action_configuration dict: contains 'id' (Id), 'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        :type config: dict
        """
        self._gateway_api.set_scheduled_action_configuration(config)
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_scheduled_action_configurations(self, config):
        """
        Set multiple scheduled_action_configurations.

        :param config: The list of scheduled_action_configurations to set: list of scheduled_action_configuration dict: contains 'id' (Id), 'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        :type config: list
        """
        self._gateway_api.set_scheduled_action_configurations(config)
        return {}

    # PulseCounters

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_pulse_counter_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific pulse_counter_configuration defined by its id.
        :param id: The id of the pulse_counter_configuration
        :param fields: The field of the pulse_counter_configuration to get, None if all
        """
        return {'config': PulseCounterSerializer.serialize(pulse_counter_dto=self._pulse_counter_controller.load_pulse_counter(pulse_counter_id=id),
                                                           fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_pulse_counter_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all pulse_counter_configurations.
        :param fields: The field of the pulse_counter_configuration to get, None if all
        """
        return {'config': [PulseCounterSerializer.serialize(pulse_counter_dto=pulse_counter, fields=fields)
                           for pulse_counter in self._pulse_counter_controller.load_pulse_counters()]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_pulse_counter_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one pulse_counter_configuration. """
        data = PulseCounterSerializer.deserialize(config)
        self._pulse_counter_controller.save_pulse_counters([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_pulse_counter_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple pulse_counter_configurations. """
        data = [PulseCounterSerializer.deserialize(entry) for entry in config]
        self._pulse_counter_controller.save_pulse_counters(data)
        return {}

    @openmotics_api(auth=True, check=types(amount=int))
    def set_pulse_counter_amount(self, amount):  # type: (int) -> Dict
        """
        Set the number of pulse counters. The minimum is 24, these are the pulse counters
        that can be linked to an input. An amount greater than 24 will result in virtual
        pulse counter that can be set through the API.
        """
        return {'amount': self._pulse_counter_controller.set_amount_of_pulse_counters(amount)}

    @openmotics_api(auth=True)
    def get_pulse_counter_status(self):  # type: () -> Dict[str, List[Optional[int]]]
        """ Get the pulse counter values. """
        values = self._pulse_counter_controller.get_values()
        return {'counters': [values[number] for number in sorted(values.keys())]}

    @openmotics_api(auth=True, check=types(pulse_counter_id=int, value=int))
    def set_pulse_counter_status(self, pulse_counter_id, value):  # type: (int, int) -> Dict
        """
        Sets a pulse counter to a value. This can only be done for virtual pulse counters,
        with a pulse_counter_id >= 24.
        """
        return {'value': self._pulse_counter_controller.set_value(pulse_counter_id, value)}

    # Startup actions

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_startup_action_configuration(self, fields=None):
        """
        Get the startup_action_configuration.

        :param fields: The field of the startup_action_configuration to get. (None gets all fields)
        :type fields: list
        :returns: 'config': startup_action_configuration dict: contains 'actions' (Actions[100])
        :rtype: dict
        """
        return {'config': self._gateway_api.get_startup_action_configuration(fields)}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_startup_action_configuration(self, config):
        """
        Set the startup_action_configuration.

        :param config: The startup_action_configuration to set: startup_action_configuration dict: contains 'actions' (Actions[100])
        :type config: dict
        """
        self._gateway_api.set_startup_action_configuration(config)
        return {}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_dimmer_configuration(self, fields=None):
        """
        Get the dimmer_configuration.

        :param fields: The field of the dimmer_configuration to get. (None gets all fields)
        :type fields: list
        :returns: 'config': dimmer_configuration dict: contains 'dim_memory' (Byte), 'dim_step' (Byte), 'dim_wait_cycle' (Byte), 'min_dim_level' (Byte)
        :rtype: dict
        """
        return {'config': self._gateway_api.get_dimmer_configuration(fields)}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_dimmer_configuration(self, config):
        """
        Set the dimmer_configuration.

        :param config: The dimmer_configuration to set: dimmer_configuration dict: contains 'dim_memory' (Byte), 'dim_step' (Byte), 'dim_wait_cycle' (Byte), 'min_dim_level' (Byte)
        :type config: dict
        """
        self._gateway_api.set_dimmer_configuration(config)
        return {}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_global_thermostat_configuration(self, fields=None):
        """
        Get the global_thermostat_configuration.
        :param fields: The field of the cooling_configuration to get, None if all
        """
        thermostat_group_dto = self._thermostat_controller.load_thermostat_group()
        return {'config': ThermostatGroupSerializer.serialize(thermostat_group_dto=thermostat_group_dto,
                                                              fields=fields)}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_global_thermostat_configuration(self, config):
        """ Set the global_thermostat_configuration. """
        data = ThermostatGroupSerializer.deserialize(config)
        self._thermostat_controller.save_thermostat_group(data)
        return {}

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_can_led_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific can_led_configuration defined by its id.
        :param id: The id of the can_led_configuration
        :param fields: The field of the can_led_configuration to get, None if all
        """
        return {'config': GlobalFeedbackSerializer.serialize(global_feedback_dto=self._output_controller.load_global_feedback(id),
                                                             fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_can_led_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all can_led_configurations.
        :param fields: The field of the can_led_configuration to get, None if all
        """
        return {'config': [GlobalFeedbackSerializer.serialize(global_feedback_dto=global_feedback, fields=fields)
                           for global_feedback in self._output_controller.load_global_feedbacks()]}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_can_led_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one can_led_configuration. """
        data = GlobalFeedbackSerializer.deserialize(config)
        self._output_controller.save_global_feedbacks([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_can_led_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple can_led_configurations. """
        data = [GlobalFeedbackSerializer.deserialize(entry) for entry in config]
        self._output_controller.save_global_feedbacks(data)
        return {}

    # Room configurations

    @openmotics_api(auth=True, check=types(id=int, fields='json'))
    def get_room_configuration(self, id, fields=None):  # type: (int, Optional[List[str]]) -> Dict[str, Any]
        """
        Get a specific room_configuration defined by its id.
        :param id: The id of the room_configuration
        :param fields: The fields of the room_configuration to get, None if all
        """
        try:
            room_dto = self._room_controller.load_room(room_id=id)
        except DoesNotExist:
            if 0 <= id < 100:
                room_dto = RoomDTO(id=id)
            else:
                raise
        return {'config': RoomSerializer.serialize(room_dto=room_dto,
                                                   fields=fields)}

    @openmotics_api(auth=True, check=types(fields='json'))
    def get_room_configurations(self, fields=None):  # type: (Optional[List[str]]) -> Dict[str, Any]
        """
        Get all room_configuration.
        :param fields: The field of the room_configuration to get, None if all
        """
        data = []
        rooms = {room.id: room for room in self._room_controller.load_rooms()}
        for i in range(100):
            room = rooms.get(i, RoomDTO(id=i))
            data.append(RoomSerializer.serialize(room_dto=room, fields=fields))
        return {'config': data}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_room_configuration(self, config):  # type: (Dict[Any, Any]) -> Dict
        """ Set one room_configuration. """
        data = RoomSerializer.deserialize(config)
        self._room_controller.save_rooms([data])
        return {}

    @openmotics_api(auth=True, check=types(config='json'))
    def set_room_configurations(self, config):  # type: (List[Dict[Any, Any]]) -> Dict
        """ Set multiple room_configuration. """
        data = [RoomSerializer.deserialize(entry) for entry in config]
        self._room_controller.save_rooms(data)
        return {}

    # Extra calls

    @openmotics_api(auth=True)
    def get_reset_dirty_flag(self):
        """
        Gets the dirty flags, and immediately clears them
        """
        power_dirty = self._power_dirty
        self._power_dirty = False
        orm_dirty = Database.get_dirty_flag()
        # eeprom key used here for compatibility
        return {'eeprom': self._gateway_api.get_configuration_dirty_flag(),
                'power': power_dirty,
                'orm': orm_dirty}

    # Energy modules

    @openmotics_api(auth=True)
    def get_power_modules(self):
        """
        Get information on the power modules. The times format is a comma seperated list of
        HH:MM formatted times times (index 0 = start Monday, index 1 = stop Monday,
        index 2 = start Tuesday, ...).

        :returns: 'modules': list of dictionaries with the following keys: 'id', 'name', \
            'address', 'input0', 'input1', 'input2', 'input3', 'input4', 'input5', 'input6', \
            'input7', 'sensor0', 'sensor1', 'sensor2', 'sensor3', 'sensor4', 'sensor5', 'sensor6', \
            'sensor7', 'times0', 'times1', 'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        :rtype: dict
        """
        return {'modules': self._gateway_api.get_power_modules()}

    @openmotics_api(auth=True)
    def set_power_modules(self, modules):
        """
        Set information for the power modules.

        :param modules: json encoded list of dicts with keys: 'id', 'name', 'input0', 'input1', \
            'input2', 'input3', 'input4', 'input5', 'input6', 'input7', 'sensor0', 'sensor1', \
            'sensor2', 'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7', 'times0', 'times1', \
            'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        :type modules: str
        """
        return self._gateway_api.set_power_modules(json.loads(modules))

    @openmotics_api(auth=True)
    def get_realtime_power(self):
        """
        Get the realtime power measurements.

        :returns: module id as the keys: [voltage, frequency, current, power].
        :rtype: dict
        """
        response = {}  # type: Dict[str,List[List[float]]]
        for module_id, items in self._gateway_api.get_realtime_power().items():
            response[module_id] = []
            for realtime_power in items:
                response[module_id].append([realtime_power.voltage,
                                            realtime_power.frequency,
                                            realtime_power.current,
                                            realtime_power.power])
        return response

    @openmotics_api(auth=True)
    def get_total_energy(self):
        """
        Get the total energy (Wh) consumed by the power modules.

        :returns: modules id as key: [day, night].
        :rtype: dict
        """
        return self._gateway_api.get_total_energy()

    @openmotics_api(auth=True)
    def start_power_address_mode(self):
        """
        Start the address mode on the power modules.
        """
        return self._gateway_api.start_power_address_mode()

    @openmotics_api(auth=True)
    def stop_power_address_mode(self):
        """
        Stop the address mode on the power modules.
        """
        self._power_dirty = True
        return self._gateway_api.stop_power_address_mode()

    @openmotics_api(auth=True)
    def in_power_address_mode(self):
        """
        Check if the power modules are in address mode.

        :returns: 'address_mode': Boolean
        :rtype: dict
        """
        return self._gateway_api.in_power_address_mode()

    @openmotics_api(auth=True, check=types(module_id=int, voltage=float))
    def set_power_voltage(self, module_id, voltage):
        """
        Set the voltage for a given module.

        :param module_id: The id of the power module.
        :type module_id: int
        :param voltage: The voltage to set for the power module.
        :type voltage: float
        """
        return self._gateway_api.set_power_voltage(module_id, voltage)

    @openmotics_api(auth=True, check=types(module_id=int, input_id=int))
    def get_energy_time(self, module_id, input_id=None):
        """
        Gets 1 period of given module and optional input (no input means all).

        :param module_id: The id of the power module.
        :type module_id: int
        :param input_id: The id of the input on the given power module
        :type input_id: int or None
        :returns: A dict with the input_id(s) as key, and as value another dict with
                  (up to 80) voltage and current samples.
        :rtype: dict
        """
        return self._gateway_api.get_energy_time(module_id, input_id)

    @openmotics_api(auth=True, check=types(module_id=int, input_id=int))
    def get_energy_frequency(self, module_id, input_id=None):
        """
        Gets the frequency components for a given module and optional input (no input means all)

        :param module_id: The id of the power module
        :type module_id: int
        :param input_id: The id of the input on the given power module
        :type input_id: int | None
        :returns: A dict with the input_id(s) as key, and as value another dict with for
                  voltage and current the 20 frequency components
        :rtype: dict
        """
        return self._gateway_api.get_energy_frequency(module_id, input_id)

    @openmotics_api(auth=True, check=types(address=int), plugin_exposed=False)
    def do_raw_energy_command(self, address, mode, command, data):
        """
        Perform a raw energy module command, for debugging purposes.

        :param address: The address of the energy module
        :type address: int
        :param mode: 1 char: S or G
        :type mode: str
        :param command: 3 char power command
        :type command: str
        :param data: comma seperated list of Bytes
        :type data: str
        :returns: dict with 'data': comma separated list of Bytes
        :rtype: dict
        """
        if mode not in ['S', 'G']:
            raise ValueError("mode not in [S, G]: %s" % mode)

        if len(command) != 3:
            raise ValueError('Command should be 3 chars, got "%s"' % command)

        if data:
            bdata = [int(c) for c in data.split(",")]
        else:
            bdata = []

        ret = self._gateway_api.do_raw_energy_command(address, mode, command, bdata)
        return {'data': ",".join([str(d) for d in ret])}

    @openmotics_api(auth=True)
    def get_version(self):
        """
        Get the version of the openmotics software.

        :returns: 'version': String (a.b.c).
        :rtype: dict
        """
        master_version = self._gateway_api.get_master_version()
        if master_version is not None:
            master_version = ".".join([str(n) for n in master_version] if len(master_version) else None)
        return {'version': self._gateway_api.get_main_version(),
                'gateway': gateway.__version__,
                'master': master_version}

    @openmotics_api(auth=True)
    def get_system_info(self):
        operating_system = System.get_operating_system()
        os_id = operating_system.get('ID', '')
        name = operating_system.get('NAME', '')
        version = operating_system.get('VERSION_ID', 'unknown')
        return {'model': str(Hardware.get_board_type()),
                'operating_system': {'id': str(os_id),
                                     'version': str(version),
                                     'name': str(name)},
                'platform': str(Platform.get_platform())}

    @openmotics_api(auth=True, plugin_exposed=False)
    def update(self, version, md5, update_data=None):
        """
        Perform an update.

        :param version: the new version number.
        :type version: str
        :param md5: the md5 sum of update_data.
        :type md5: str
        :param update_data: a tgz file containing the update script (update.sh) and data.
        :type update_data: multipart/form-data encoded byte string.
        """
        if not os.path.exists(constants.get_update_dir()):
            os.mkdir(constants.get_update_dir())

        if update_data:
            logger.info('using old style update.tgz')
            update_data = update_data.file.read()
            with open(constants.get_update_file(), "wb") as update_file:
                update_file.write(update_data)

        subprocess.Popen(constants.get_update_cmd(version, md5), close_fds=True)

        return {}

    @openmotics_api(auth=True)
    def get_update_output(self):
        """
        Get the output of the last update.

        :returns: 'output': String with the output from the update script.
        :rtype: dict
        """
        with open(constants.get_update_output_file(), "r") as output_file:
            output = output_file.read()
        version = self._gateway_api.get_main_version()

        return {'output': output,
                'version': version}

    @openmotics_api(auth=True, plugin_exposed=False)
    def update_firmware(self, master=None, output=None, input=None, can=None, dimmer=None, temperature=None):
        if master:
            temp_file = self._download_firmware('master_classic', master)
            self._gateway_api.update_master_firmware(temp_file)
            shutil.move(temp_file, '/opt/openmotics/firmware.hex')
        if output:
            temp_file = self._download_firmware('output', output)
            self._gateway_api.update_slave_firmware('O', temp_file)
            shutil.move(temp_file, '/opt/openmotics/o_firmware.hex')
        if input:
            temp_file = self._download_firmware('input', input)
            self._gateway_api.update_slave_firmware('I', temp_file)
            shutil.move(temp_file, '/opt/openmotics/i_firmware.hex')
        if can:
            temp_file = self._download_firmware('can', can)
            self._gateway_api.update_slave_firmware('C', temp_file)
            shutil.move(temp_file, '/opt/openmotics/c_firmware.hex')
        if dimmer:
            temp_file = self._download_firmware('dimmer', dimmer)
            self._gateway_api.update_slave_firmware('D', temp_file)
            shutil.move(temp_file, '/opt/openmotics/d_firmware.hex')
        if temperature:
            temp_file = self._download_firmware('temperature', temperature)
            self._gateway_api.update_slave_firmware('T', temp_file)
            shutil.move(temp_file, '/opt/openmotics/t_firmware.hex')
        return {}

    @Inject
    def _get_firmware_url(self, firmware, version, firmware_url=INJECTED, gateway_uuid=INJECTED):
        # type: (str, str, str, str) -> str
        uri = urlparse(firmware_url)
        path = '{0}/{1}/{2}/'.format(uri.path, firmware, version)
        query = 'uuid={0}'.format(gateway_uuid)
        return urlunparse((uri.scheme, uri.netloc, path, '', query, ''))

    def _download_firmware(self, firmware, version):
        # type: (str, str) -> str
        url = self._get_firmware_url(firmware, version)
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError('failed to retrieve firmware from {}, response {}'.format(url, response.status_code))
        data = response.json()
        temp_file = tempfile.mktemp('-firmware.hex')
        logger.info('downloading {}...'.format(data['url']))
        response = requests.get(data['url'], stream=True)
        with open(temp_file, 'wb') as f:
            shutil.copyfileobj(response.raw, f)

        hasher = hashlib.sha256()
        with open(temp_file, 'rb') as f:
            hasher.update(f.read())
        calculated_hash = hasher.hexdigest()
        if calculated_hash != data['sha256']:
            raise ValueError('firmware sha256:%s does not match' % calculated_hash)
        return temp_file

    @openmotics_api(auth=True, plugin_exposed=False)
    def update_master_firmware(self, md5, firmware_data):
        """
        Perform a master firmware update.
        """
        firmware_data = firmware_data.file.read()
        hasher = hashlib.md5()
        hasher.update(firmware_data)
        calculated_md5 = hasher.hexdigest()
        if md5 != calculated_md5:
            raise ValueError('firmware md5:%s does not match' % calculated_md5)

        temp_file = '/tmp/{}.hex'.format(md5)
        with open(temp_file, 'wb') as firmware_file:
            firmware_file.write(firmware_data)
        self._gateway_api.update_master_firmware(temp_file)
        shutil.move(temp_file, '/opt/openmotics/firmware.hex')
        return {}

    @openmotics_api(auth=True, plugin_exposed=False)
    def update_slave_firmware(self, type, md5, firmware_data):
        """
        Perform a slave firmware update.
        """
        if type not in ('C', 'O', 'I', 'D', 'E', 'T'):
            raise ValueError('invalid slave module type %s' % type)

        firmware_data = firmware_data.file.read()
        hasher = hashlib.md5()
        hasher.update(firmware_data)
        calculated_md5 = hasher.hexdigest()
        if md5 != calculated_md5:
            raise ValueError('firmware md5:%s does not match' % calculated_md5)

        temp_file = '/tmp/{}.hex'.format(md5)
        with open(temp_file, 'wb') as firmware_file:
            firmware_file.write(firmware_data)
        self._gateway_api.update_slave_firmware(type, temp_file)
        shutil.move(temp_file, '/opt/openmotics/{}_firmware.hex'.format(type))
        return {}

    @openmotics_api(auth=True)
    def set_timezone(self, timezone):
        """
        Set the timezone for the gateway.

        :param timezone: in format 'Continent/City'.
        :type timezone: str
        """
        self._gateway_api.set_timezone(timezone)
        self._gateway_api.sync_master_time()
        return {}

    @openmotics_api(auth=True)
    def get_timezone(self):
        """
        Get the timezone for the gateway.

        :returns: 'timezone': the timezone in 'Continent/City' format (String).
        :rtype: dict
        """
        return {'timezone': self._gateway_api.get_timezone()}

    @openmotics_api(auth=True, check=types(headers='json', auth='json', timeout=int), plugin_exposed=False)
    def do_url_action(self, url, method='GET', headers=None, data=None, auth=None, timeout=10):
        """
        Execute an url action.

        :param url: The url to fetch.
        :type url: str
        :param method: (optional) The http method (defaults to GET).
        :type method: str | None
        :param headers: (optional) The http headers to send (format: json encoded dict)
        :type headers: str | None
        :param data: (optional) Bytes to send in the body of the request.
        :type data: str | None
        :param auth: (optional) Json encoded tuple (username, password).
        :type auth: str | None
        :param timeout: (optional) Timeout in seconds for the http request (default = 10 sec).
        :type timeout: int | None
        :returns: 'headers': response headers, 'data': response body.
        :rtype: dict
        """
        response = requests.request(method, url,
                                    headers=headers,
                                    data=data,
                                    auth=auth,
                                    timeout=timeout)

        if response.status_code != requests.codes.ok:
            raise RuntimeError("Got bad resonse code: %d" % response.status_code)
        response_headers = response.headers  # type: Any
        return {'headers': response_headers._store,
                'data': response.text}

    @openmotics_api(auth=True, check=types(timestamp=int, action='json'), deprecated='add_schedule')
    def schedule_action(self, timestamp, action):
        self.add_schedule(name=action['description'],
                          start=timestamp,
                          schedule_type='LOCAL_API',
                          arguments={'name': action['action'],
                                     'parameters': action['params']})
        return {}

    @openmotics_api(auth=True, check=types(name=str, start=int, schedule_type=str, arguments='json', repeat='json', duration=int, end=int))
    def add_schedule(self, name, start, schedule_type, arguments=None, repeat=None, duration=None, end=None):
        schedule_dto = ScheduleDTO(id=None,
                                   name=name,
                                   start=start,
                                   action=schedule_type,
                                   repeat=repeat,
                                   duration=duration,
                                   end=end,
                                   arguments=arguments)
        self._scheduling_controller.save_schedules([schedule_dto])
        return {}

    @openmotics_api(auth=True, deprecated='list_schedules')
    def list_scheduled_actions(self):
        # Deprecated API, so manual serialization to old format
        return {'actions': [{'timestamp': schedule.start,
                             'from_now': schedule.start - time.time(),
                             'id': schedule.id,
                             'description': schedule.name,
                             'action': json.dumps({'action': schedule.arguments['name'],
                                                   'params': schedule.arguments['parameters']})}
                            for schedule in self._scheduling_controller.load_schedules()
                            if schedule.action == 'LOCAL_API']}

    @openmotics_api(auth=True)
    def list_schedules(self):
        return {'schedules': [ScheduleSerializer.serialize(schedule_dto, fields=None)
                              for schedule_dto in self._scheduling_controller.load_schedules()]}

    @openmotics_api(auth=True, check=types(id=int), deprecated='remove_schedule')
    def remove_scheduled_action(self, id):
        self.remove_schedule(schedule_id=id)
        return {}

    @openmotics_api(auth=True, check=types(schedule_id=int))
    def remove_schedule(self, schedule_id):
        self._scheduling_controller.remove_schedules([ScheduleDTO(id=schedule_id,  # Only ID is relevant for delete action
                                                                  name=None, start=None, action=None)])
        return {}

    @openmotics_api(auth=True)
    def get_plugins(self):
        """
        Get the installed plugins.

        :returns: 'plugins': dict with name, version and interfaces where name and version \
            are strings and interfaces is a list of tuples (interface, version) which are both strings.
        :rtype: dict
        """
        plugins = self._plugin_controller.get_plugins()
        ret = [{'name': p.name,
                'version': p.version,
                'interfaces': p.interfaces,
                'status': 'RUNNING' if p.is_running() else 'STOPPED'} for p in plugins]
        return {'plugins': ret}

    @openmotics_api(auth=True, plugin_exposed=False)
    def get_plugin_logs(self):
        """
        Get the logs for all plugins.

        :returns: 'logs': dict with the names of the plugins as keys and the logs (String) as \
            value.
        :rtype: dict
        """
        return {'logs': self._plugin_controller.get_logs()}

    @openmotics_api(auth=True, plugin_exposed=False)
    def install_plugin(self, md5, package_data):
        """
        Install a new plugin. The package_data should include a __init__.py file and
        will be installed in $OPENMOTICS_PREFIX/python/plugins/<name>.

        :param md5: md5 sum of the package_data.
        :type md5: String
        :param package_data: a tgz file containing the content of the plugin package.
        :type package_data: multipart/form-data encoded byte string.
        """
        return {'msg': self._plugin_controller.install_plugin(md5, package_data.file.read())}

    @openmotics_api(auth=True, plugin_exposed=False)
    def remove_plugin(self, name):
        """
        Remove a plugin. This removes the package data and configuration data of the plugin.

        :param name: Name of the plugin to remove.
        :type name: str
        """
        return self._plugin_controller.remove_plugin(name)

    @openmotics_api(auth=True, plugin_exposed=False)
    def stop_plugin(self, name):
        """
        Stops a plugin
        """
        running = self._plugin_controller.stop_plugin(name)
        return {'status': 'RUNNING' if running else 'STOPPED'}

    @openmotics_api(auth=True, plugin_exposed=False)
    def start_plugin(self, name):
        """
        Starts a plugin
        """
        running = self._plugin_controller.start_plugin(name)
        return {'status': 'RUNNING' if running else 'STOPPED'}

    @openmotics_api(auth=True, check=types(settings='json'), plugin_exposed=False)
    def get_settings(self, settings):
        """
        Gets a given setting
        """
        values = {}  # type: Dict[str, Any]
        for setting in settings:
            value = Config.get_entry(setting, None)
            if value is not None:
                values[setting] = value
        return {'values': values}

    @openmotics_api(auth=True, check=types(value='json'), plugin_exposed=False)
    def set_setting(self, setting, value):
        """
        Configures a setting
        """
        if setting not in ['cloud_enabled', 'cloud_metrics_enabled|energy', 'cloud_metrics_enabled|counter',
                           'cloud_support']:
            raise RuntimeError('Setting {0} cannot be set'.format(setting))
        Config.set_entry(setting, value)
        return {}

    @openmotics_api(auth=True, check=types(active=bool), plugin_exposed=False)
    def set_self_recovery(self, active):
        self._gateway_api.set_self_recovery(active=active)
        return {}

    @openmotics_api(auth=True)
    def get_metric_definitions(self, source=None, metric_type=None):
        sources = self._metrics_controller.get_filter('source', source)
        metric_types = self._metrics_controller.get_filter('metric_type', metric_type)
        definitions = {}  # type: Dict[str,Dict[str,Any]]
        for _source, _metric_types in six.iteritems(self._metrics_controller.definitions):
            if _source in sources:
                definitions[_source] = {}
                for _metric_type, definition in six.iteritems(_metric_types):
                    if _metric_type in metric_types:
                        definitions[_source][_metric_type] = definition
        return {'definitions': definitions}

    @openmotics_api(check=types(confirm=bool), auth=True, plugin_exposed=False)
    def factory_reset(self, username, password, confirm=False):
        user_dto = UserDTO(username=username)
        user_dto.set_password(password)
        success, _ = self._user_controller.login(user_dto)
        if not success:
            raise cherrypy.HTTPError(401, 'invalid_credentials')
        if not confirm:
            raise cherrypy.HTTPError(401, 'not_confirmed')
        return self._gateway_api.factory_reset()

    @openmotics_api(auth=False)
    def health_check(self):
        """ Requests the state of the various services and checks the returned value for the global state """
        health = {'openmotics': {'state': self._service_state},
                  'master': {'state': self._gateway_api.get_master_online()}}
        try:
            state = {}
            if self._message_client is not None:
                state = self._message_client.get_state('vpn_service', {})
            health['vpn_service'] = {'state': state.get('last_cycle', 0) > time.time() - 300}
        except Exception as ex:
            logger.error('Error loading vpn_service health: %s', ex)
            health['vpn_service'] = {'state': False}
        return {'health': health,
                'health_version': 1.0}

    @openmotics_api(auth=True)
    def indicate(self):
        """ Blinks the Status led on the Gateway to indicate the module """
        if self._frontpanel_controller:
            self._frontpanel_controller.indicate()
            return {}
        else:
            raise NotImplementedError()

    @cherrypy.expose
    @cherrypy.tools.cors()
    @cherrypy.tools.authenticated(pass_token=True)
    def ws_metrics(self, token, source=None, metric_type=None, interval=None):
        cherrypy.request.ws_handler.metadata = {'token': token,
                                                'client_id': uuid.uuid4().hex,
                                                'source': source,
                                                'metric_type': metric_type,
                                                'interval': None if interval is None else int(interval),
                                                'interface': self}

    @cherrypy.expose
    @cherrypy.tools.cors()
    @cherrypy.tools.authenticated(pass_token=True)
    def ws_events(self, token):
        cherrypy.request.ws_handler.metadata = {'token': token,
                                                'client_id': uuid.uuid4().hex,
                                                'interface': self}

    @cherrypy.expose
    @cherrypy.tools.cors()
    @cherrypy.tools.authenticated(pass_token=True)
    def ws_maintenance(self, token):
        cherrypy.request.ws_handler.metadata = {'token': token,
                                                'client_id': uuid.uuid4().hex,
                                                'interface': self}


@Injectable.named('web_service')
@Singleton
class WebService(object):
    """ The web service serves the gateway api over http. """

    name = 'web'

    @Inject
    def __init__(self, web_interface=INJECTED, http_port=INJECTED, https_port=INJECTED, verbose=False):
        # type: (WebInterface, int, int, bool) -> None
        self._webinterface = web_interface
        self._http_port = http_port
        self._https_port = https_port
        self._http_server = None  # type: Optional[cherrypy._cpserver.Server]
        self._https_server = None  # type: Optional[cherrypy._cpserver.Server]
        if not verbose:
            logging.getLogger("cherrypy").propagate = False

    @staticmethod
    def _http_server_logger(msg='', level=20, traceback=False):
        """
        This workaround is to lower some CherryPy "TICK"-SSL errors' severity that are incorrectly
        logged in our version of CherryPy. It is already resolved in a newer version, but we
        still need to upgrade
        """
        # TODO upgrade cherrypy
        _ = level, traceback
        logger.debug(msg)

    def start(self):
        # type: () -> None
        """ Run the web service: start cherrypy. """
        try:
            logger.info('Starting webserver...')
            OMPlugin(cherrypy.engine).subscribe()
            cherrypy.tools.websocket = OMSocketTool()

            cherrypy.config.update({'server.socket_port': self._http_port})

            config = {'/terms': {'tools.staticdir.on': True,
                                 'tools.staticdir.dir': constants.get_terms_dir()},
                      '/static': {'tools.staticdir.on': True,
                                  'tools.staticdir.dir': constants.get_static_dir()},
                      '/ws_metrics': {'tools.websocket.on': True,
                                      'tools.websocket.handler_cls': MetricsSocket},
                      '/ws_events': {'tools.websocket.on': True,
                                     'tools.websocket.handler_cls': EventsSocket},
                      '/ws_maintenance': {'tools.websocket.on': True,
                                          'tools.websocket.handler_cls': MaintenanceSocket},
                      '/': {'tools.cors.on': Config.get_entry('cors_enabled', False),
                            'tools.sessions.on': False}}

            cherrypy.tree.mount(root=self._webinterface,
                                config=config)

            cherrypy.config.update({'engine.autoreload.on': False})
            cherrypy.server.unsubscribe()

            self._https_server = cherrypy._cpserver.Server()
            self._https_server.socket_port = self._https_port
            self._https_server._socket_host = '0.0.0.0'
            self._https_server.socket_timeout = 60
            self._https_server.ssl_certificate = constants.get_ssl_certificate_file()
            self._https_server.ssl_private_key = constants.get_ssl_private_key_file()
            System.setup_cherrypy_ssl(self._https_server)
            self._https_server.subscribe()

            self._http_server = cherrypy._cpserver.Server()
            self._http_server.socket_port = self._http_port
            if Config.get_entry('enable_http', False):
                # This is added for development purposes.
                # Do NOT enable unless you know what you're doing and understand the risks.
                self._http_server._socket_host = '0.0.0.0'
            else:
                self._http_server._socket_host = '127.0.0.1'
            self._http_server.socket_timeout = 60
            self._http_server.subscribe()

            cherrypy.engine.autoreload_on = False

            cherrypy.engine.start()
            self._https_server.httpserver.error_log = WebService._http_server_logger
            self._http_server.httpserver.error_log = WebService._http_server_logger
            logger.info('Starting webserver... Done')
        except Exception:
            logger.exception("Could not start webservice. Dying...")
            sys.exit(1)

    def stop(self):
        # type: () -> None
        """ Stop the web service. """
        logger.info('Stopping webserver...')
        cherrypy.engine.exit()  # Shutdown the cherrypy server: no new requests
        logger.info('Stopping webserver... Done')

    def update_tree(self, mounts):
        try:
            self._http_server.stop()
        except Exception as ex:
            logger.error('Could not stop non-secure webserver: {0}'.format(ex))
        try:
            self._https_server.stop()
        except Exception as ex:
            logger.error('Could not stop secure webserver: {0}'.format(ex))
        try:
            for mount in mounts:
                cherrypy.tree.mount(**mount)
        except Exception as ex:
            logger.error('Could not mount updated tree: {0}'.format(ex))
        try:
            self._http_server.start()
            self._http_server.httpserver.error_log = WebService._http_server_logger
        except Exception as ex:
            logger.error('Could not restart non-secure webserver: {0}'.format(ex))
        try:
            self._https_server.start()
            self._https_server.httpserver.error_log = WebService._http_server_logger
        except Exception as ex:
            logger.error('Could not restart secure webserver: {0}'.format(ex))
