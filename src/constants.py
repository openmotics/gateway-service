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
""""
The constants modules contains static definitions for filenames.

@author: fryckbos
"""
import os
import platform_utils
import sys

PYINSTALLER_PREFIX = os.environ.get('PYINSTALLER_PREFIX', None)
OPENMOTICS_PREFIX = os.environ.get('OPENMOTICS_PREFIX', os.path.abspath(os.path.join(__file__, '../..')))


def get_openmotics_prefix():
    """ Returns the openmotics prefix, this can be useful to be mocked in unit-tests """
    return OPENMOTICS_PREFIX


def get_src_root_full_path():
    """ Returns the top level directory of the python src code """
    return os.path.abspath(os.path.join(__file__, '..'))


def get_config_file():
    """ Get the filename of the OpenMotics config file. This file is in ini format. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/openmotics.conf')


def get_config_database_file():
    """ Get the filename of the config database file. This file is in sqlite format. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/config.db')


def get_power_database_file():
    """ Get the filename of the power database file. This file is in sqlite format. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/power.db')


def get_scheduling_database_file():
    """ Get the filename of the scheduling database file. This file is in sqlite format. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/sched.db')


def get_gateway_database_file():
    """ Get the filename of the gateway database file. This file is in sqlite format. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/gateway.db')


def get_thermostats_scheduler_database_file():
    """ Get the filename of the gateway database file. This file is in sqlite format. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/thermostat-scheduler.db')


def get_eeprom_extension_database_file():
    """ Get the filename of the EEPROM extension database file. This file is in sqlite format. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/eeprom_ext.db')


def get_metrics_database_file():
    """ Get the filename of the metrics database file. This file is in sqlite format. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/metrics.db')


def get_pulse_counter_database_file():
    """ Get the filename of the pulse counter database file. This file is in sqlite format. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/pulse.db')


def get_all_database_files():
    return [
        get_config_database_file(),
        get_power_database_file(),
        get_scheduling_database_file(),
        get_gateway_database_file(),
        get_thermostats_scheduler_database_file(),
        get_eeprom_extension_database_file(),
        get_metrics_database_file(),
        get_pulse_counter_database_file(),
    ]


def get_ssl_certificate_file():
    """ Get the filename of the ssl certificate. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/https.crt')


def get_ssl_private_key_file():
    """ Get the filename of the ssl private key. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/https.key')


def get_update_dir():
    """ Get the directory to store the temporary update data. """
    return os.path.join(OPENMOTICS_PREFIX, 'update/')


def get_update_file():
    """ Get the filename of the tgz file that contains the update script and data. """
    return os.path.join(OPENMOTICS_PREFIX, 'update/update.tgz')


def get_update_output_file():
    """ Get the filename for the output of the update command. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/last_update.out')


def get_timezone_file():
    """ Get the path of the timezone file. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/timezone')


def get_plugin_config_dir():
    """ Get the directory where plugin data is stored. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/')


def get_plugin_configfiles():
    """ Get the directory where plugin data is stored. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/pi_*')


def get_hex_files():
    """ Get the firmware hex files. """
    return os.path.join(OPENMOTICS_PREFIX, '*.hex')


def get_config_dir():
    """ Get the directory general configuration is stored. """
    return os.path.join(OPENMOTICS_PREFIX, 'etc/')


def get_static_dir():
    """ Get the directory where the static frontend assets are stored. """
    return os.path.join(OPENMOTICS_PREFIX, 'static')


def get_terms_dir():
    """ Get the directory where plugin data is stored. """
    python_root = os.path.abspath(os.path.join(__file__, '..'))
    return os.path.join(python_root, 'terms')


def get_plugin_dir():
    """ Get the directory where plugin data is stored. """
    curr_os = platform_utils.System.get_operating_system()
    if curr_os.get('ID') != platform_utils.System.OS.BUILDROOT:
        python_root = os.path.abspath(os.path.join(__file__, '..'))
        return os.path.join(python_root, 'plugins/')
    else:
        path = os.path.join(OPENMOTICS_PREFIX, 'plugins/')
        return path


def get_plugin_runtime_dir():
    """ Get the directory where plugin data is stored. """
    python_root = os.path.abspath(os.path.join(__file__, '..'))
    return os.path.join(python_root, 'plugin_runtime')


def get_update_cmd(version, md5):
    """ Get the command to execute an update. Returns an array of arguments (string). """
    python_root = os.path.abspath(os.path.join(__file__, '..'))
    python_executable = sys.executable
    if python_executable is None or len(python_executable) == 0:
        python_executable = '/usr/bin/python'
    system_os = platform_utils.System.get_operating_system().get('ID')
    if system_os == platform_utils.System.OS.BUILDROOT:
        extended_path = False
    else:
        extended_path = True
    path = os.path.join(python_root, 'openmotics_update.py') if extended_path else 'openmotics_update.py'
    return [python_executable, path, str(version), str(md5)]


def get_update_log_location():
    """ Gets the update logfile location """
    return '/var/log/openmotics_update.log'


def get_init_lockfile():
    # type: () -> str
    """ Returns the lock file used by openmotics_init.py """
    return '/tmp/openmotics_init.lock'


def get_update_lockfile():
    # type: () -> str
    """ Returns the lock file used by openmotics_update.py """
    return '/tmp/openmotics_update.lock'

def get_runit_service_folder():
    # type: () -> str
    """ Returns the location of the runit services definitions """
    if PYINSTALLER_PREFIX is not None:
        return os.path.join(PYINSTALLER_PREFIX, 'om-services')
    else:
        raise ValueError('"PYINSTALLER_PREFIX" environment variable is not set, cannot retrieve the runit service folder')

def get_renson_main_config_file():
    # type: () -> str
    return '/data/app_data/main.config'

def get_esafe_touchscreen_calibration_file():
    # type: () -> str
    return '/etc/pointercal'

def get_email_verification_regex():
    # type: () -> str
    """ Returns the official RFC 5322 email regex """
    return r"(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|" \
           r"\"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*\")" \
           r"@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|" \
           r"\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|" \
           r"[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"