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
logger = logging.getLogger('openmotics')


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
def software_update(toolbox_session):
    toolbox = toolbox_session

    update = os.environ.get('OPENMOTICS_UPDATE')
    if update:
        try:
            logger.info('applying update {}...'.format(update))
            with open(update, 'rb') as fd:
                hasher = hashlib.md5()
                hasher.update(fd.read())
                md5 = hasher.hexdigest()
            toolbox.dut.post('/update', {'version': '0.0.0', 'md5': md5},
                             files={'update_data': open(update, 'rb')})
            logger.info('waiting for update to complete...')
            time.sleep(120)
            toolbox.health_check(timeout=480)
        finally:
            toolbox.health_check()
            toolbox.dut.login()
            logger.debug('update output')
            since = time.time()
            while since > time.time() - 120:
                output = toolbox.dut.get('/get_update_output')['output']
                logger.info(output)
                if 'exit 0' in output:
                    break
            output = toolbox.dut.get('/get_update_output')['output']
            assert 'exit 0' in output
            assert 'DONE' in output

    logger.info('gateway {}'.format(toolbox.get_gateway_version()))


@fixture(scope='session')
def firmware_updates(toolbox_session):
    toolbox = toolbox_session

    if os.environ.get('OPENMOTICS_UPDATE'):
        logger.debug('firmware updates, skipped')
        return

    versions = toolbox.get_firmware_versions()
    logger.info('firmware {}'.format(' '.join('{}={}'.format(k, v) for k, v in versions.items())))
    firmware = {}
    # TODO: Add support for Core+ firmwares
    force_update = os.environ.get('OPENMOTICS_FORCE_UPDATE', '0') == '1'
    if TEST_PLATFORM != TestPlatform.CORE_PLUS:
        master_firmware = os.environ.get('OPENMOTICS_MASTER_FIRMWARE')
        if master_firmware and (force_update or master_firmware != versions['M']):
            logger.info('master firmware {} -> {}...'.format(versions['M'], master_firmware))
            firmware['master'] = master_firmware
        output_firmware = os.environ.get('OPENMOTICS_OUTPUT_FIRMWARE')
        if output_firmware and (force_update or output_firmware != versions['O']):
            logger.info('Output firmware {} -> {}...'.format(versions['O'], output_firmware))
            firmware['output'] = output_firmware
        input_firmware = os.environ.get('OPENMOTICS_INPUT_FIRMWARE')
        if input_firmware and (force_update or input_firmware != versions['I']):
            logger.info('Input firmware {} -> {}...'.format(versions['I'], input_firmware))
            firmware['input'] = input_firmware
        can_firmware = os.environ.get('OPENMOTICS_CAN_FIRMWARE')
        if can_firmware and (force_update or can_firmware != versions['C']):
            logger.info('CAN firmware {} -> {}...'.format(versions['C'], can_firmware))
            firmware['can'] = can_firmware
    if firmware:
        for module, version in firmware.items():
            logger.info('updating {} firmware...'.format(module))
            for _ in range(8):
                try:
                    toolbox.health_check(timeout=120)
                    toolbox.dut.get('/update_firmware', {module: version})
                    toolbox.health_check(timeout=120)
                    break
                except Exception:
                    logger.error('updating {} failed, retrying'.format(module))
                    time.sleep(30)
        versions = toolbox.get_firmware_versions()
        logger.info('firmware {}'.format(' '.join('{}={}'.format(k, v) for k, v in versions.items())))


@fixture
def toolbox(toolbox_session, software_update, firmware_updates):
    toolbox = toolbox_session
    toolbox.tester.get('/plugins/syslog_receiver/reset', success=False)
    toolbox.health_check(timeout=360)
    toolbox.module_error_check()
    try:
        yield toolbox
    finally:
        toolbox.print_logs()
