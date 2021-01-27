import os
import time
import logging
from threading import Thread
import ujson as json
from collections import deque

from plugins.base import om_expose, om_metric_data, OMPluginBase, PluginConfigChecker, background_task, PluginWebRequest, PluginWebResponse

if False:  # MyPy
    from typing import Optional, Dict, Any


class EsafeConnect(OMPluginBase):

    name = 'eSafeConnect'
    version = '0.0.1'
    interfaces = [('config', '1.0'), ('metrics', '1.0')]

    config_descr = [
        {
            'name': 'esafe_ip',
            'type': 'str',
            'description': 'the eSafe ip address to connect to (default localhost)'
        },
        {
            'name': 'esafe_port',
            'type': 'int',
            'description': 'The port of the eSafe api'
        }
    ]
    default_config = {'esafe_ip': 'localhost', 'esafe_port': 80}


    def __init__(self, webinterface, logger):
        super(EsafeConnect, self).__init__(webinterface, logger)

        self.__config = self.read_config(EsafeConnect.default_config)
        self.__config_checker = PluginConfigChecker(EsafeConnect.config_descr)

        self.logger("Started eSafe Connect plugin")


    @om_expose(version=2)
    def api2(self, PluginWebRequest):
        # Type: (PluginWebRequest) -> PluginWebResponse
        self.logger('Version2 request')
        self.logger(PluginWebRequest)
        self.logger('Returning dummy response')
        resp = PluginWebResponse(
            status_code=201,
            body='Received api request successfully on path: {}'.format(PluginWebRequest.path),
            headers={'someHeader': 'SomeHeaderData'},
            path=PluginWebRequest.path
            )
        return resp

    @om_expose
    def api(self, action):
        self.logger("eSafe api is invoked!")
        self.logger('Action: {}'.format(action))
        return 'Done!'


    @om_expose
    def get_config_description(self):
        return json.dumps(EsafeConnect.config_descr)

    @om_expose
    def get_config(self):
        return json.dumps(self.__config)

    @om_expose
    def set_config(self, config):
        config = json.loads(config)
        try:
            self._check_config(config)
        except Exception as ex:
            self.logger("Could not set new config, config check failed: {}".format(ex))
            return json.dumps({'success': False})

        self.__config_checker.check_config(config)
        self.write_config(config)
        self.__config = config
        self.logger("Succesfully saved new config")

        return json.dumps({'success': True})

    @staticmethod
    def _check_config(config):
        # check if all fields are populated
        if 'esafe_ip' not in config:
            raise RuntimeError('Config has no field "esafe_ip" (required)')
        # check if all fields are populated
        if 'esafe_port' not in config:
            raise RuntimeError('Config has no field "esafe" (required)')


        # check all the fields if they are valid input
        if not isinstance(config['esafe_ip'], str):
            raise RuntimeError('field "esafe_ip": ({}) is not a valid input in the provided config (not str)'.format(config['esafe_ip']))
        if not isinstance(config['esafe_port'], int):
            raise RuntimeError('field "esafe_port": ({}) is not a valid input in the provided config (not int)'.format(config['esafe_port']))
