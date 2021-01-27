"""
Main eSafe communication objects and implementations
"""
import requests
import time

class EsafeExeption(Exception):
    pass

class EsafeApi():
    API_PREFIX = '/api/v1'
    TEST_ENDPOINT = '/users'

    def __init__(self, host, port):
        log_debug('creating eSafe API object: {}:{}'.format(host, port))
        self.host = host
        self.port = port
        self.is_connected = False

        self.test_connection()
        log_debug('creating eSafe API object done')

    def _get_url(self, endpoint):
        """ Create the full endpoint api url """
        log_function_call(locals())
        url = 'http://{}:{}{}{}'.format(
            self.host,
            self.port,
            EsafeApi.API_PREFIX,
            endpoint
        )
        return url

    def test_connection(self):
        """ Function to do a basic call to the eSafe api """
        log_function_call(locals())
        resp = requests.get(self._get_url(EsafeApi.TEST_ENDPOINT), params=None)
        if resp is not None:
            self.is_connected = (resp.status_code == 200)
            log_debug('Connected!!')

    def _perform_get_request(self, url, params=None):
        # type: (str, Optional[Dict[str, str]]) -> Optional[requests.models.Response]
        """ Executes a get request. First checks if the device is in reach or not"""
        if not self.is_connected:
            self.test_connection()
        if not self.is_connected:
            raise EsafeExeption('Could not reach eSafe device, is the device online?')
        else:
            resp = None
            try:
                resp = requests.get(url, params=params)
            except Exception:
                self.is_connected = False
            return resp

    def _perform_post_request(self, url, body=None, params=None):
        # type: (str, str, Optional[Dict[str, str]]) -> Optional[requests.models.Response]
        """ Executes a post request. First checks if the device is in reach or not"""
        if not self.is_connected:
            self.test_connection()
        if not self.is_connected:
            raise EsafeExeption('Could not reach eSafe device, is the device online?')
        else:
            resp = None
            try:
                resp = requests.post(url, params=params, json=body)
            except Exception:
                self.is_connected = False
            return resp

    def proxy_request(self, url):
        return self._perform_get_request(url)



    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '<EsafeApi>: {}:{}'.format(self.host, self.port)


class EsafeManager():
    def __init__(self, host, port):
        log_debug('creating eSafe Manager object: {}:{}'.format(host, port))
        self.api = EsafeApi(host, port)
        log_debug('eSafe Manager object creation done!')

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '<EsafeManager>: {}'.format(self.api)


"""
--------------------------------------------------------
Logging functions
--------------------------------------------------------
"""


def log_debug(msg):
    # check if logger exists
    # this will make sure that there is only logged when this file is runned
    if 'logger' in globals():
        logger.debug(msg)


def log_function_call(loc):
    if __name__ == "__main__":
        s = inspect.stack()
        calling_func = s[1][3]
        calling_func_line = s[1][2]
        log_debug('Function called: {} @ {} With arguments {}'.format(calling_func, calling_func_line, loc))


if __name__ == "__main__":
    import logging
    import inspect
    log_level = logging.DEBUG
    logger = logging.getLogger('eSafeConnect')

    def setup_logger():
        logger.setLevel(log_level)
        logger.propagate = False

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    setup_logger()

    log_debug('starting')

    ip = '192.168.0.154'
    port = 80
    em = EsafeManager(ip, port)


"""
data = [
    FrameInfo(frame= < frame at 0x7f2a9798d520, file 'esafe.py', line 61, code log_function_call >, filename='esafe.py', lineno=60, function='log_function_call', code_context=['        s = inspect.stack()\n'], index=0),
    FrameInfo(frame= < frame at 0x7f2a9797f780, file 'esafe.py', line 22, code _get_url > , filename='esafe.py', lineno=22, function='_get_url', code_context=['        log_function_call()\n'], index=0),
    FrameInfo(frame= < frame at 0x7f2a9798e040, file 'esafe.py', line 33, code test_connection > , filename='esafe.py', lineno=33, function='test_connection', code_context=['        result = requests.get(self._get_url(EsafeApi.TEST_ENDPOINT),params=None)\n'], index=0),
    FrameInfo(frame= < frame at 0x7f2a97980900, file 'esafe.py', line 17, code __init__ > , filename='esafe.py', lineno=17, function='__init__', code_context=['        self.test_connection()\n'], index=0),
    FrameInfo(frame= < frame at 0x7f2a97980580, file 'esafe.py', line 42, code __init__ > , filename='esafe.py', lineno=42, function='__init__', code_context=['        self.api = EsafeApi(host, port)\n'], index=0),
    FrameInfo(frame= < frame at 0x7f2a9c166640, file 'esafe.py', line 86, code < module>>, filename='esafe.py', lineno=86, function='<module>', code_context=['    em = EsafeManager(ip, port)\n'], index=0)
    ]

"""