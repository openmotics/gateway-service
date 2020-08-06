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

from constants import get_config_file, get_update_file, get_update_output_file

logger = logging.getLogger('update.py')
logging.basicConfig(filename=get_update_output_file(), level=logging.DEBUG)


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


def md5(filename):
    """
    Generate the md5 sum of a file.

    :param filename: the name of the file to hash.
    :returns: md5sum
    """
    md5_hash = hashlib.md5()
    with open(filename, 'rb') as file_to_hash:
        for chunk in iter(lambda: file_to_hash.read(128 * md5_hash.block_size), ''):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def update(version, md5_server):
    """
    Execute the actual update: extract the archive and execute the bash update script.

    :param version: the new version (after the update).
    :param md5_server: the md5 sum provided by the server.
    """
    config = ConfigParser()
    config.read(get_config_file())
    gateway_uuid = config.get('OpenMotics', 'uuid')
    from_version = config.get('OpenMotics', 'version')
    logger.info('Update {} -> {}'.format(from_version, version))
    logger.info('=========================')

    try:
        update_url = config.get('OpenMotics', 'update_url')
    except NoOptionError:
        path = '/portal/update_metadata/'
        vpn_uri = urlparse(config.get('OpenMotics', 'vpn_check_url'))
        update_url = urlunparse((vpn_uri.scheme, vpn_uri.netloc, path, '', '', ''))

    update_file = get_update_file()
    update_dir = os.path.dirname(update_file)
    os.chdir(update_dir)

    meta = {}

    if os.path.exists(update_file):
        md5_client = md5(update_file)
        if md5_server != md5_client:
            raise Exception('MD5 of client (' + str(md5_client) + ') and server (' + str(md5_server) + ') don\'t match')

        logger.info(' -> Extracting update.tgz')
        cmd(['tar', 'xzf', update_file])
    else:
        uri = urlparse(update_url)
        path = '{}/{}'.format(uri.path, version)
        query = 'uuid={0}'.format(gateway_uuid)
        logger.info('Fetching metadata')
        response = requests.get(urlunparse((uri.scheme, uri.netloc, path, '', query, '')))
        if response.status_code != 200:
            raise ValueError('failed to get update metadata')
        hasher = hashlib.md5()
        hasher.update(response.content)
        calculated_md5 = hasher.hexdigest()
        if md5_server != calculated_md5:
            logger.error(response.content)
            raise ValueError('update metadata md5:%s does not match expected md5:%s' % (calculated_md5, md5_server))
        meta = response.json()
        logger.info('Update {}'.format(meta['version']))

        firmware_file_map = {'gateway_service': 'gateway.tgz',
                             'gateway_os': 'gateway_os.tgz',
                             'master_classic': 'm_classic_firmware.hex',
                             'can': 'c_firmware.hex'}
        for data in meta['firmware']:
            response = requests.get(data['url'], stream=True)
            firmware_file = os.path.join(update_dir, firmware_file_map[data['type']])
            logger.info('Downloading {}...'.format(firmware_file))
            with open(firmware_file, 'wb') as f:
                shutil.copyfileobj(response.raw, f)

            hasher = hashlib.sha256()
            with open(firmware_file, 'rb') as f:
                hasher.update(f.read())
            calculated_hash = hasher.hexdigest()
            if calculated_hash != data['sha256']:
                raise ValueError('firmware sha256:%s does not match' % calculated_hash)

    try:
        error = None
        date = datetime.now().strftime('%Y%m%d%H%M%S')

        # TODO: should update and re-execute itself before proceeding?

        logger.info(' -> Checking services')
        for service in ('openmotics', 'vpn_service'):
            status_output = subprocess.check_output(['supervisorctl', 'status', service])
            if 'no such process' in status_output.encode().lower():
                raise Exception('Could not find service "{}"'.format(service))

        logger.info(' -> Stopping services')
        for service in ('openmotics', 'vpn_service'):
            cmd(['supervisorctl', 'stop', service])

        gateway_os = os.path.join(update_dir, 'gateway_os.tgz')
        if os.path.exists(gateway_os):
            logger.info(' -> Updating Gateway OS')
            try:
                cmd(['mount', '-o', 'remount,rw', '/'])
                cmd(['tar', '-xz', '--no-same-owner', '-f', gateway_os, '-C', '/'])
                cmd(['sync'])
                cmd(['bash', '/usr/bin/os_update.sh'])
            except Exception as exc:
                logger.error('Updating Gateway OS failed')
                error = exc
            finally:
                cmd(['mount', '-o', 'remount,ro', '/'])

        gateway_service = os.path.join(update_dir, 'gateway.tgz')
        if os.path.exists(gateway_service):
            logger.info(' -> Updating Gateway service')
            try:
                backup_dir = '/opt/openmotics/backup'
                python_dir = '/opt/openmotics/python'
                cmd(['mkdir', '-p', backup_dir])
                cmd('ls -tp | grep "/$" | tail -n +3 | while read file; do rm -r $file; done', shell=True, cwd=backup_dir)

                # TODO: symlink, blue green deployment
                cmd(['mkdir', '-p', os.path.join(backup_dir, date)])
                cmd(['mv', python_dir, os.path.join(backup_dir, date)])

                # Cleanup for old versions.
                old_dist_dir = '/opt/openmotics/dist-packages'
                if os.path.exists(old_dist_dir):
                    cmd(['mv', old_dist_dir, os.path.join(backup_dir, date)])

                logger.info('Extracting gateway')
                cmd(['mkdir', '-p', python_dir])
                cmd(['tar', '-v', '-xzf', gateway_service, '-C', python_dir])
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
                error = exc

        master_firmware = os.path.join(update_dir, 'm_classic_firmware.hex')
        if os.path.exists(master_firmware):
            try:
                logger.info(' -> Updating Master firmware')
                output = subprocess.check_output(['python', '/opt/openmotics/python/master_tool.py', '--version'])
                from_master_version, _, _ = output.decode().rstrip().partition(' ')
                master_version = next((x['version'] for x in meta.get('firmware', []) if x['type'] == 'master_classic'), None)
                if from_master_version == master_version:
                    logger.info('Master is already {}, skipped'.format(master_version))
                else:
                    logger.info('master {} -> {}'.format(from_master_version, master_version))
                    cmd(['python', '/opt/openmotics/python/master_tool.py', '--update', '--master-firmware-classic', master_firmware])
                    cmd(['cp', master_firmware, '/opt/openmotics/firmware.hex'])
            except Exception as exc:
                logger.error('Updating Master firmware failed')
                error = exc

        can_firmware = os.path.join(update_dir, 'c_firmware.hex')
        if os.path.exists(can_firmware):
            logger.info('Checking master communication')
            cmd(['python', '/opt/openmotics/python/master_tool.py', '--reset'])

            try:
                cmd(['python', '/opt/openmotics/python/master_tool.py', '--sync'])
            except Exception:
                time.sleep(2)
                try:
                    cmd(['python', '/opt/openmotics/python/master_tool.py', '--sync'])
                except Exception:
                    logger.info('No communication, resetting master')
                    cmd(['python', '/opt/openmotics/python/master_tool.py', '--hard-reset'])
                    time.sleep(2)
                    try:
                        cmd(['python', '/opt/openmotics/python/master_tool.py', '--sync'])
                    except Exception:
                        time.sleep(2)
            finally:
                cmd(['python', '/opt/openmotics/python/master_tool.py', '--sync'])

            logger.info(' -> Updating CAN firmware')
            try:
                # TODO: check versions
                cmd(['python', '/opt/openmotics/python/modules_bootloader.py', '-t', 'c' '-f', can_firmware])
                cmd(['cp', can_firmware, '/opt/openmotics/c_firmware.hex'])
            except Exception as exc:
                logger.error('Updating CAN firmware failed')
                error = exc

        logger.info('Checking master communication')
        cmd(['python', '/opt/openmotics/python/master_tool.py', '--reset'])

        try:
            cmd(['python', '/opt/openmotics/python/master_tool.py', '--sync'])
        except Exception:
            time.sleep(2)
            try:
                cmd(['python', '/opt/openmotics/python/master_tool.py', '--sync'])
            except Exception:
                logger.info('No communication, resetting master')
                cmd(['python', '/opt/openmotics/python/master_tool.py', '--hard-reset'])
                time.sleep(2)
                try:
                    cmd(['python', '/opt/openmotics/python/master_tool.py', '--sync'])
                except Exception:
                    time.sleep(2)
        finally:
            cmd(['python', '/opt/openmotics/python/master_tool.py', '--sync'])

        gateway_frontend = os.path.join(update_dir, 'gateway_frontend.tgz')
        if os.path.exists(gateway_frontend):
            logger.info(' -> Updating Gateway frontend')
            try:
                backup_dir = '/opt/openmotics/backup'
                static_dir = '/opt/openmotics/static'
                cmd(['mkdir', '-p', backup_dir])
                cmd('ls -tp | grep "/$" | tail -n +3 | while read file; do rm -r $file; done', shell=True, cwd=backup_dir)

                # TODO: symlink, A-B deployment
                cmd(['mkdir', '-p', os.path.join(backup_dir, date)])
                cmd(['mv', static_dir, os.path.join(backup_dir, date)])

                logger.info('Extracting gateway')
                cmd(['mkdir', '-p', static_dir])
                cmd(['tar', '-v', '-xzf', gateway_frontend, '-C', static_dir])
                cmd(['sync'])
            except Exception as exc:
                logger.error('Updating Gateway service failed')
                error = exc

    except Exception as exc:
        error = exc
        # TODO: rollback
    finally:
        logger.info(' -> Starting services')
        for service in ('openmotics', 'vpn_service'):
            try:
                cmd(['supervisorctl', 'start', service])
            except Exception:
                logger.warning('Starting {} failed'.format(service))

        logger.info(' -> Starting cleanup')
        cmd('rm -v -rf {}/*'.format(update_dir), shell=True)

        config.set('OpenMotics', 'version', version)
        temp_file = get_config_file() + '.update'
        with open(temp_file, 'wb') as configfile:
            config.write(configfile)
        shutil.move(temp_file, get_config_file())
        subprocess.check_call(['sync'])

        if error:
            logger.error('FAILED')
            logger.error('exit 1')
            raise SystemExit(1)

        if os.path.exists('/tmp/post_update_reboot'):
            logger.info('Scheduling reboot in 5 minutes')
            subprocess.Popen('sleep 300 && reboot', shell=True)

        logger.info('SUCCESS')
        logger.info('exit 0')


def main():
    """ The main function. """
    if len(sys.argv) != 3:
        print('Usage: python ' + __file__ + ' version md5sum')
        sys.exit(1)

    (version, md5_sum) = (sys.argv[1], sys.argv[2])
    update(version, md5_sum)


if __name__ == '__main__':
    main()
