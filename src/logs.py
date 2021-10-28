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

import logging
import sys
from logging import handlers
import os
import re
import constants
import warnings

if False:  # MYPY
    from typing import Union, Optional, Generator
    from logging import Logger

# Different name to reduce confusion between multiple used loggers
global_logger = logging.getLogger(__name__)


class Logs(object):

    LOG_FORMAT = "%(asctime)s - %(levelname)-8s - (%(threadName)s) - %(name)s - %(message)s"
    PREFIX = constants.OPENMOTICS_PREFIX  # e.g. /x
    UPDATE_LOGS_FOLDER = os.path.join(PREFIX, 'update_logs')  # e.g. /x/update_logs

    @staticmethod
    def setup_logger(log_level_override=None):
        """
        Setup the OpenMotics logger.
        :param log_level_override: Sets the main log level for OpenMotics logging to the default StreamHandler/SysLogHandler
        """

        from platform_utils import System

        # Remove all log handlers (since python2 `defaultConfig` has no `force` flag)
        root_logger = logging.getLogger()
        while root_logger.handlers:
            root_logger.removeHandler(root_logger.handlers[0])

        # Alter some system loggers
        requests_logger = logging.getLogger('requests.packages.urllib3.connectionpool')
        requests_logger.setLevel(logging.WARNING)
        warnings.filterwarnings('ignore')  # Supressed so called `user warnings`

        # Setup basic stream handler
        logging.basicConfig(format=Logs.LOG_FORMAT, level=logging.INFO)

        # Set log level
        if log_level_override is not None:
            openmotics_log_level = log_level_override
        else:
            openmotics_log_level = Logs._get_configured_loglevel(fallback=logging.INFO)

        # Apply log level
        for namespace in Logs._get_service_namespaces():
            Logs.set_loglevel(openmotics_log_level, namespace)

    @staticmethod
    def get_update_logger(name):  # type: (str) -> Logger
        """
        Sets up a logger for update logging;
        * Logs to `{OPENMOTICS_PREFIX}/update/logs/{name}.log`
        * Namespace is `update.{name}`
        """
        if not os.path.exists(Logs.UPDATE_LOGS_FOLDER):
            os.makedirs(Logs.UPDATE_LOGS_FOLDER)
        namespace = 'update.{0}'.format(name)
        filename = os.path.join(Logs.UPDATE_LOGS_FOLDER, '{0}.log'.format(name))
        update_handler = handlers.RotatingFileHandler(filename, maxBytes=3 * 1024 ** 2, backupCount=2)
        update_handler.setFormatter(logging.Formatter(Logs.LOG_FORMAT))
        update_handler.openmotics_update_handler = True  # type: ignore
        logger = logging.getLogger(namespace)
        handler_found = False
        for handler in logger.handlers:
            if hasattr(handler, 'openmotics_update_handler'):
                handler_found = True
                break
        if not handler_found:
            logger.addHandler(update_handler)
        logger.propagate = True
        return logger

    @staticmethod
    def get_print_logger(namespace):
        """
        Sets up a logger that simply prints to stdout
        """
        print_handler = logging.StreamHandler(sys.stdout)
        print_handler.openmotics_print_handler = True  # type: ignore
        logger = logging.getLogger(namespace)
        handler_found = False
        for handler in logger.handlers:
            if hasattr(handler, 'openmotics_print_handler'):
                handler_found = True
                break
        if not handler_found:
            logger.addHandler(print_handler)
        logger.propagate = False
        return logger

    @staticmethod
    def set_loglevel(level, namespace):  # type: (Union[int, str], Optional[str]) -> None
        for logger_namespace in logging.root.manager.loggerDict:  # type: ignore
            if namespace is None or re.match("^{}.*".format(namespace), logger_namespace):
                logger = logging.getLogger(logger_namespace)
                logger.setLevel(level)
                logger.propagate = True

    @staticmethod
    def _get_service_namespaces():
        return ['openmotics', 'gateway', 'master', 'plugins', 'energy', 'update']

    @staticmethod
    def _get_configured_loglevel(fallback=logging.INFO):
        import constants
        from six.moves.configparser import ConfigParser, NoOptionError, NoSectionError
        try:
            config = ConfigParser()
            config.read(constants.get_config_file())
            log_level = config.get('logging', 'log_level')
            return logging._checkLevel(log_level) if log_level else fallback  # type: ignore
        except (NoOptionError, NoSectionError):
            return fallback
