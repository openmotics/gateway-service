import unittest
import base64
import logging
import msgpack
import requests
import time
from ws4py.client.threadedclient import WebSocketClient
from toolbox import exception_handler

LOGGER = logging.getLogger('openmotics')

#                                            _   _
#                                           | | (_)
#    ___  _ __   ___ _ __    _ __ ___   ___ | |_ _  ___ ___
#   / _ \| '_ \ / _ \ '_ \  | '_ ` _ \ / _ \| __| |/ __/ __|
#  | (_) | |_) |  __/ | | | | | | | | | (_) | |_| | (__\__ \
#   \___/| .__/ \___|_| |_| |_| |_| |_|\___/ \__|_|\___|___/
#        | |
#        |_|


class WebsocketTest(unittest.TestCase):
    webinterface = None
    tools = None
    token = ''
    DATA = None

    @classmethod
    def setUpClass(cls):
        if not cls.tools.healthy_status:
            raise unittest.SkipTest('The Testee is showing an unhealthy status. All tests are skipped.')
        cls.token = cls.tools._get_new_token('openmotics', '123456')

    def setUp(self):
        if not self.tools.discovery_success:
            self.tools.discovery_success = self.tools._assert_discovered(self.token, self.webinterface)
            if not self.tools.discovery_success:
                LOGGER.error('Skipped: {} due to discovery failure.'.format(self.id()))
                self.skipTest('Failed to discover modules.')
        LOGGER.info('Running: {}'.format(self.id()))

    @exception_handler
    def test_websocket_output_change(self):
        """ Testing the websocket on the Testee for output_change event. """

        token = requests.get('https://{0}/login'.format('10.91.99.52'),
                             params={'username': 'openmotics',
                                     'password': '123456'},
                             verify=False).json()['token']
        socket = PassthroughClient('wss://{0}/ws_events'.format('10.91.99.52'),
                                   protocols=['authorization.bearer.{0}'.format(
                                       base64.b64encode(token.encode('ascii')).decode('utf-8').replace('=', ''))], callback=_callback)
        socket.connect()

        self.tools.clicker_releaser(3, token, True)
        time.sleep(0.5)
        self.assertTrue(bool(WebsocketTest.DATA), ' Should not be None. Got: {0}'.format(WebsocketTest.DATA))
        time.sleep(1)
        self.assertTrue(WebsocketTest.DATA['data']['data']['status']['on'], 'Should contain the status of the output. Got: {0}'.format(WebsocketTest.DATA))
        self.assertEquals(WebsocketTest.DATA['data']['data']['id'], 3, 'Should contain the correct triggered ID. Got: {0}'.format(WebsocketTest.DATA))
        self.assertEquals(WebsocketTest.DATA['type'], 'OUTPUT_CHANGE', 'Should contain the correct event type. Got: {0}'.format(WebsocketTest.DATA))

        time.sleep(0.5)

        self.tools.clicker_releaser(3, token, False)

        time.sleep(0.5)
        self.assertTrue(bool(WebsocketTest.DATA), ' Got something else: {0}'.format(WebsocketTest.DATA))
        time.sleep(1)
        self.assertTrue(not WebsocketTest.DATA['data']['data']['status']['on'], 'Should contain the status of the output. Got: {0}'.format(WebsocketTest.DATA))
        self.assertEquals(WebsocketTest.DATA['data']['data']['id'], 3, 'Should contain the correct triggered ID. Got: {0}'.format(WebsocketTest.DATA))
        self.assertEquals(WebsocketTest.DATA['type'], 'OUTPUT_CHANGE', 'Should contain the correct event type. Got: {0}'.format(WebsocketTest.DATA))

    @exception_handler
    def test_websocket_input_trigger(self):
        """ Testing the websocket on the Testee for input_trigger event. """
        token = requests.get('https://{0}/login'.format('10.91.99.52'),
                             params={'username': 'openmotics',
                                     'password': '123456'},
                             verify=False).json()['token']
        socket = PassthroughClient('wss://{0}/ws_events'.format('10.91.99.52'),
                                   protocols=['authorization.bearer.{0}'.format(
                                       base64.b64encode(token.encode('ascii')).decode('utf-8').replace('=', ''))], callback=_callback)
        socket.connect()

        self.webinterface.set_output(id=4, is_on=True)
        time.sleep(0.5)
        self.webinterface.set_output(id=4, is_on=False)
        self.assertTrue(bool(WebsocketTest.DATA), ' Got something else: {0}'.format(WebsocketTest.DATA))
        time.sleep(1)
        self.assertEquals(WebsocketTest.DATA['data']['data']['id'], 4, 'Should contain the correct triggered ID. Got: {0}'.format(WebsocketTest.DATA))
        self.assertEquals(WebsocketTest.DATA['type'], 'OUTPUT_CHANGE', 'Should contain the correct event type. Got: {0}'.format(WebsocketTest.DATA))

        time.sleep(0.5)

        self.webinterface.set_output(id=4, is_on=True)
        time.sleep(0.5)
        self.webinterface.set_output(id=4, is_on=False)
        self.assertTrue(bool(WebsocketTest.DATA), ' Got something else: {0}'.format(WebsocketTest.DATA))
        time.sleep(1)
        self.assertEquals(WebsocketTest.DATA['data']['data']['id'], 4, 'Should contain the correct triggered ID. Got: {0}'.format(WebsocketTest.DATA))
        self.assertEquals(WebsocketTest.DATA['type'], 'OUTPUT_CHANGE', 'Should contain the correct event type. Got: {0}'.format(WebsocketTest.DATA))


class PassthroughClient(WebSocketClient):
    """ PassthroughClient is a custom WebSocketClient. """
    def __init__(self, *args, **kwargs):
        self.callback = kwargs.pop('callback')
        WebSocketClient.__init__(self, *args, **kwargs)

    def opened(self):
        self.send(
            msgpack.dumps(
                {'type': 'ACTION',
                 'data': {'action': 'set_subscription',
                          'types': ['OUTPUT_CHANGE', 'INPUT_TRIGGER']}}
            ),
            binary=True
        )

    def received_message(self, message):
        try:
            data = msgpack.loads(message.data)
            self.callback(data)
        except Exception:
            pass


def _callback(data):
    """ _callback will set the variable DATA when a message is received. """
    WebsocketTest.DATA = data
