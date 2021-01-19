import logging
from logging import handlers


class Logs(object):

    @staticmethod
    def setup_logger(default_level=logging.INFO, extra_configuration=None):
        """ Setup the OpenMotics logger. """

        from platform_utils import System

        handler = logging.StreamHandler()
        handler.setLevel(default_level)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

        syslog_handler = None
        if System.get_operating_system().get('ID') == System.OS.BUILDROOT:
            syslog_handler = handlers.SysLogHandler(address='/dev/log')
            syslog_handler.setLevel(default_level)
            syslog_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

        for logger_namespace in ['openmotics', 'gateway']:
            _logger = logging.getLogger(logger_namespace)
            _logger.setLevel(default_level)
            _logger.propagate = False
            _logger.addHandler(handler)

            if syslog_handler is not None:
                _logger.addHandler(syslog_handler)

            if extra_configuration is not None:
                extra_configuration(_logger)
