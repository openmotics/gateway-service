# Copyright (C) 2016 OpenMotics BV
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
""" The update modules provides the update functionality. """

from __future__ import absolute_import

from platform_utils import System
System.import_libs()

import fcntl
import glob
import hashlib
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

import requests
from six.moves.configparser import ConfigParser, NoOptionError
from six.moves.urllib.parse import urlparse, urlunparse

import constants


logging.basicConfig(level=logging.INFO, filemode='w', format='%(message)s', filename=constants.get_update_output_file())
logger = logging.getLogger('update.py')
logger.setLevel(logging.DEBUG)

PREFIX = '/opt/openmotics'
SUPERVISOR_SERVICES = ('openmotics', 'vpn_service')
FIRMWARE_FILES = {'gateway_service': 'gateway.tgz',
                  'gateway_frontend': 'gateway_frontend.tgz',
                  'gateway_os': 'gateway_os.tgz',
                  'master_classic': 'm_classic_firmware.hex',
                  'power': 'p_firmware.hex',
                  'energy': 'e_firmware.hex',
                  'can': 'c_firmware.hex',
                  'output': 'o_firmware.hex',
                  'input': 'i_firmware.hex',
                  'dimmer': 'd_firmware.hex',
                  'temperature': 't_firmware.hex'}
MODULE_TYPES = {'can': 'c',
                'output': 'o',
                'input': 'i',
                'dimmer': 'd',
                'temperature': 't'}


def cmd(command, **kwargs):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    output = ''
    for line in proc.stdout:
        if line:
            logger.debug(line.rstrip('\n'))
        output += line
    ret = proc.wait()
    if ret != 0:
        raise Exception('Command {} failed'.format(command))
    return output


def extract_legacy_update(update_file, expected_md5):
    hash = hashlib.md5()
    with open(update_file, 'rb') as fd:
        for chunk in iter(lambda: fd.read(128 * hash.block_size), ''):
            hash.update(chunk)
    calculated_md5 = hash.hexdigest()
    if calculated_md5 != expected_md5:
        raise ValueError('update.tgz md5:%s does not match expected md5:%s' % (calculated_md5, expected_md5))

    cmd(['tar', 'xzf', update_file])

def fetch_metadata(config, version, expected_md5):
    response = requests.get(get_metadata_url(config, version))
    if response.status_code != 200:
        raise ValueError('failed to get update metadata')
    hasher = hashlib.md5()
    hasher.update(response.content)
    calculated_md5 = hasher.hexdigest()
    if expected_md5 != calculated_md5:
        logger.error(response.content)
        raise ValueError('update metadata md5:%s does not match expected md5:%s' % (calculated_md5, expected_md5))
    return response.json()


def get_metadata_url(config, version):
    gateway_uuid = config.get('OpenMotics', 'uuid')
    try:
        uri = urlparse(config.get('OpenMotics', 'update_url'))
    except NoOptionError:
        path = '/api/v1/base/updates/metadata'
        vpn_uri = urlparse(config.get('OpenMotics', 'vpn_check_url'))
        uri = urlunparse((vpn_uri.scheme, vpn_uri.netloc, path, '', '', ''))
    path = '{}/{}'.format(uri.path, version)
    query = 'uuid={0}'.format(gateway_uuid)
    return urlunparse((uri.scheme, uri.netloc, path, '', query, ''))


def download_firmware(firmware_type, url, expected_sha256):
    response = requests.get(url, stream=True)
    firmware_file = FIRMWARE_FILES[firmware_type]
    logger.info('Downloading {}...'.format(firmware_file))
    with open(firmware_file, 'wb') as f:
        shutil.copyfileobj(response.raw, f)

    hasher = hashlib.sha256()
    with open(firmware_file, 'rb') as f:
        hasher.update(f.read())
    calculated_sha256 = hasher.hexdigest()
    if expected_sha256 != calculated_sha256:
        raise ValueError('firmware %s sha256:%s does not match expected sha256:%s' % (firmware_file, calculated_sha256, expected_sha256))


