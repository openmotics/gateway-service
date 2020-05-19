# Copyright (C) 2020 OpenMotics BV
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

from __future__ import absolute_import

from platform_utils import Platform, System
System.import_libs()

import fcntl
import logging
import os
import time
from contextlib import contextmanager
from threading import Lock

from peewee_migrate import Router
from serial import Serial
from six.moves.configparser import ConfigParser
from six.moves.urllib.parse import urlparse

import constants
from bus.om_bus_client import MessageClient
from gateway.models import Database, Feature
from ioc import INJECTED, Inject, Injectable
from serial_utils import RS485

if False:  # MYPY
    from typing import Any
    from gateway.hal.master_controller import MasterController

logger = logging.getLogger('openmotics')


def initialize():
    # type: () -> None
    logger.info('Initializing')
    init_lock = constants.get_init_lockfile()
    logger.info('Waiting for lock')
    with lock_file(init_lock) as fd:
        content = fd.read()
        apply_migrations()
        setup_platform()
        if content == '':
            logger.info('Initializing, done')
        elif content == 'factory_reset':
            logger.info('Running factory reset...')
            factory_reset()
            logger.info('Running factory reset, done')
        else:
            logger.warning('unknown initialization {}'.format(content))


@contextmanager
def lock_file(file):
    # type: (str) -> Any
    with open(file, 'a') as wfd:
        fcntl.flock(wfd, fcntl.LOCK_EX)
        try:
            with open(file, 'r') as rfd:
                yield rfd
            os.unlink(file)
        except Exception:
            fcntl.flock(wfd, fcntl.LOCK_UN)
            raise


def apply_migrations():
    # type: () -> None
    logger.info('Applying migrations')
    # Run all unapplied migrations
    db = Database.get_db()
    router = Router(db, migrate_dir='/opt/openmotics/python/gateway/migrations/orm')
    router.run()


@Inject
def factory_reset(master_controller=INJECTED):
    # type: (MasterController) -> None
    import glob
    import shutil

    logger.info('Rebooting master...')
    master_controller.cold_reset()
    time.sleep(5)

    logger.info('Wiping master eeprom...')
    master_controller.start()
    master_controller.factory_reset()
    master_controller.stop()

    logger.info('Removing databases...')
    # Delete databases.
    for f in constants.get_all_database_files():
        if os.path.exists(f):
            os.remove(f)

    # Delete plugins
    logger.info('Removing plugins...')
    plugin_dir = constants.get_plugin_dir()
    plugins = [name for name in os.listdir(plugin_dir)
               if os.path.isdir(os.path.join(plugin_dir, name))]
    for plugin in plugins:
        shutil.rmtree(plugin_dir + plugin)

    config_files = constants.get_plugin_configfiles()
    for config_file in glob.glob(config_files):
        os.remove(config_file)


def setup_platform():
    # type: () -> None
    setup_target_platform(Platform.get_platform())


