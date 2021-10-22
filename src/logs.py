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
from logging import handlers
import re

if False:  # MYPY
    from typing import Union, Optional

logger = logging.getLogger('openmotics')


class Logs(object):

    LOG_FORMAT = "%(asctime)s - %(levelname)-8s - (%(threadName)s) - %(name)s - %(message)s"

    @staticmethod
    def setup_logger(log_level_override=None, enable_update_logging=False):
        """
        Setup the OpenMotics logger.
        :param log_level_override: Sets the main log level for OpenMotics logging to the default StreamHandler/SysLogHandler
        :param enable_update_logging: Enables logging to the `update_log` file. This will always log in DEBUG
        """

        import constants
        from platform_utils import System

        # Remove all log handlers (since python2 `defaultConfig` has no `force` flag)
        root_logger = logging.getLogger()
        while root_logger.handlers:
            root_logger.removeHandler(root_logger.handlers[0])

        # Setup basic stream handler
        logging.basicConfig(format=Logs.LOG_FORMAT, level=logging.INFO)

        openmotics_log_level = Logs.get_configured_loglevel(fallback=logging.INFO, override=log_level_override)

        # Alter some system loggers
        requests_logger = logging.getLogger('requests.packages.urllib3.connectionpool')
        requests_logger.setLevel(logging.WARNING)

        update_handler = None
        if enable_update_logging:
            update_handler = handlers.RotatingFileHandler(constants.get_update_log_location(), maxBytes=3 * 1024 ** 2, backupCount=2)
            update_handler.setLevel(logging.DEBUG)
            update_handler.setFormatter(logging.Formatter(Logs.LOG_FORMAT))
            openmotics_log_level = min(openmotics_log_level, logging.DEBUG)

        Logs.set_service_loglevel(openmotics_log_level)

        for _logger in Logs._get_service_loggers():
            for extra_handler in [update_handler]:
                # Add extra handlers, where available
                if extra_handler is not None:
                    _logger.addHandler(extra_handler)

    @staticmethod
    def set_service_loglevel(level, namespace=None):  # type: (Union[int, str], Optional[str]) -> None
        if namespace:
            logger.info('Switching %s loglevel to %s', namespace, level)
            for logger_namespace in logging.root.manager.loggerDict:  # type: ignore
                if re.match("^{}.*".format(namespace), logger_namespace):
                    _logger = logging.getLogger(logger_namespace)
                    _logger.setLevel(level)
        else:
            logger.info('Switching services loglevel to %s', level)
            for _logger in Logs._get_service_loggers():
                _logger.setLevel(level)
                _logger.propagate = True

    @staticmethod
    def _get_service_loggers():
        for logger_namespace in logging.root.manager.loggerDict:  # type: ignore
            if re.match("^openmotics.*|^gateway.*|^master.*|^plugins.*|^energy.*", logger_namespace):
                yield logging.getLogger(logger_namespace)

    @staticmethod
    def get_configured_loglevel(fallback=logging.INFO, override=None):
        import constants
        from six.moves.configparser import ConfigParser, NoOptionError, NoSectionError
        if override is not None:
            return override
        try:
            config = ConfigParser()
            config.read(constants.get_config_file())
            log_level = config.get('logging', 'log_level')
            return logging._checkLevel(log_level) if log_level else fallback  # type: ignore
        except NoOptionError:
            return fallback
        except NoSectionError:
            return fallback
