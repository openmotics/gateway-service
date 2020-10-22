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


OPENMOTICS_PREFIX = os.environ.get('OPENMOTICS_PREFIX', os.path.abspath(os.path.join(__file__, '../..')))


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


def get_static_dir():
    """ Get the directory where the static frontend assets are stored. """
    return os.path.join(OPENMOTICS_PREFIX, 'static')


def get_terms_dir():
    """ Get the directory where plugin data is stored. """
    python_root = os.path.abspath(os.path.join(__file__, '..'))
    return os.path.join(python_root, 'terms')


def get_plugin_dir():
    """ Get the directory where plugin data is stored. """
    python_root = os.path.abspath(os.path.join(__file__, '..'))
    return os.path.join(python_root, 'plugins/')


def get_update_cmd(version, md5):
    """ Get the command to execute an update. Returns an array of arguments (string). """
    python_root = os.path.abspath(os.path.join(__file__, '..'))
    return ["/usr/bin/python", os.path.join(python_root, 'update.py'), str(version), str(md5)]


def get_update_log_location():
    """ Gets the update logfile location """
    return '/var/log/openmotics_update.log'


def get_init_lockfile():
    # type: () -> str
    """ Returns the lock file used by openmotics_init.py """
    return '/tmp/openmotics_init.lock'


def get_update_lockfile():
    # type: () -> str
    """ Returns the lock file used by update.py """
    return '/tmp/openmotics_update.lock'
