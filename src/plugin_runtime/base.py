from __future__ import absolute_import

import base64
import logging
import os
import sys

import six

import constants
from plugin_runtime.decorators import *  # Import for backwards compatibility

try:
    import ujson as json
except ImportError:
    # This is the case when the plugin runtime is unittested
    import json  # type: ignore

if False:  # MyPy
    from typing import Dict, Optional, Any, Union, AnyStr

logger = logging.getLogger("openmotics")


class PluginException(Exception):
    """ Exception that is raised when there are errors in a plugin implementation. """
    pass


class OMPluginBase(object):
    """
    Base class for an OpenMotics plugin. Every plugin package should contain a
    module with the name 'main' that contains a class that extends this class.
    """

    def __init__(self, webinterface, logger):
        """
        The web interface is provided to the plugin to interface with the OpenMotics system.

        :param webinterface: Reference the OpenMotics webinterface, this can be used to
        perform actions, fetch status data, etc.
        :param logger: Function that can be called with one parameter: message (String),
        the message will be appended to the plugin's log. This log can be fetched using
        the webinterface.
        """
        self.webinterface = webinterface
        self.logger = logger

    def __get_config_path(self):
        """ Get the path for the plugin configuration file based on the plugin name. """
        plugin_config_dir = constants.get_plugin_config_dir()
        config_file = 'pi_{0}.conf'.format(self.__class__.name)
        return os.path.join(plugin_config_dir, config_file)

    def read_config(self, default_config=None):
        """ Read the configuration file for the plugin: the configuration file contains json
        string that will be converted to a python dict, if an error occurs, the default confi
        is returned. The PluginConfigChecker can be used to check if the configuration is valid,
        this has to be done explicitly in the Plugin class.
        """
        config_path = self.__get_config_path()

        if os.path.exists(config_path):
            with open(config_path, 'r') as config_file:
                config = config_file.read()

            try:
                return json.loads(config)
            except Exception as exception:
                logger.error('Exception while getting config for plugin \'{0}\': {1}'.format(self.__class__.name, exception))

        return default_config

    def write_config(self, config):
        """ Write the plugin configuration to the configuration file: the config is a python dict
        that will be serialized to a json string.
        """
        with open(self.__get_config_path(), 'w') as config_file:
            config_file.write(json.dumps(config))