def check_services():
    for service in SUPERVISOR_SERVICES:
        status_output = subprocess.check_output(['supervisorctl', 'status', service])
        if 'no such process' in status_output.encode().lower():
            raise Exception('Could not find service "{}"'.format(service))


def stop_services():
    for service in SUPERVISOR_SERVICES:
        cmd(['supervisorctl', 'stop', service])


def start_services():
    for service in SUPERVISOR_SERVICES:
        try:
            cmd(['supervisorctl', 'start', service])
        except Exception:
            logger.warning('Starting {} failed'.format(service))


def check_gateway_health(timeout=60):
    since = time.time()
    pending = ['unknown']
    while since > time.time() - timeout:
        try:
            response = requests.get('http://127.0.0.1/health_check', timeout=2)
            data = response.json()
            if data['success']:
                pending = [k for k, v in data['health'].items() if not v['state']]
                if not pending:
                    return
        except Exception:
            pass
        time.sleep(10)
    logger.error('health check failed {}'.format(pending))
    raise Exception('Gateway services failed to start')


def check_master_communication():
    master_tool = os.path.join(PREFIX, 'python/master_tool.py')
    cmd(['python', master_tool, '--reset'])
    try:
        cmd(['python', master_tool, '--sync'])
    except Exception:
        time.sleep(2)
        try:
            cmd(['python', master_tool, '--sync'])
        except Exception:
            logger.info('No communication, resetting master')
            cmd(['python', master_tool, '--hard-reset'])
            time.sleep(2)
            try:
                cmd(['python', master_tool, '--sync'])
            except Exception:
                time.sleep(2)
    finally:
        cmd(['python', master_tool, '--sync'])


def update_master_firmware(hexfile, firmware):
    master_tool = os.path.join(PREFIX, 'python/master_tool.py')
    try:
        output = subprocess.check_output(['python', master_tool, '--version'])
        from_master_version, _, _ = output.decode().rstrip().partition(' ')
        master_version = next((x['version'] for x in firmware if x['type'] == 'master_classic'), None)
        if from_master_version == master_version:
            logger.info('Master is already {}, skipped'.format(master_version))
        else:
            logger.info('master {} -> {}'.format(from_master_version, master_version))
            cmd(['python', master_tool, '--update', '--master-firmware-classic', hexfile])
            cmd(['cp', hexfile, os.path.join(PREFIX, 'firmware.hex')])
    except Exception as exc:
        logger.error('Updating Master firmware failed')
        return exc

def update_power_firmware(hexfile):
    check_master_communication()
    power_bootloader = os.path.join(PREFIX, 'python/power_bootloader.py')
    try:
        # TODO: check versions
        cmd(['python', power_bootloader, '--all', '--8', '--file', hexfile])
        cmd(['cp', hexfile, os.path.join(PREFIX, os.path.basename(hexfile))])
    except Exception as exc:
        logger.error('Updating Power firmware failed')
        return exc


def update_energy_firmware(hexfile):
    check_master_communication()
    power_bootloader = os.path.join(PREFIX, 'python/power_bootloader.py')
    try:
        # TODO: check versions
        cmd(['python', power_bootloader, '--all', '--file', hexfile])
        cmd(['cp', hexfile, os.path.join(PREFIX, os.path.basename(hexfile))])
    except Exception as exc:
        logger.error('Updating Energy firmware failed')
        return exc


def update_module_firmware(hexfile, module):
    check_master_communication()
    modules_bootloader = os.path.join(PREFIX, 'python/modules_bootloader.py')
    try:
        # TODO: check versions
        cmd(['python', modules_bootloader, '-t', MODULE_TYPES[module], '-f', hexfile])
        cmd(['cp', hexfile, os.path.join(PREFIX, os.path.basename(hexfile))])
    except Exception as exc:
        logger.error('Updating {} firmware failed'.format(module))
        return exc


