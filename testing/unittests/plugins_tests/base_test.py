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
"""
Tests for plugins.base.
"""

from __future__ import absolute_import

import hashlib
import inspect
import os
import shutil
import tempfile
import time
import ujson as json
import unittest
import logging
from subprocess import call

from mock import Mock
from peewee import SqliteDatabase
from pytest import mark

import plugin_runtime
from gateway.dto import OutputStateDTO
from gateway.enums import ShutterEnums
from gateway.events import GatewayEvent
from gateway.models import Plugin
from gateway.output_controller import OutputController
from gateway.shutter_controller import ShutterController
from ioc import SetTestMode, SetUpTestInjections
from plugin_runtime.base import PluginConfigChecker, PluginException, PluginWebResponse, PluginWebRequest
from logs import Logs

MODELS = [Plugin]


class PluginControllerTest(unittest.TestCase):
    """ Tests for the PluginController. """

    PLUGINS_PATH = None
    PLUGIN_CONFIG_PATH = None
    RUNTIME_PATH = os.path.dirname(plugin_runtime.__file__)

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.PLUGINS_PATH = tempfile.mkdtemp()
        cls.PLUGIN_CONFIG_PATH = tempfile.mkdtemp()
        Logs.setup_logger(log_level=logging.DEBUG)

    def setUp(self):
        self.test_db = SqliteDatabase(':memory:')
        self.test_db.bind(MODELS)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    @classmethod
    def tearDownClass(cls):
        try:
            if cls.PLUGINS_PATH is not None:
                shutil.rmtree(cls.PLUGINS_PATH)
            if cls.PLUGIN_CONFIG_PATH is not None:
                shutil.rmtree(cls.PLUGIN_CONFIG_PATH)
        except Exception:
            pass

    @staticmethod
    def _create_plugin(name, code, base_path=None):
        """ Create a plugin with a given name and the provided code. """
        if base_path is None:
            base_path = PluginControllerTest.PLUGINS_PATH
        path = '{0}/{1}'.format(base_path, name)
        os.makedirs(path)

        with open('{0}/main.py'.format(path), 'w') as code_file:
            code_file.write(code)

        with open('{0}/__init__.py'.format(path), 'w'):
            pass

    @staticmethod
    def _destroy_plugin(name):
        """ Remove the code for a plugin created by _create_plugin. """
        path = '{0}/{1}'.format(PluginControllerTest.PLUGINS_PATH, name)
        if os.path.exists(path):
            shutil.rmtree(path)

    @staticmethod
    def _get_controller(output_controller=None, shutter_controller=None):
        SetUpTestInjections(shutter_controller=shutter_controller,
                            web_interface=None,
                            configuration_controller=None,
                            output_controller=output_controller)
        from plugins.base import PluginController
        PluginController.DEPENDENCIES_TIMER = 0.25
        controller = PluginController(runtime_path=PluginControllerTest.RUNTIME_PATH,
                                      plugins_path=PluginControllerTest.PLUGINS_PATH,
                                      plugin_config_path=PluginControllerTest.PLUGIN_CONFIG_PATH)
        metric_controller = type('MetricController', (), {'get_filter': lambda *args, **kwargs: ['test'],
                                                          'set_plugin_definitions': lambda _self, *args, **kwargs: None})()
        controller.set_metrics_controller(metric_controller)
        return controller

    @staticmethod
    def _create_plugin_package(name, code):
        temp_directory = tempfile.mkdtemp()
        try:
            PluginControllerTest._create_plugin(name, code, temp_directory)
            call('cd {0}/{1}; tar -czf ../package.tgz .'.format(temp_directory, name), shell=True)
            with open('{0}/package.tgz'.format(temp_directory), 'rb') as package_file:
                package_data = package_file.read()
            hasher = hashlib.md5()
            hasher.update(package_data)
            calculated_md5 = hasher.hexdigest()
            return calculated_md5, package_data
        finally:
            shutil.rmtree(temp_directory)

    @mark.slow
    def test_get_one_plugin(self):
        """ Test getting one plugin in the plugins package. """
        controller = None
        try:
            PluginControllerTest._create_plugin('P1', """
from plugins.base import *

class P1(OMPluginBase):
    name = 'P1'
    version = '1.0.0'
    interfaces = []
""")
            controller = PluginControllerTest._get_controller()
            controller.start()
            plugin_list = controller.get_plugins()
            self.assertEqual(1, len(plugin_list))
            self.assertEqual('P1', plugin_list[0].name)
            plugin = Plugin.get(name='P1')
            self.assertEqual('1.0.0', plugin.version)
        finally:
            if controller is not None:
                controller.stop()
            PluginControllerTest._destroy_plugin('P1')

    @mark.slow
    def test_get_two_plugins(self):
        """ Test getting two plugins in the plugins package. """
        controller = None
        try:
            PluginControllerTest._create_plugin('P1', """
from plugins.base import *

class P1(OMPluginBase):
    name = 'P1'
    version = '1.0.0'
    interfaces = []
""")

            PluginControllerTest._create_plugin('P2', """
from plugins.base import *

class P2(OMPluginBase):
    name = 'P2'
    version = '1.0.0'
    interfaces = []
""")

            controller = PluginControllerTest._get_controller()
            controller.start()
            plugin_list = controller.get_plugins()
            self.assertEqual(2, len(plugin_list))
            names = sorted([plugin_list[0].name, plugin_list[1].name])
            self.assertEqual(['P1', 'P2'], names)
        finally:
            if controller is not None:
                controller.stop()
            PluginControllerTest._destroy_plugin('P1')
            PluginControllerTest._destroy_plugin('P2')

    @mark.slow
    def test_dependencies_callback(self):
        """ Test getting one plugin in the plugins package. """
        called = {'called': 0}

        def _call():
            called['called'] += 1

        def _wait_for_called(amount, timeout=1):
            end = time.time() + timeout
            while time.time() < end:
                if called['called'] == amount:
                    break
            self.assertEqual(amount, called['called'])

        controller = None
        try:
            PluginControllerTest._create_plugin('P1', """
from plugins.base import *

class P1(OMPluginBase):
    name = 'P1'
    version = '1.0.0'
    interfaces = []
""")
            controller = PluginControllerTest._get_controller()
            controller._update_dependencies = _call
            controller.start()
            self.assertIsNotNone(controller._dependencies_timer)
            self.assertEquals(0, called['called'])
            _wait_for_called(1)
            controller.stop_plugin('P1')
            _wait_for_called(2)
        finally:
            if controller is not None:
                controller.stop()
            PluginControllerTest._destroy_plugin('P1')

    @mark.slow
    def test_get_special_methods(self):
        """ Test getting special methods on a plugin. """
        controller = None
        try:
            PluginControllerTest._create_plugin('P1', """
import time
from plugins.base import *

class P1(OMPluginBase):
    name = 'P1'
    version = '0.1.0'
    interfaces = [('webui', '1.0')]

    def __init__(self, webservice, logger):
        OMPluginBase.__init__(self, webservice, logger)
        self._bg_running = False
        self._input_data = None
        self._input_data_version_2 = None
        self._output_data = None
        self._output_data_version_2 = None
        self._event_data = None

    @om_expose(auth=True)
    def html_index(self):
        return 'HTML'

    @om_expose(auth=False)
    def get_log(self):
        return {'bg_running': self._bg_running,
                'input_data': self._input_data,
                'input_data_version_2': self._input_data_version_2,
                'output_data': self._output_data,
                'output_data_version_2': self._output_data_version_2,
                'event_data': self._event_data}

    @input_status
    def input(self, input_status_inst):
        self._input_data = input_status_inst
        
    @input_status(version=2)
    def input_version_2(self, input_status_inst):
        self._input_data_version_2 = input_status_inst
        
    @output_status
    def output(self, output_status_inst):
        self._output_data = output_status_inst
        
    @output_status(version=2)
    def output_version_2(self, output_status_inst):
        self._output_data_version_2 = output_status_inst
        
    @receive_events
    def recv_events(self, code):
        self._event_data = code

    @background_task
    def run(self):
        while True:
            self._bg_running = True
            time.sleep(1)
""")

            output_controller = Mock(OutputController)
            output_controller.get_output_statuses = lambda: [OutputStateDTO(id=1, status=True, dimmer=5)]
            controller = PluginControllerTest._get_controller(output_controller=output_controller)
            controller.start()

            kwargs = {'plugin_web_request': PluginWebRequest(method='html_index', version=1).serialize()}
            response = controller._request('P1', 'html_index', kwargs=kwargs)
            response = PluginWebResponse.deserialize(response).body
            self.assertEqual(response, 'HTML')

            rising_input_event = {'id': 1,
                                  'status': True,
                                  'location': {'room_id': 1}}
            controller.process_observer_event(GatewayEvent(event_type=GatewayEvent.Types.INPUT_CHANGE, data=rising_input_event))
            falling_input_event = {'id': 2,
                                   'status': False,
                                   'location': {'room_id': 5}}
            controller.process_observer_event(GatewayEvent(event_type=GatewayEvent.Types.INPUT_CHANGE, data=falling_input_event))
            output_event = {'id': 1,
                            'status': {'on': True,
                                       'value': 5,
                                       'locked': True},
                            'location': {'room_id': 5}}
            controller.process_observer_event(GatewayEvent(event_type=GatewayEvent.Types.OUTPUT_CHANGE, data=output_event))
            controller.process_event(1)

            keys = ['input_data', 'input_data_version_2', 'output_data', 'output_data_version_2', 'event_data']
            start = time.time()
            while time.time() - start < 2:
                kwargs = {'plugin_web_request': PluginWebRequest(method='html_index', version=1).serialize()}
                response = controller._request('P1', 'get_log', kwargs=kwargs)
                response = PluginWebResponse.deserialize(response).body
                if all(response[key] is not None for key in keys):
                    break
                time.sleep(0.1)
            self.assertEqual(response['bg_running'], True)
            self.assertEqual(response['input_data'], [1, None])  # only rising edges should be triggered
            self.assertEqual(response['output_data'],  [[1, 5]])
            self.assertEqual(response['output_data_version_2'], output_event)
            self.assertEqual(response['event_data'], 1)
        finally:
            if controller is not None:
                controller.stop()
            PluginControllerTest._destroy_plugin('P1')

    @mark.slow
    def test_get_unsupported_decorators(self):
        """ Test getting special methods on a plugin. """
        controller = None
        try:
            PluginControllerTest._create_plugin('UnsupportedPlugin', """
import time
from plugins.base import *

class UnsupportedPlugin(OMPluginBase):
    name = 'UnsupportedPlugin'
    version = '0.1.0'
    interfaces = [('webui', '1.0')]
        
    def __init__(self, webservice, logger):
        OMPluginBase.__init__(self, webservice, logger)

    @om_expose(auth=True)
    def html_index(self):
        return 'HTML'

    @input_status(version=3)
    def input_with_unsupported_decorator(self, test_data):
        pass

    @output_status(version=3)
    def output_with_unsupported_decorator(self, test_data):
        pass
""")
            output_controller = Mock(OutputController)
            controller = PluginControllerTest._get_controller(output_controller=output_controller)
            # the plugin will fail to load, but only log this
            controller.start()
            # get the logs and check if we see the output in the logs
            plugin_logs = controller.get_logs()['UnsupportedPlugin']
            matches = ['Decorator', 'version', 'is not supported']
            self.assertTrue(all(match in plugin_logs for match in matches), plugin_logs)
        finally:
            if controller is not None:
                controller.stop()
            PluginControllerTest._destroy_plugin('UnsupportedPlugin')

    @mark.slow
    def test_get_shutter_decorators(self):
        """ Test getting shutter decorators on a plugin. """
        controller = None
        try:
            PluginControllerTest._create_plugin('ShutterPlugin', """
from plugins.base import *

class ShutterPlugin(OMPluginBase):
    name = 'ShutterPlugin'
    version = '0.1.0'
    interfaces = [('webui', '1.0')]
        
    def __init__(self, webservice, logger):
        OMPluginBase.__init__(self, webservice, logger)
        self._shutter_data_v1 = None
        self._shutter_data_v1_detail = None
        self._shutter_data_v2 = None
        self._shutter_data_v3 = None
        
    @om_expose(auth=True)
    def html_index(self):
        return 'HTML'

    @om_expose(auth=False)
    def get_log(self):
        return {'shutter_data_v1': self._shutter_data_v1,
                'shutter_data_v1_detail': self._shutter_data_v1_detail,
                'shutter_data_v2': self._shutter_data_v2,
                'shutter_data_v3': self._shutter_data_v3}
                
    @shutter_status
    def shutter_v1(self, test_data):
        self._shutter_data_v1 = test_data
        
    @shutter_status
    def shutter_v1_detail(self, test_data, detail):
        self._shutter_data_v1_detail = (test_data, detail)
        
    @shutter_status(version=2)
    def shutter_v2(self, test_data, detail):
        self._shutter_data_v2 = (test_data, detail)
        
    @shutter_status(version=3)
    def shutter_v3(self, shutter_event):
        self._shutter_data_v3 = shutter_event
""")
            shutter_controller = Mock(ShutterController)
            shutter_status = [ShutterEnums.State.STOPPED]
            detail_for_shutter = {'1': {'state': ShutterEnums.State.STOPPED,
                                      'actual_position': None,
                                      'desired_position': None,
                                      'last_change': 1596787761.147892}}
            shutter_controller.get_states = lambda: {'status': shutter_status,
                                                     'detail': detail_for_shutter}
            controller = PluginControllerTest._get_controller(shutter_controller=shutter_controller)
            controller.start()

            shutter_event = GatewayEvent(event_type=GatewayEvent.Types.SHUTTER_CHANGE, data={'some_random_key': 'some_random_value'})
            controller.process_observer_event(shutter_event)

            keys = ['shutter_data_v1', 'shutter_data_v1_detail', 'shutter_data_v2', 'shutter_data_v3']
            start = time.time()
            dict_response = None
            while time.time() - start < 2:
                kwargs = {'plugin_web_request': PluginWebRequest(method='get_log', version=1).serialize()}
                response = controller._request('ShutterPlugin', 'get_log', kwargs=kwargs)
                # Expect a plugin web response string
                plugin_response = PluginWebResponse.deserialize(response)
                dict_response = plugin_response.body
                if all(dict_response[key] is not None for key in keys):
                    break
                time.sleep(0.1)
            self.maxDiff = None
            self.assertEqual(dict_response['shutter_data_v1'], shutter_status)
            self.assertEqual(dict_response['shutter_data_v1_detail'], [shutter_status, detail_for_shutter])
            self.assertEqual(dict_response['shutter_data_v2'], [shutter_status, detail_for_shutter])
            self.assertEqual(dict_response['shutter_data_v3'], shutter_event.data)
        finally:
            if controller is not None:
                controller.stop()
            PluginControllerTest._destroy_plugin('ShutterPlugin')

    @mark.slow
    def test_update_plugin(self):
        """ Validates whether a plugin can be updated """
        test_1_md5, test_1_data = PluginControllerTest._create_plugin_package('Test', """
from plugins.base import *

class Test(OMPluginBase):
    name = 'Test'
    version = '0.0.1'
    interfaces = []
""")
        test_2_md5, test_2_data = PluginControllerTest._create_plugin_package('Test', """
from plugins.base import *

class Test(OMPluginBase):
    name = 'Test'
    version = '0.0.2'
    interfaces = []
""")

        controller = PluginControllerTest._get_controller()
        controller.start()

        # Install first version
        result = controller.install_plugin(test_1_md5, test_1_data)
        self.assertEqual(result, 'Plugin successfully installed')
        controller.start_plugin('Test')
        self.assertEqual([r.name for r in controller.get_plugins()], ['Test'])
        plugin = Plugin.get(name='Test')
        self.assertEqual('0.0.1', plugin.version)

        # Update to version 2
        result = controller.install_plugin(test_2_md5, test_2_data)
        self.assertEqual(result, 'Plugin successfully installed')
        self.assertEqual([r.name for r in controller.get_plugins()], ['Test'])
        plugin = Plugin.get(name='Test')
        self.assertEqual('0.0.2', plugin.version)

    @mark.slow
    def test_plugin_metric_reference(self):
        """ Validates whether two plugins won't get the same metric instance """
        controller = None
        try:
            p1_md5, p1_data = PluginControllerTest._create_plugin_package('P1', """
from plugins.base import *

class P1(OMPluginBase):
    name = 'P1'
    version = '0.0.1'
    interfaces = []
    
    def __init__(self, webservice, logger):
        OMPluginBase.__init__(self, webservice, logger)
        self._metric = None
        
    @om_expose(auth=False)
    def get_metric(self):
        return {'metric': self._metric}
        
    @om_metric_receive()
    def set_metric(self, metric):
        self._metric = metric
        self._metric['foo'] = 'P1'
""")
            p2_md5, p2_data = PluginControllerTest._create_plugin_package('P2', """
from plugins.base import *

class P2(OMPluginBase):
    name = 'P2'
    version = '0.0.1'
    interfaces = []
    
    def __init__(self, webservice, logger):
        OMPluginBase.__init__(self, webservice, logger)
        self._metric = None
        
    @om_expose(auth=False)
    def get_metric(self):
        return {'metric': self._metric}
        
    @om_metric_receive()
    def set_metric(self, metric):
        self._metric = metric
        self._metric['foo'] = 'P2'
""")

            controller = PluginControllerTest._get_controller()
            controller.start()

            controller.install_plugin(p1_md5, p1_data)
            controller.start_plugin('P1')
            controller.install_plugin(p2_md5, p2_data)
            controller.start_plugin('P2')

            delivery_rate = controller.distribute_metrics([{'timestamp': 0,
                                                            'source': 'test',
                                                            'type': 'test',
                                                            'tags': {},
                                                            'values': {}}])
            self.assertEqual({'total': 2,
                              'test.test': 2}, delivery_rate)

            start = time.time()
            p1_metric = {'metric': None}
            p2_metric = {'metric': None}
            while time.time() - start < 2:
                kwargs = {'plugin_web_request': PluginWebRequest(version=1).serialize()}
                p1_metric = controller._request('P1', 'get_metric', kwargs=kwargs)
                p1_metric = PluginWebResponse.deserialize(p1_metric).body
                p2_metric = controller._request('P2', 'get_metric', kwargs=kwargs)
                p2_metric = PluginWebResponse.deserialize(p2_metric).body
                if p1_metric['metric'] is not None and p2_metric['metric'] is not None:
                    break
                time.sleep(0.1)

            self.assertIsNotNone(p1_metric['metric'])
            self.assertEqual('P1', p1_metric['metric'].get('foo'))
            self.assertIsNotNone(p2_metric['metric'])
            self.assertEqual('P2', p2_metric['metric'].get('foo'))
            # Compare the addresses to make sure it's a different instance
            self.assertNotEqual(id(p1_metric['metric']), id(p2_metric['metric']))

        finally:
            if controller is not None:
                controller.stop()
            PluginControllerTest._destroy_plugin('P1')
            PluginControllerTest._destroy_plugin('P2')

    def test_check_plugin(self):
        """ Test the exception that can occur when checking a plugin. """
        from plugin_runtime.utils import check_plugin
        from plugin_runtime.base import OMPluginBase

        PluginControllerTest._get_controller()

        class P1(OMPluginBase):
            """ Plugin without name. """
            pass

        try:
            check_plugin(P1)
        except PluginException as exception:
            self.assertEqual('Attribute \'name\' is missing from the plugin class', str(exception))

        class P2(OMPluginBase):
            """ Plugin with malformed name. """
            name = 'malformed name'

        try:
            check_plugin(P2)
        except PluginException as exception:
            self.assertEqual('Plugin name \'malformed name\' is malformed: can only contain letters, numbers and underscores.', str(exception))

        class P3(OMPluginBase):
            """ Plugin without version. """
            name = 'test_name123'

        try:
            check_plugin(P3)
        except PluginException as exception:
            self.assertEqual('Attribute \'version\' is missing from the plugin class', str(exception))

        class P4(OMPluginBase):
            """ Plugin without interfaces. """
            name = 'test'
            version = '1.0.0'

        try:
            check_plugin(P4)
        except PluginException as exception:
            self.assertEqual('Attribute \'interfaces\' is missing from the plugin class', str(exception))

        class P5(OMPluginBase):
            """ Valid plugin. """
            name = 'test'
            version = '1.0.0'
            interfaces = []

        check_plugin(P5)

        class P6(OMPluginBase):
            """ Plugin that violates the webui interface. """
            name = 'test'
            version = '1.0.0'
            interfaces = [('webui', '1.0')]

        try:
            check_plugin(P6)
        except PluginException as exception:
            self.assertEqual('Plugin \'test\' has no method named \'html_index\'', str(exception))

    @mark.slow
    def test_om_expose_decorator(self):
        """ Test the om_expose decorator. """
        controller = None
        try:
            PluginControllerTest._create_plugin('P1', """
import inspect
import time
from plugins.base import *

class P1(OMPluginBase):
    name = 'P1'
    version = '0.1.0'
    interfaces = []

    def __init__(self, webservice, logger):
        OMPluginBase.__init__(self, webservice, logger)
        self.logger = logger
        self.dummy_var = 37

    def print_func_name(self):
        self.logger('Calling func: {}'.format(inspect.stack()[1][3]))

    # om_expose function naming convention:
    # vX : version 1 or 2
    # auth or nonauth
    # return type
    @om_expose(auth=True)
    def v1_auth_string(self):
        self.print_func_name()
        return 'string'

    @om_expose(auth=False)
    def v1_nonauth_dict(self):
        self.print_func_name()
        return {'dummy_var': self.dummy_var}
        
    @om_expose
    def v1_default_bytes(self):
        self.print_func_name()
        return b'someBytesString'
        
    @om_expose
    def v1_default_param(self, param):
        self.print_func_name()
        self.logger('Received param: {} of type: {}'.format(param, type(param)))
        return param
        
    @om_expose(version=2)
    def v2_default_string(self):
        self.print_func_name()
        return 'someString'
        
    @om_expose(version=2)
    def v2_default_param(self, param):
        self.print_func_name()
        self.logger('Received param: {} of type: {}'.format(param, type(param)))
        return param
        
    @om_expose(version=2)
    def v2_default_param_web_request(self, param, plugin_web_request):
        self.print_func_name()
        self.logger('Received param: {} of type: {}'.format(param, type(param)))
        self.logger('Received PluginWebRequest: {}'.format(plugin_web_request))
        return param
        
    @om_expose(version=2)
    def v2_default_dict(self, plugin_web_request):
        self.print_func_name()
        self.logger('Received PluginWebRequest: {}'.format(plugin_web_request))
        return {'response-data': 'response...'} 
        
    @om_expose(version=2)
    def v2_default_param_web_request_web_response(self, param, plugin_web_request):
        self.print_func_name()
        self.logger('Received param: {} of type: {}'.format(param, type(param)))
        self.logger('Received PluginWebRequest: {}'.format(plugin_web_request))
        response =PluginWebResponse(
            status_code=201,
            headers={'some-header': 'some-header-value'},
            body=param,
            path='somePath'
        )
        return response

    @om_expose
    def v1_body(self, request_body):
        self.print_func_name()
        self.logger('Received body: {}'.format(request_body))
        return request_body

    @om_expose(version=2)
    def v2_body(self, request_body):
        self.print_func_name()
        self.logger('Received body: {}'.format(request_body))
        return request_body
""")

            controller = PluginControllerTest._get_controller()
            controller.start()

            def do_request(func, plugin='P1', web_request=None, get_web_response=False, self=self):
                if web_request is None:
                    request = PluginWebRequest(version=1).serialize()
                    version = 1
                else:
                    request = web_request.serialize()
                    version = web_request.version

                kwargs = {'plugin_web_request': request}
                resp = controller._request(plugin, func, kwargs=kwargs)
                if not get_web_response:
                    plugin_response = PluginWebResponse.deserialize(resp)
                    resp = plugin_response.body
                    self.assertEqual(plugin_response.version, version)
                else:
                    resp = PluginWebResponse.deserialize(resp)
                return resp

            response = do_request('v1_auth_string')
            self.assertEqual(response, 'string')

            response = do_request('v1_nonauth_dict')
            self.assertEqual(response, {'dummy_var': 37})

            response = do_request('v1_default_bytes')
            self.assertEqual(response, b'someBytesString')

            response = do_request('v1_default_param',
                                  web_request=PluginWebRequest(version=1, params={'param': 'some-param'}))
            self.assertEqual(response, 'some-param')

            response = do_request('v1_default_param',
                                  web_request=PluginWebRequest(version=1, params={'param': {'test': 'test'}}))
            self.assertEqual(response, {'test': 'test'})

            try:
                response = do_request('v1_default_param',
                                      web_request=PluginWebRequest(version=1, params={}))
                self.fail('There should be a missing parameter')
            except Exception as ex:
                pass

            response = do_request('v2_default_string')
            self.assertEqual(response, 'someString')

            response = do_request('v2_default_param',
                                  web_request=PluginWebRequest(version=2, params={'param': 'some-param'}))
            self.assertEqual(response, 'some-param')

            response = do_request('v2_default_param',
                                  web_request=PluginWebRequest(version=2, params={'param': {'test': 'test'}}))
            self.assertEqual(response, {'test': 'test'})

            response = do_request('v2_default_param_web_request',
                                  web_request=PluginWebRequest(version=2, params={'param': {'test': 'test'}}))
            self.assertEqual(response, {'test': 'test'})

            response = do_request('v2_default_dict',
                                  web_request=PluginWebRequest(version=2, params={}),
                                  get_web_response=True)
            self.assertEqual(response.body, {'response-data': 'response...'})
            self.assertEqual(response.version, 2)
            self.assertEqual(response.status_code, 200)

            response = do_request('v2_default_param_web_request',
                                  web_request=PluginWebRequest(version=2, params={'param': {'test': 'test'}}),
                                  get_web_response=True)
            self.assertEqual(response.body, {'test': 'test'})
            self.assertEqual(response.version, 2)
            self.assertEqual(response.status_code, 200)

            response = do_request('v2_default_param_web_request_web_response',
                                  web_request=PluginWebRequest(version=2, params={'param': {'test': 'test'}}),
                                  get_web_response=True)
            self.assertEqual(response.body, {'test': 'test'})
            self.assertEqual(response.version, 2)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.headers, {'some-header': 'some-header-value'})

            response = do_request('v2_default_param_web_request_web_response',
                                  web_request=PluginWebRequest(version=2, params={'param': 'someString'}),
                                  get_web_response=True)
            self.assertEqual(response.body, 'someString')
            self.assertEqual(response.version, 2)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.headers, {'some-header': 'some-header-value'})

            response = do_request('v2_default_param_web_request_web_response',
                                  web_request=PluginWebRequest(version=2, params={'param': 'someString', 'param2': 'test'}),
                                  get_web_response=True)
            self.assertEqual(response.body, 'someString')
            self.assertEqual(response.version, 2)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.headers, {'some-header': 'some-header-value'})

            for special_string in [
                'someString/someOtherText!@#$%^&*()<>{}[]',
                'basic_string',
                u'test_unicode'
            ]:
                response = do_request('v2_default_param_web_request_web_response',
                                      web_request=PluginWebRequest(version=2, params={'param': special_string, 'param2': 'test'}),
                                      get_web_response=True)
                self.assertEqual(response.body, special_string)
                self.assertEqual(response.version, 2)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.headers, {'some-header': 'some-header-value'})

            try:
                response = do_request('v2_default_param_web_request_web_response',
                                      web_request=PluginWebRequest(version=2, params={}),
                                      get_web_response=True)
                self.fail('Request should not succeed due to parameter not filled in')
            except Exception:
                pass

            response = do_request('v1_body',
                                  web_request=PluginWebRequest(version=1, body='somebody'),
                                  get_web_response=True)
            self.assertEqual(response.body, 'somebody')
            self.assertEqual(response.version, 1)
            self.assertEqual(response.status_code, 200)

            response = do_request('v2_body',
                                  web_request=PluginWebRequest(version=2, body='somebody'),
                                  get_web_response=True)
            self.assertEqual(response.body, 'somebody')
            self.assertEqual(response.version, 2)
            self.assertEqual(response.status_code, 200)


        finally:
            if controller is not None:
                controller.stop()
            PluginControllerTest._destroy_plugin('P1')