class PluginConfigChecker(object):
    """
    The standard configuration controller for plugins enables the plugin creator to easily
    implement the 'config' plugin interface. By specifying a configuration description, the
    PluginConfigController is able to verify if a configuration dict matches this description.
    The description is a list of dicts, each dict contains the 'name', 'type' and optionally
    'description' and 'i18n' keys.

    These are the basic types: 'str', 'int', 'bool', 'password', these types don't have additional
    keys. For the 'enum' type the user specifies the possible values in a list of strings in the
    'choices' key.

    The complex types 'section' and 'nested_enum' allow the creation of lists and conditional
    elements.

    A 'nested_enum' allows the user to create a subsection of which the content depends on the
    choosen enum value. The 'choices' key should contain a list of dicts with two keys: 'value',
    the value of the enum and 'content', a configuration description like specified here.

    A 'section' allows the user to create a subsection or a list of subsections (when the 'repeat'
    key is present and true, a minimum number of subsections ('min' key) can be provided when
    'repeat' is true. The 'content' key should provide a configuration description like specified
    above.

    An example of a description:
    [
      {'name': 'hostname', 'type': 'str',      'description': 'The hostname of the server.', 'i18n': 'hostname'},
      {'name': 'port',     'type': 'int',      'description': 'Port on the server.',         'i18n': 'port'},
      {'name': 'use_auth', 'type': 'bool',     'description': 'Use authentication while connecting.'},
      {'name': 'password', 'type': 'password', 'description': 'Your secret password.' },
      {'name': 'enumtest', 'type': 'enum',     'description': 'Test for enum',
       'choices': ['First', 'Second']},

      {'name': 'outputs', 'type': 'section', 'repeat': True, 'min': 1,
       'content': [{'name': 'output', 'type': 'int'}]},

      {'name': 'network', 'type': 'nested_enum', 'choices': [
           {'value': 'Facebook', 'content': [{'name': 'likes', 'type': 'int'}]} ,
           {'value': 'Twitter', 'content': [{'name': 'followers', 'type': 'int'}]}
       ]}
    ]
    """

    MISSES_KEY = 'The configuration item \'{0}\' does not contain a \'{1}\' key.'
    KEY_INVALID_TYPE = 'The key \'{0}\' of configuration item \'{1}\' is not {2}.'
    UNKNOWN_TYPE = 'The configuration item \'{0}\' contains unknown type \'{1}\'.'
    CHOICES_INVALID_TYPE = 'An element of the \'choices\' list of configuration item \'{0}\' is not {1}.'
    CONFIG_INVALID_TYPE = 'Config \'{0}\': \'{1}\' is not {2}.'

    def __init__(self, description):
        """
        Creates a PluginConfigChecker using a description. If the description is not valid,
        a PluginException will be thrown.
        """
        self._check_description(description)
        self.__description = description

    def _check_description(self, description):
        """ Checks if a plugin configuration description is valid. """
        if not isinstance(description, list):
            raise PluginException('The configuration description is not a list')
        else:
            for item in description:
                for key, mandatory in [('name', True),
                                       ('type', True),
                                       ('description', False),
                                       ('i18n', False)]:
                    if mandatory is True and key not in item:
                        raise PluginException(PluginConfigChecker.MISSES_KEY.format(item, key))
                    if key in item and not isinstance(item[key], six.string_types):
                        raise PluginException(PluginConfigChecker.KEY_INVALID_TYPE.format(key, item, 'a string'))

                if item['type'] == 'enum':
                    PluginConfigChecker._check_enum(item)
                elif item['type'] == 'section':
                    self._check_section(item)
                elif item['type'] == 'nested_enum':
                    self._check_nested_enum(item)
                elif item['type'] not in ['str', 'int', 'bool', 'password']:
                    raise PluginException(PluginConfigChecker.UNKNOWN_TYPE.format(item, item['type']))

    @staticmethod
    def _check_enum(item):
        """ Check an enum configuration description. """
        if 'choices' not in item:
            raise PluginException(PluginConfigChecker.MISSES_KEY.format(item, 'choices'))
        if not isinstance(item['choices'], list):
            raise PluginException(PluginConfigChecker.KEY_INVALID_TYPE.format('choices', item, 'a list'))

        for choice in item['choices']:
            if not isinstance(choice, six.string_types):
                raise PluginException(PluginConfigChecker.CHOICES_INVALID_TYPE.format(item, 'a string'))

    def _check_section(self, item):
        """ Check an section configuration description. """
        if 'repeat' in item and not isinstance(item['repeat'], bool):
            raise PluginException(PluginConfigChecker.KEY_INVALID_TYPE.format('repeat', item, 'a bool'))

        if ('repeat' not in item or item['repeat'] is False) and 'min' in item:
            raise PluginException('The configuration item \'{}\' does contains a \'min\' key but is not repeatable.'.format(item))

        if 'min' in item and not isinstance(item['min'], int):
            raise PluginException(PluginConfigChecker.KEY_INVALID_TYPE.format('min', item, 'an int'))

        if 'content' not in item:
            raise PluginException(PluginConfigChecker.MISSES_KEY.format(item, 'content'))

        try:
            self._check_description(item['content'])
        except PluginException as exception:
            raise PluginException('Exception in \'content\': {0}'.format(exception))

    def _check_nested_enum(self, item):
        """ Check a nested enum configuration description. """
        if 'choices' not in item:
            raise PluginException(PluginConfigChecker.MISSES_KEY.format(item, 'choices'))
        if not isinstance(item['choices'], list):
            raise PluginException(PluginConfigChecker.KEY_INVALID_TYPE.format('choices', item, 'a list'))

        for choice in item['choices']:
            if not isinstance(choice, dict):
                raise PluginException(PluginConfigChecker.KEY_INVALID_TYPE.format('choices', item, 'a dict'))

            for key in ['value', 'content']:
                if key not in choice:
                    raise PluginException('The choices dict \'{0}\' of item \'{1}\' does not contain a \'{2}\' key.'.format(choice, item['name'], key))

            if not isinstance(choice['value'], str):
                raise PluginException('The \'value\' key of choices dict \'{0}\' of item \'{1}\' is not a string.'.format(choice, item['name']))

            try:
                self._check_description(choice['content'])
            except PluginException as exception:
                raise PluginException('Exception in \'choices\' - \'content\': {0}'.format(exception))

    def check_config(self, config):
        """
        Check if a config is valid for the description.
        Raises a PluginException if the config is not valid.
        """
        self._check_config(config, self.__description)

    def _check_config(self, config, description):
        """
        Check if a config is valid for this description.
        Raises a PluginException if the config is not valid.
        """
        if not isinstance(config, dict):
            raise PluginException('The config \'{0}\' is not a dict'.format(config))

        for item in description:
            name = item['name']
            if name not in config:
                raise PluginException('The config does not contain key \'{0}\'.'.format(name))

            for key, type_info in six.iteritems({'str': (six.string_types, 'a string'),
                                                 'int': (int, 'an int'),
                                                 'bool': (bool, 'a bool'),
                                                 'password': (six.string_types, 'a string'),
                                                 'section': (list, 'a list')}):
                if item['type'] == key and not isinstance(config[name], type_info[0]):
                    raise PluginException(PluginConfigChecker.CONFIG_INVALID_TYPE.format(name, config[name], type_info[1]))

            if item['type'] == 'enum':
                if config[name] not in item['choices']:
                    raise PluginException('Config \'{0}\': \'{1}\' is not in the choices: {2}'.format(name, config[name], ', '.join(item['choices'])))
            elif item['type'] == 'section':
                for config_section in config[name]:
                    try:
                        self._check_config(config_section, item['content'])
                    except PluginException as exception:
                        raise PluginException('Exception in section list: {0}'.format(exception))
            elif item['type'] == 'nested_enum':
                if not isinstance(config[name], list) or len(config[name]) != 2:
                    raise PluginException('Config \'{0}\': \'{1}\' is not a list of length 2'.format(name, config[name]))

                choices = [choice['value'] for choice in item['choices']]
                try:
                    i = choices.index(config[name][0])
                    self._check_config(config[name][1], item['choices'][i]['content'])
                except PluginException as ex:
                    raise PluginException("Exception in nested_enum dict: %s" % ex)
                except ValueError:
                    raise PluginException('Config \'{0}\': \'{1}\' is not in the choices: {2}'.format(name, config[name], ', '.join(choices)))


