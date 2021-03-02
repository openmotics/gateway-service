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


class Logs(object):

    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @staticmethod
    def setup_logger(log_level=logging.INFO, enable_update_logging=False):
        """
        Setup the OpenMotics logger.
        :param log_level: Sets the main log level for OpenMotics logging to the default StreamHandler/SysLogHandler
        :param enable_update_logging: Enables logging to the `update_log` file. This will always log in DEBUG
        """

        import constants
        from platform_utils import System

        # Remove all log handlers (since python2 `defaultConfig` has no `force` flag)
        root_logger = logging.getLogger()
        while root_logger.handlers:
            root_logger.removeHandler(root_logger.handlers[0])

        # Setup basic stream handler
        logging.basicConfig(format=Logs.LOG_FORMAT,
                            level=logging.INFO)
        openmotics_log_level = log_level

        # Alter some system loggers
        requests_logger = logging.getLogger('requests.packages.urllib3.connectionpool')
        requests_logger.setLevel(logging.WARNING)

        # Prepare extra handlers
        openmotics_stream_handler = logging.StreamHandler()
        openmotics_stream_handler.setLevel(log_level)
        openmotics_stream_handler.setFormatter(logging.Formatter(Logs.LOG_FORMAT))

        update_handler = None
        if enable_update_logging:
            update_handler = handlers.RotatingFileHandler(constants.get_update_log_location(), maxBytes=3 * 1024 ** 2, backupCount=2)
            update_handler.setLevel(logging.DEBUG)
            update_handler.setFormatter(logging.Formatter(Logs.LOG_FORMAT))
            openmotics_log_level = min(log_level, logging.DEBUG)

        syslog_handler = None
        if System.get_operating_system().get('ID') == System.OS.BUILDROOT:
            syslog_handler = handlers.SysLogHandler(address='/dev/log')
            syslog_handler.setLevel(log_level)
            syslog_handler.setFormatter(logging.Formatter(Logs.LOG_FORMAT))

        for logger_namespace in ['openmotics', 'gateway']:
            _logger = logging.getLogger(logger_namespace)
            _logger.setLevel(openmotics_log_level)
            _logger.propagate = True

            for extra_handler in [openmotics_stream_handler, update_handler, syslog_handler]:
                # Add extra handlers, where available
                if extra_handler is not None:
                    _logger.addHandler(extra_handler)
