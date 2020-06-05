from __future__ import absolute_import
import os
import logging

from hypothesis import settings
from pytest import fixture
from requests.packages import urllib3

from .toolbox import Toolbox

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.getLogger('urllib3').propagate = False
logger = logging.getLogger('openmotics')


settings.register_profile('default', deadline=None, max_examples=10, stateful_step_count=5, print_blob=True)
settings.register_profile('once', deadline=None, max_examples=1, stateful_step_count=5, print_blob=True)
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


@fixture
def toolbox(toolbox_session):
    toolbox = toolbox_session
    toolbox.tester.get('/plugins/syslog_receiver/reset', success=False)
    yield toolbox
    toolbox.print_logs()