class PluginWebResponse(object):
    """
    Class that will hold the data for an api response from the plugin.
    """
    VARIABLES_TO_SERIALIZE = ['status_code', 'body', 'headers', 'path', 'version']

    def __init__(self, status_code=None, body=None, headers=None, path=None, version=2):
        # type: (Optional[int], Optional[Any], Optional[Dict[str, str]], Optional[str], int) -> None
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}
        self.path = path
        self.version = version
    def serialize(self):
        # type: () -> str
        obj_dict = {}
        for var in PluginWebResponse.VARIABLES_TO_SERIALIZE:
            if var == 'body':
                obj_dict[var] = PluginWebBody(self.body).serialize()
            else:
                obj_dict[var] = getattr(self, var)
        return json.dumps(obj_dict)

    @staticmethod
    def deserialize(serial_str):
        # type: (AnyStr) -> PluginWebResponse
        obj_dict = json.loads(serial_str)
        response = PluginWebResponse()
        for var in PluginWebResponse.VARIABLES_TO_SERIALIZE:
            if var == 'body':
                response.body = PluginWebBody.deserialize(obj_dict['body'])
            else:
                setattr(response, var, obj_dict[var])
        return response

    def __eq__(self, other):
        if not isinstance(other, PluginWebResponse):
            return False
        vars_to_check = ['status_code', 'body', 'headers', 'path']
        for var in vars_to_check:
            if getattr(self, var) != getattr(other, var):
                return False
        return True

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        # type: () -> str
        vars_to_print = ['status_code', 'body', 'headers', 'path']
        vars_str = ',   '.join(
            ['{}={}'.format(name, getattr(self, name)) for name in vars_to_print]
        )
        return '<PluginWebResponse>   {}'.format(vars_str)