def update_gateway_os(tarball):
    try:
        cmd(['mount', '-o', 'remount,rw', '/'])
        cmd(['tar', '-xz', '--no-same-owner', '-f', tarball, '-C', '/'])
        cmd(['sync'])
        cmd(['bash', '/usr/bin/os_update.sh'])
    except Exception as exc:
        logger.error('Updating Gateway OS failed')
        return exc
    finally:
        cmd(['mount', '-o', 'remount,ro', '/'])


def update_gateway_backend(tarball, date):
    try:
        backup_dir = os.path.join(PREFIX, 'backup')
        python_dir = os.path.join(PREFIX, 'python')
        etc_dir = os.path.join(PREFIX, 'etc')
        cmd(['mkdir', '-p', backup_dir])
        cmd('ls -tp | grep "/$" | tail -n +3 | while read file; do rm -r $file; done', shell=True, cwd=backup_dir)

        # TODO: symlink, blue green deployment
        cmd(['mkdir', '-p', os.path.join(backup_dir, date)])
        cmd(['mv', python_dir, os.path.join(backup_dir, date)])
        cmd(['cp', '-r', etc_dir, os.path.join(backup_dir, date)])

        # Cleanup for old versions.
        old_dist_dir = os.path.join(PREFIX, 'dist-packages')
        if os.path.exists(old_dist_dir):
            cmd(['mv', old_dist_dir, os.path.join(backup_dir, date)])

        logger.info('Extracting gateway')
        cmd(['mkdir', '-p', python_dir])
        cmd(['tar', '-v', '-xzf', tarball, '-C', python_dir])
        cmd(['sync'])

        plugins = glob.glob('{}/{}/python/plugins/*/'.format(backup_dir, date))
        if plugins:
            logger.info('Restoring plugins')
            for plugin in plugins:
                cmd(['mv', '-v', plugin, os.path.join(python_dir, 'plugins')])

        logger.info('Running post-update')
        cmd(['bash', os.path.join(python_dir, 'post-update.sh')])
        cmd(['sync'])
    except Exception as exc:
        logger.error('Updating Gateway service failed')
        return exc


def update_gateway_frontend(tarball, date):
    try:
        backup_dir = os.path.join(PREFIX, 'backup')
        static_dir = os.path.join(PREFIX, 'static')
        cmd(['mkdir', '-p', backup_dir])
        cmd('ls -tp | grep "/$" | tail -n +3 | while read file; do rm -r $file; done', shell=True, cwd=backup_dir)

        # TODO: symlink, A-B deployment
        cmd(['mkdir', '-p', os.path.join(backup_dir, date)])
        cmd(['mv', static_dir, os.path.join(backup_dir, date)])

        logger.info('Extracting gateway')
        cmd(['mkdir', '-p', static_dir])
        cmd(['tar', '-v', '-xzf', tarball, '-C', static_dir])
        cmd(['sync'])
    except Exception as exc:
        logger.error('Updating Gateway service failed')
        return exc