FULL_DESCR = [
    {'name': 'hostname', 'type': 'str', 'description': 'The hostname of the server.'},
    {'name': 'port', 'type': 'int', 'description': 'Port on the server.'},
    {'name': 'use_auth', 'type': 'bool', 'description': 'Use authentication while connecting.'},
    {'name': 'password', 'type': 'password', 'description': 'Your secret password.'},
    {'name': 'enumtest', 'type': 'enum', 'description': 'Test for enum',
     'choices': ['First', 'Second']},
    {'name': 'outputs', 'type': 'section', 'repeat': True, 'min': 1,
     'content': [{'name': 'output', 'type': 'int'}]},
    {'name': 'network', 'type': 'nested_enum',
     'choices': [{'value': 'Facebook', 'content': [{'name': 'likes', 'type': 'int'}]},
                 {'value': 'Twitter', 'content': [{'name': 'followers', 'type': 'int'}]}]}
]


class PluginConfigCheckerTest(unittest.TestCase):
    """ Tests for the PluginConfigChecker. """

    maxDiff = None

    def test_constructor(self):
        """ Test for the constructor. """
        _ = self
        PluginConfigChecker(FULL_DESCR)

    def test_constructor_error(self):
        """ Test with an invalid data type """
        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker({'test': 123})
        self.assertTrue('list' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'test': 123}])
        self.assertTrue('name' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 123}])
        self.assertTrue('name' in str(ctx.exception) and 'string' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'test'}])
        self.assertTrue('type' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'test', 'type': 123}])
        self.assertTrue('type' in str(ctx.exception) and 'string' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'test', 'type': 'something_else'}])
        self.assertTrue('type' in str(ctx.exception) and 'something_else' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'test', 'type': 'str', 'description': []}])
        self.assertTrue('description' in str(ctx.exception) and 'string' in str(ctx.exception))

    def test_constructor_str(self):
        """ Test for the constructor for str. """
        PluginConfigChecker([{'name': 'hostname', 'type': 'str', 'description': 'The hostname of the server.'}])
        PluginConfigChecker([{'name': 'hostname', 'type': 'str'}])

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'type': 'str'}])
        self.assertTrue('name' in str(ctx.exception))

    def test_constructor_int(self):
        """ Test for the constructor for int. """
        PluginConfigChecker([{'name': 'port', 'type': 'int', 'description': 'Port on the server.'}])
        PluginConfigChecker([{'name': 'port', 'type': 'int'}])

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'type': 'int'}])
        self.assertTrue('name' in str(ctx.exception))

    def test_constructor_bool(self):
        """ Test for the constructor for bool. """
        PluginConfigChecker([{'name': 'use_auth', 'type': 'bool', 'description': 'Use authentication while connecting.'}])
        PluginConfigChecker([{'name': 'use_auth', 'type': 'bool'}])

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'type': 'bool'}])
        self.assertTrue('name' in str(ctx.exception))

    def test_constructor_password(self):
        """ Test for the constructor for bool. """
        PluginConfigChecker([{'name': 'password', 'type': 'password', 'description': 'A password.'}])
        PluginConfigChecker([{'name': 'password', 'type': 'password'}])

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'type': 'password'}])
        self.assertTrue('name' in str(ctx.exception))

    def test_constructor_enum(self):
        """ Test for the constructor for enum. """
        PluginConfigChecker([{'name': 'enumtest', 'type': 'enum', 'description': 'Test for enum', 'choices': ['First', 'Second']}])
        PluginConfigChecker([{'name': 'enumtest', 'type': 'enum', 'choices': ['First', 'Second']}])

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'enumtest', 'type': 'enum', 'choices': 'First'}])
        self.assertTrue('choices' in str(ctx.exception) and 'list' in str(ctx.exception))

    def test_constructor_section(self):
        """ Test for the constructor for section. """
        PluginConfigChecker([{'name': 'outputs', 'type': 'section', 'repeat': True, 'min': 1, 'content': [{'name': 'output', 'type': 'int'}]}])
        PluginConfigChecker([{'name': 'outputs', 'type': 'section', 'repeat': False, 'content': [{'name': 'output', 'type': 'int'}]}])
        PluginConfigChecker([{'name': 'outputs', 'type': 'section', 'content': [{'name': 'output', 'type': 'int'}]}])

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'outputs', 'type': 'section', 'repeat': 'hello', 'content': [{'name': 'output', 'type': 'int'}]}])
        self.assertTrue('repeat' in str(ctx.exception) and 'bool' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'outputs', 'type': 'section', 'min': 1, 'content': [{'name': 'output', 'type': 'int'}]}])
        self.assertTrue('min' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'outputs', 'type': 'section', 'content': 'error'}])
        self.assertTrue('content' in str(ctx.exception) and 'list' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'outputs', 'type': 'section', 'content': [{'name': 123}]}])
        self.assertTrue('content' in str(ctx.exception) and 'name' in str(ctx.exception) and 'string' in str(ctx.exception))

    def test_constructor_nested_enum(self):
        """ Test for constructor for nested enum. """
        PluginConfigChecker([{'name': 'network', 'type': 'nested_enum', 'choices': [
            {'value': 'Facebook', 'content': [{'name': 'likes', 'type': 'int'}]},
            {'value': 'Twitter', 'content': [{'name': 'followers', 'type': 'int'}]}
        ]}])

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'network', 'type': 'nested_enum', 'choices': 'test'}])
        self.assertTrue('choices' in str(ctx.exception) and 'list' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'network', 'type': 'nested_enum', 'choices': ['test']}])
        self.assertTrue('choices' in str(ctx.exception) and 'dict' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'network', 'type': 'nested_enum', 'choices': [{}]}])
        self.assertTrue('choices' in str(ctx.exception) and 'value' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'network', 'type': 'nested_enum', 'choices': [{'value': 123}]}])
        self.assertTrue('choices' in str(ctx.exception) and 'network' in str(ctx.exception) and 'content' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'network', 'type': 'nested_enum', 'choices': [{'value': 'test'}]}])
        self.assertTrue('choices' in str(ctx.exception) and 'content' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'network', 'type': 'nested_enum', 'choices': [{'value': 'test', 'content': 'test'}]}])
        self.assertTrue('choices' in str(ctx.exception) and 'content' in str(ctx.exception) and 'list' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            PluginConfigChecker([{'name': 'network', 'type': 'nested_enum', 'choices': [{'value': 'test', 'content': [{}]}]}])
        self.assertTrue('choices' in str(ctx.exception) and 'content' in str(ctx.exception) and 'name' in str(ctx.exception))

    def test_check_config_error(self):
        """ Test check_config with an invalid data type """
        checker = PluginConfigChecker([{'name': 'hostname', 'type': 'str'}])

        with self.assertRaises(PluginException) as ctx:
            checker.check_config('string')
        self.assertTrue('dict' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({})
        self.assertTrue('hostname' in str(ctx.exception))

    def test_check_config_str(self):
        """ Test check_config for str. """
        checker = PluginConfigChecker([{'name': 'hostname', 'type': 'str'}])
        checker.check_config({'hostname': 'cloud.openmotics.com'})

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'hostname': 123})
        self.assertTrue('str' in str(ctx.exception))

    def test_check_config_int(self):
        """ Test check_config for int. """
        checker = PluginConfigChecker([{'name': 'port', 'type': 'int'}])
        checker.check_config({'port': 123})

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'port': "123"})
        self.assertTrue('int' in str(ctx.exception))

    def test_check_config_bool(self):
        """ Test check_config for bool. """
        checker = PluginConfigChecker([{'name': 'use_auth', 'type': 'bool'}])
        checker.check_config({'use_auth': True})

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'use_auth': 234543})
        self.assertTrue('bool' in str(ctx.exception))

    def test_check_config_password(self):
        """ Test check_config for bool. """
        checker = PluginConfigChecker([{'name': 'password', 'type': 'password'}])
        checker.check_config({'password': 'test'})

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'password': 123})
        self.assertTrue('str' in str(ctx.exception))

    def test_check_config_section(self):
        """ Test check_config for section. """
        checker = PluginConfigChecker([{'name': 'outputs', 'type': 'section', 'repeat': True, 'min': 1, 'content': [{'name': 'output', 'type': 'int'}]}])

        checker.check_config({'outputs': []})
        checker.check_config({'outputs': [{'output': 2}]})
        checker.check_config({'outputs': [{'output': 2}, {'output': 4}]})

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'outputs': 'test'})
        self.assertTrue('list' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'outputs': [{'test': 123}]})
        self.assertTrue('section' in str(ctx.exception) and 'output' in str(ctx.exception))

    def test_check_config_nested_enum(self):
        """ Test check_config for nested_enum. """
        checker = PluginConfigChecker([{'name': 'network', 'type': 'nested_enum', 'choices': [
            {'value': 'Facebook', 'content': [{'name': 'likes', 'type': 'int'}]},
            {'value': 'Twitter', 'content': [{'name': 'followers', 'type': 'int'}]}
        ]}])

        checker.check_config({'network': ['Twitter', {'followers': 3}]})
        checker.check_config({'network': ['Facebook', {'likes': 3}]})

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'network': 'test'})
        self.assertTrue('list' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'network': []})
        self.assertTrue('list' in str(ctx.exception) and '2' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'network': ['something else', {}]})
        self.assertTrue('choices' in str(ctx.exception))

        with self.assertRaises(PluginException) as ctx:
            checker.check_config({'network': ['Twitter', {}]})
        self.assertTrue('nested_enum dict' in str(ctx.exception) and 'followers' in str(ctx.exception))

    def test_simple(self):
        """ Test a simple valid configuration. """
        _ = self
        checker = PluginConfigChecker([
            {'name': 'log_inputs', 'type': 'bool', 'description': 'Log the input data.'},
            {'name': 'log_outputs', 'type': 'bool', 'description': 'Log the output data.'}
        ])
        checker.check_config({'log_inputs': True, 'log_outputs': False})

    def test_load_webinterface(self):
        """ Tests whether the webinterface.py parsing works as expected """
        from plugin_runtime import web
        from gateway.webservice import WebInterface
        found_calls = web._load_webinterface()

        ramaining_methods = list(found_calls.keys())
        for method_info in inspect.getmembers(WebInterface, predicate=lambda m: inspect.isfunction(m) or inspect.ismethod(m)):
            method = method_info[1]
            method_name = method.__name__
            call_info = found_calls.get(method_name)
            if not hasattr(method, 'plugin_exposed'):
                # Not an @openmotics_api call
                self.assertIsNone(call_info, 'An unexpected call was exposed to the plugins: {0}'.format(method_name))
                continue
            if method.plugin_exposed is False or method.deprecated is True:
                self.assertIsNone(call_info, 'An unexpected call was exposed to the plugins: {0}'.format(method_name))
                continue
            self.assertIsNotNone(call_info, 'Expected call was not exposed to plugins: {0}'.format(method_name))
            arg_spec = inspect.getargspec(method)
            self.assertEqual(arg_spec.args[0], 'self')
            self.assertEqual(arg_spec.args[1:], call_info)
            ramaining_methods.remove(method_name)
        self.assertEqual(ramaining_methods, [])

    def test_plugin_web_request_serialize(self):
        """ Test the functionality fo the plugin web request serialize"""
        pwr = PluginWebRequest(
            method='POST',
            body=json.dumps({"test": "value"}),
            headers={"Some-Header": "Some-Header-Value"},
            path='/api/test/endpoint'
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebRequest.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        # with a dict as body
        pwr = PluginWebRequest(
            method='POST',
            body={"test": "value"},
            headers={"Some-Header": "Some-Header-Value"},
            path='/api/test/endpoint'
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebRequest.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        # with a dict as body with non string values
        pwr = PluginWebRequest(
            method='POST',
            body={"test": 236, 'other': 'test', 'last': 'test'},
            headers={"Some-Header": "Some-Header-Value"},
            path='/api/test/endpoint'
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebRequest.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        # with a empty body
        pwr = PluginWebRequest(
            method='POST',
            body=None,
            headers={"Some-Header": "Some-Header-Value"},
            path='/api/test/endpoint'
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebRequest.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        # Complete empty web request
        pwr = PluginWebRequest(
            method=None,
            body=None,
            headers=None,
            path=None
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebRequest.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        # Bytestring test
        pwr = PluginWebRequest(
            method=None,
            body=b'sometest',
            headers=None,
            path=None
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebRequest.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        # Bytestring test
        pwr = PluginWebRequest(
            method=None,
            body=object(),
            headers=None,
            path=None
        )
        try:
            pwr_serial = pwr.serialize()
            self.fail('It should not be possible to serialize web request with object as body')
        except AttributeError as ex:
            pass
        except Exception as ex:
            self.fail('Wrong exception raised: {}'.format(ex))

        # special characters test
        pwr = PluginWebRequest(
            method=None,
            body='sometest/someothertext!@#$%^&*()',
            headers=None,
            path=None
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebRequest.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

    def test_plugin_web_response_serialize(self):
        """ Test the functionality fo the plugin web response serialize"""
        pwr = PluginWebResponse(
            body=json.dumps({"test": "value"}),
            headers={"Some-Header": "Some-Header-Value"},
            status_code=200,
            path='somepath'
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebResponse.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        pwr = PluginWebResponse(
            body={"test": "value"},
            headers={"Some-Header": "Some-Header-Value"},
            status_code=200,
            path='somepath'
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebResponse.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        pwr = PluginWebResponse(
            body=b'testString',
            headers={"Some-Header": "Some-Header-Value"},
            status_code=200,
            path='somepath'
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebResponse.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        pwr = PluginWebResponse(
            body='testString/someothertext!@#$%^&*()<>',
            headers={"Some-Header": "Some-Header-Value"},
            status_code=200,
            path='somepath'
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebResponse.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        pwr = PluginWebResponse(
            body={'test': 'testString/someothertext!@#$%^&*()<>'},
            headers={"Some-Header": "Some-Header-Value"},
            status_code=200,
            path='somepath'
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebResponse.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)

        pwr = PluginWebResponse(
            body=None,
            headers=None,
            status_code=None,
            path=None
        )
        pwr_serial = pwr.serialize()
        self.assertTrue(isinstance(pwr_serial, str))
        pwr_deserialized = PluginWebResponse.deserialize(pwr_serial)
        self.assertEqual(pwr, pwr_deserialized)