class PluginWebRequest(object):
    """
    Class that will hold the data for an api request to the plugin
    """
    VARIABLES_TO_SERIALIZE = ['method', 'body', 'headers', 'path', 'params', 'version']

    def __init__(self, method=None, body=None, headers=None, path=None, params=None, version=2):
        # type: (Optional[str], Optional[Any], Optional[Dict[str, str]], Optional[str], Optional[Dict[str, str]], int) -> None
        self.method = method
        self.body = body
        self.headers = headers or {}
        self.path = path
        self.params = params or {}
        self.version = version

    def serialize(self):
        # type: () -> str
        obj_dict = {}
        for var in PluginWebRequest.VARIABLES_TO_SERIALIZE:
            if var == 'body':
                obj_dict[var] = PluginWebBody(self.body).serialize()
            else:
                obj_dict[var] = getattr(self, var)
        return json.dumps(obj_dict)


    @staticmethod
    def deserialize(serial_str):
        # type: (AnyStr) -> PluginWebRequest
        obj_dict = json.loads(serial_str)
        response = PluginWebRequest()
        for var in PluginWebRequest.VARIABLES_TO_SERIALIZE:
            if var == 'body':
                response.body = PluginWebBody.deserialize(obj_dict['body'])
            else:
                setattr(response, var, obj_dict[var])
        return response

    def __eq__(self, other):
        if not isinstance(other, PluginWebRequest):
            return False
        vars_to_check = ['method', 'body', 'headers', 'path', 'params']
        for var in vars_to_check:
            if getattr(self, var) != getattr(other, var):
                return False
        return True

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        # type: () -> str
        vars_to_print = ['method', 'body', 'headers', 'path', 'params']
        vars_str = ',   '.join(
            ['{}={}'.format(name, getattr(self, name)) for name in vars_to_print]
        )
        return '<PluginWebRequest>   {}'.format(vars_str)

class PluginWebBody():
    """
    Class that will hold the PluginWebBody content and can serialize the content in Base64 string.
    """

    def __init__(self, content=None):
        self.content = content
        self.obj_type = type(content).__name__

    def serialize(self):
        # type: () -> Optional[str]
        if self.obj_type not in ['str', 'bytes', 'dict', 'NoneType', 'unicode']:
            raise AttributeError('Could not serialize body data of type: {}'.format(type(self.content)))
        if self.content is None:
            return None
        if self.obj_type == 'str':
            content_bytes = self.content.encode('utf-8')  # type: bytes
            encoded = base64.b64encode(content_bytes)
        elif self.obj_type == 'dict':
            json_dump = json.dumps(self.content).encode('utf-8')  # type: bytes
            encoded = base64.b64encode(json_dump)
        else:  # if bytes (py3 only)
            encoded = base64.b64encode(self.content)
        obj_dict = {
            'type': self.obj_type,
            'data': encoded
        }
        return json.dumps(obj_dict)

    @staticmethod
    def deserialize(serial):
        # type: (Optional[AnyStr]) -> Optional[Any]
        if serial is None:
            return None
        obj_dict = json.loads(serial)
        obj_type = obj_dict['type']
        data = obj_dict['data']
        if obj_type not in ['str', 'bytes', 'dict', 'NoneType', 'unicode']:
            raise AttributeError('Could not deserialize serial data of type: {}'.format(type(serial)))
        content = None
        if data is not None:
            content = base64.b64decode(data)
        if content is not None:
            if obj_type == 'dict':
                try:
                    content_json = json.loads(content)
                    return content_json
                except Exception:
                    return content.decode(encoding='utf-8')
            elif obj_type == 'str':
                return content.decode(encoding='utf-8')
            else:  # bytes string
                return content
        return None

    def __eq__(self, other):
        if not isinstance(other, PluginWebBody):
            return False
        vars_to_check = ['content', 'obj_type']
        for var in vars_to_check:
            if getattr(self, var) != getattr(other, var):
                return False
        return True