def update(version, expected_md5):
    """
    Execute the actual update: extract the archive and execute the bash update script.

    :param version: the new version (after the update).
    :param md5_server: the md5 sum provided by the server.
    """
    try:
        config = ConfigParser()
        config.read(constants.get_config_file())
        from_version = config.get('OpenMotics', 'version')
        logger.info('==================================')
        logger.info('Starting update {} -> {}'.format(from_version, version))

        update_file = constants.get_update_file()
        update_dir = os.path.dirname(update_file)
        # Change to update directory.
        os.chdir(update_dir)

        meta = {}

        if os.path.exists(update_file):
            logger.info(' -> Extracting update.tgz')
            extract_legacy_update(update_file, expected_md5)
        else:
            logger.info(' -> Fetching metadata')
            meta = fetch_metadata(config, version, expected_md5)
            logger.info(' -> Downloading firmware for update {}'.format(meta['version']))
            for data in meta['firmwares']:
                download_firmware(data['type'], data['url'], data['sha256'])
    except Exception:
        logger.exception('failed to preprepare update')
        raise SystemExit(1)

    try:
        errors = []
        date = datetime.now().strftime('%Y%m%d%H%M%S')

        # TODO: should update and re-execute itself before proceeding?

        logger.info(' -> Checking services')
        check_services()

        logger.info(' -> Stopping services')
        stop_services()

        gateway_os = FIRMWARE_FILES['gateway_os']
        if os.path.exists(gateway_os):
            logger.info(' -> Updating Gateway OS')
            error = update_gateway_os(gateway_os)
            if error:
                errors.append(error)

        gateway_service = FIRMWARE_FILES['gateway_service']
        if os.path.exists(gateway_service):
            logger.info(' -> Updating Gateway service')
            error = update_gateway_backend(gateway_service, date)
            if error:
                errors.append(error)

        master_firmware = FIRMWARE_FILES['master_classic']
        if os.path.exists(master_firmware):
            logger.info(' -> Updating Master firmware')
            error = update_master_firmware(master_firmware, meta.get('firmware', []))
            if error:
                errors.append(error)

        power_firmware = FIRMWARE_FILES['power']
        if os.path.exists(power_firmware):
            logger.info(' -> Updating Power firmware')
            error = update_power_firmware(power_firmware)
            if error:
                errors.append(error)

        energy_firmware = FIRMWARE_FILES['energy']
        if os.path.exists(energy_firmware):
            logger.info(' -> Updating Energy firmware')
            error = update_energy_firmware(energy_firmware)
            if error:
                errors.append(error)

        for module in MODULE_TYPES:
            module_firmware = FIRMWARE_FILES[module]
            if os.path.exists(module_firmware):
                logger.info(' -> Updating {} firmware'.format(module))
                error = update_module_firmware(module_firmware, module)
                if error:
                    errors.append(error)

        logger.info('Checking master communication')
        check_master_communication()

        gateway_frontend = FIRMWARE_FILES['gateway_frontend']
        if os.path.exists(gateway_frontend):
            logger.info(' -> Updating Gateway frontend')
            error = update_gateway_frontend(gateway_frontend, date)
            if error:
                errors.append(error)

        logger.info(' -> Starting services')
        start_services()

        logger.info(' -> Waiting for health check')
        check_gateway_health()

    except Exception as exc:
        errors.append(exc)
        # TODO: rollback
    finally:
        logger.info(' -> Starting services')
        start_services()

        logger.info(' -> Running cleanup')
        cmd('rm -v -rf {}/*'.format(update_dir), shell=True)

        if errors:
            for error in errors:
                logger.error(error)
            raise SystemExit(1)

        config.set('OpenMotics', 'version', version)
        with open(constants.get_config_file(), 'wb') as configfile:
            config.write(configfile)

        if os.path.exists('/tmp/post_update_reboot'):
            logger.info('Scheduling reboot in 5 minutes')
            subprocess.Popen('sleep 300 && reboot', shell=True)

        logger.info('DONE')
        logger.info('exit 0')


def main():
    """ The main function. """
    if len(sys.argv) != 3:
        print('Usage: python ' + __file__ + ' version md5sum')
        sys.exit(1)

    (version, expected_md5) = (sys.argv[1], sys.argv[2])

    # Start with version line, this is expected by the cloud.
    logger.info(version)

    lockfile = constants.get_update_lockfile()
    with open(lockfile, 'wc') as wfd:
        try:
            fcntl.flock(wfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            logger.exception('failed to aquire update lock')
            logger.error('FAILED')
            logger.error('exit 2')
            raise SystemExit(2)
        try:
            update(version, expected_md5)
        except SystemExit:
            logger.error('FAILED')
            logger.error('exit 1')
        finally:
            fcntl.flock(wfd, fcntl.LOCK_UN)
            os.unlink(lockfile)



if __name__ == '__main__':
    main()