def setup_target_platform(target_platform):
    # type: (str) -> None
    config = ConfigParser()
    config.read(constants.get_config_file())

    config_lock = Lock()
    scheduling_lock = Lock()
    metrics_lock = Lock()

    config_database_file = constants.get_config_database_file()

    # TODO: Clean up dependencies more to reduce complexity

    # IOC announcements
    # When below modules are imported, the classes are registerd in the IOC graph. This is required for
    # instances that are used in @Inject decorated functions below, and is also needed to specify
    # abstract implementations depending on e.g. the platform (classic vs core) or certain settings (classic
    # thermostats vs gateway thermostats)
    from power import power_communicator, power_controller
    from plugins import base
    from gateway import (metrics_controller, webservice, scheduling, observer, gateway_api, metrics_collector,
                         maintenance_controller, comm_led_controller, users, pulse_counter_controller, config as config_controller,
                         metrics_caching, watchdog, output_controller, room_controller, sensor_controller,
                         group_action_controller)
    from cloud import events
    _ = (metrics_controller, webservice, scheduling, observer, gateway_api, metrics_collector,
         maintenance_controller, base, events, power_communicator, comm_led_controller, users,
         power_controller, pulse_counter_controller, config_controller, metrics_caching, watchdog, output_controller,
         room_controller, sensor_controller, group_action_controller)
    if target_platform == Platform.Type.CORE_PLUS:
        from gateway.hal import master_controller_core, frontpanel_controller_core
        from master.core import maintenance, core_communicator, ucan_communicator
        from master.classic import eeprom_extension
        _ = master_controller_core, maintenance, core_communicator, ucan_communicator, frontpanel_controller_core
    else:
        from gateway.hal import master_controller_classic, frontpanel_controller_classic
        from master.classic import maintenance, master_communicator, eeprom_extension  # type: ignore
        _ = master_controller_classic, maintenance, master_communicator, eeprom_extension, frontpanel_controller_classic

    thermostats_gateway_feature = Feature.get_or_none(name='thermostats_gateway')
    thermostats_gateway_enabled = thermostats_gateway_feature is not None and thermostats_gateway_feature.enabled
    if target_platform == Platform.Type.CORE_PLUS or thermostats_gateway_enabled:
        from gateway.thermostat.gateway import thermostat_controller_gateway
        _ = thermostat_controller_gateway
    else:
        from gateway.thermostat.master import thermostat_controller_master
        _ = thermostat_controller_master

    # Hardware
    if Platform.get_platform() == Platform.Type.CLASSIC:
        Injectable.value(leds_i2c_address=int(config.get('OpenMotics', 'leds_i2c_address'), 16))

    # IPC
    Injectable.value(message_client=MessageClient('openmotics_service'))

    # Cloud API
    parsed_url = urlparse(config.get('OpenMotics', 'vpn_check_url'))
    Injectable.value(gateway_uuid=config.get('OpenMotics', 'uuid'))
    Injectable.value(cloud_endpoint=parsed_url.hostname)
    Injectable.value(cloud_port=parsed_url.port)
    Injectable.value(cloud_ssl=parsed_url.scheme == 'https')
    Injectable.value(cloud_api_version=0)

    # User Controller
    Injectable.value(user_db=config_database_file)
    Injectable.value(user_db_lock=config_lock)
    Injectable.value(token_timeout=3600)
    Injectable.value(config={'username': config.get('OpenMotics', 'cloud_user'),
                             'password': config.get('OpenMotics', 'cloud_pass')})

    # Configuration Controller
    Injectable.value(config_db=config_database_file)
    Injectable.value(config_db_lock=config_lock)

    # Energy Controller
    power_serial_port = config.get('OpenMotics', 'power_serial')
    Injectable.value(power_db=constants.get_power_database_file())
    if power_serial_port:
        # TODO: make non blocking?
        Injectable.value(power_serial=RS485(Serial(power_serial_port, 115200, timeout=None)))
    else:
        Injectable.value(power_serial=None)
        Injectable.value(power_communicator=None)
        Injectable.value(power_controller=None)

    # Pulse Controller
    Injectable.value(pulse_db=constants.get_pulse_counter_database_file())

    # Scheduling Controller
    Injectable.value(scheduling_db=constants.get_scheduling_database_file())
    Injectable.value(scheduling_db_lock=scheduling_lock)

    # Master Controller
    controller_serial_port = config.get('OpenMotics', 'controller_serial')
    Injectable.value(controller_serial=Serial(controller_serial_port, 115200))
    if target_platform == Platform.Type.CORE_PLUS:
        from master.core.memory_file import MemoryFile, MemoryTypes
        core_cli_serial_port = config.get('OpenMotics', 'cli_serial')
        Injectable.value(cli_serial=Serial(core_cli_serial_port, 115200))
        Injectable.value(passthrough_service=None)  # Mark as "not needed"
        Injectable.value(memory_files={MemoryTypes.EEPROM: MemoryFile(MemoryTypes.EEPROM),
                                       MemoryTypes.FRAM: MemoryFile(MemoryTypes.FRAM)})
        # TODO: Remove; should not be needed for Core
        Injectable.value(eeprom_db=constants.get_eeprom_extension_database_file())
    else:
        passthrough_serial_port = config.get('OpenMotics', 'passthrough_serial')
        Injectable.value(eeprom_db=constants.get_eeprom_extension_database_file())
        if passthrough_serial_port:
            Injectable.value(passthrough_serial=Serial(passthrough_serial_port, 115200))
            from master.classic.passthrough import PassthroughService
            _ = PassthroughService  # IOC announcement
        else:
            Injectable.value(passthrough_service=None)

    # Metrics Controller
    Injectable.value(metrics_db=constants.get_metrics_database_file())
    Injectable.value(metrics_db_lock=metrics_lock)

    # Webserver / Presentation layer
    Injectable.value(ssl_private_key=constants.get_ssl_private_key_file())
    Injectable.value(ssl_certificate=constants.get_ssl_certificate_file())
