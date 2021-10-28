from __future__ import absolute_import

import hashlib
import logging
import os
import sys
import time

from hypothesis import Verbosity, settings
from pytest import fixture, mark
from requests.packages import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.insert(0, os.path.abspath(os.path.join(__file__, '../..')))

from tests.toolbox import Toolbox
from tests.hardware_layout import TEST_PLATFORM, TestPlatform


logging.getLogger('urllib3').propagate = False
logger = logging.getLogger(__name__)


settings.register_profile('default', deadline=None, max_examples=10, stateful_step_count=5, print_blob=True)
settings.register_profile('debug', deadline=None, max_examples=10, stateful_step_count=5, print_blob=True, verbosity=Verbosity.verbose)
settings.register_profile('once', deadline=None, max_examples=1, stateful_step_count=1, print_blob=True)
settings.register_profile('ci', deadline=None, max_examples=100, stateful_step_count=10, print_blob=True)
settings.load_profile(os.getenv('HYPOTHESIS_PROFILE', 'default'))


@fixture(scope='session')
def toolbox_session():
    toolbox = Toolbox()
    try:
        toolbox.initialize()
    finally:
        toolbox.print_logs()
    return toolbox


@fixture(scope='session')
def update(toolbox_session):
    toolbox = toolbox_session

    update_version = os.environ.get('UPDATE_VERSION')
    update_metadata = os.environ.get('UPDATE_METADATA')
    if not update_version or not update_metadata:
        return

    logger.info('Applying update {}...'.format(update_version))
    toolbox.dut.post('/update', {'version': update_version,
                                 'metadata': update_metadata})
    logger.info('Waiting for update to complete...')
    toolbox.wait_for_completed_update()

    logger.info('Gateway version {}'.format(toolbox.get_gateway_version()))


@fixture
def toolbox(toolbox_session, update):
    def _log_debug_buffer(buffer_):
        for key in sorted(buffer_.keys()):
            logger.debug('   {0} - {1}'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(key))),
                buffer_[key]
            ))

    toolbox = toolbox_session
    toolbox.tester.get('/plugins/syslog_receiver/reset', success=False)
    toolbox.health_check(timeout=360)
    toolbox.module_error_check()
    try:
        yield toolbox
    finally:
        toolbox.print_logs()

        # Printing the debug buffer if the test fails to inspect the commands sent to the master
        debug_buffer = toolbox.dut.get('/get_master_debug_buffer', {'amount': 200})
        logger.debug('### Debug Buffer DUT')
        logger.debug(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        logger.debug('### WRITE')
        logger.debug(_log_debug_buffer(debug_buffer['write']))
        logger.debug('### READ')
        logger.debug(_log_debug_buffer(debug_buffer['read']))
