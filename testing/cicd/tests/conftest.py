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
            time.sleep(120)

    logger.info('gateway {}'.format(toolbox.get_gateway_version()))


@fixture(scope='session')
def firmware_updates(toolbox_session):
    toolbox = toolbox_session

    if os.environ.get('OPENMOTICS_UPDATE'):
        logger.debug('Firmware updates skipped')
        return

    versions = toolbox.get_firmware_versions()
    logger.info('Current firmwares: {}'.format(', '.join('{}={}'.format(k, v) for k, v in versions.items())))
    firmware = {}
    force_update = os.environ.get('OPENMOTICS_FORCE_UPDATE', '0') == '1'

    def _check_and_schedule(letter, firmware_type, desired_version):
        if desired_version:
            if letter in versions:
                if force_update or desired_version != versions[letter]:
                    logger.info('Firmware {}: {} -> {}...'.format(firmware_type, versions[letter], desired_version))
                    firmware[firmware_type] = desired_version
            else:
                logger.info('Skipping {0} - no module found'.format(firmware_type))

    if TEST_PLATFORM == TestPlatform.DEBIAN:
        _check_and_schedule('M', 'master_classic', os.environ.get('OPENMOTICS_MASTER_CLASSIC_FIRMWARE'))
    if TEST_PLATFORM == TestPlatform.CORE_PLUS:
        _check_and_schedule('M', 'master_core', os.environ.get('OPENMOTICS_MASTER_CORE_FIRMWARE'))

    _check_and_schedule('O', 'output', os.environ.get('OPENMOTICS_OUTPUT_FIRMWARE'))
    _check_and_schedule('D', 'dim_control', os.environ.get('OPENMOTICS_DIM_CONTROL_FIRMWARE'))
    _check_and_schedule('I', 'input', os.environ.get('OPENMOTICS_INPUT_FIRMWARE'))
    _check_and_schedule('T', 'temperature', os.environ.get('OPENMOTICS_TEMPERATURE_FIRMWARE'))
    _check_and_schedule('C', 'can_control', os.environ.get('OPENMOTICS_CAN_CONTROL_FIRMWARE'))
    if TEST_PLATFORM == TestPlatform.CORE_PLUS:
        _check_and_schedule('UC', 'ucan', os.environ.get('OPENMOTICS_MICRO_CAN_FIRMWARE'))

    if firmware:
        for module, version in firmware.items():
            logger.info('updating {} firmware...'.format(module))
            for _ in range(8):
                try:
                    toolbox.health_check(timeout=120)
                    toolbox.dut.get('/update_firmware', {'module_type': module,
                                                         'firmware_version': version})
                    time.sleep(5)
                    toolbox.health_check(timeout=120)
                    break
                except Exception:
                    logger.error('updating {} failed, retrying'.format(module))
                    time.sleep(30)

        versions = toolbox.get_firmware_versions()
        logger.info('Post-update firmwares: {}'.format(', '.join('{}={}'.format(k, v) for k, v in versions.items())))
        mismatches = []
        for expected, current in [('master_classic', 'M'),
                                  ('master_core', 'M'),
                                  ('output', 'O'),
                                  ('dim_control', 'D'),
                                  ('input', 'I'),
                                  ('temperature', 'T'),
                                  ('can_control', 'C')]:
            if expected in firmware and current in versions and firmware[expected] != versions[current]:
                mismatches.append('{0}({1}!={2})'.format(current, firmware[expected], versions[current]))
        if mismatches:
            logger.warning('Firmware mismatches: {0}'.format(', '.join(mismatches)))
            # TODO: assert False  # Fail


@fixture
# def toolbox(toolbox_session, software_update, firmware_updates):
def toolbox(toolbox_session):
    toolbox = toolbox_session
    toolbox.tester.get('/plugins/syslog_receiver/reset', success=False)
    toolbox.health_check(timeout=360)
    toolbox.module_error_check()
    try:
        yield toolbox
    finally:
        toolbox.print_logs()
        # # TODO: Only print the buffer when a test fails - this will print the buffer after every test
        # logger.debug(toolbox.dut.get('/get_master_debug_buffer'))
