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
from platform_utils import System
System.import_libs()

import argparse
import logging
import os
import sys
import time

import constants
import gateway
from ioc import INJECTED, Inject
from logs import Logs

logger = logging.getLogger('openmotics')


def cmd_feature_thermostats(args):
    from gateway.models import Database, DataMigration, Feature
    if args.enable and args.disable:
        logger.error('--enable and --disable are mutually exclusive')

    with Database.get_session() as db:
        feature = db.query(Feature).filter_by(name='thermostats_gateway').one_or_none()
        if feature is None:
            feature = Feature(name='thermostats_gateway')
        if args.enable or args.disable:
            logger.info('Updating feature thermostats_gateway')
            feature.enabled = args.enable and not args.disable
        migration = None
        if args.migrate:
            logger.info('Updating data migration for thermostats')
            migration = db.query(DataMigration).filter_by(name='thermostats').one_or_none()
            if migration:
                migration.migrated = False
        db.commit()


        logger.info('')
        logger.info('    feature:   thermostats_gateway enabled=%s', feature.enabled)
        logger.info('    migration: thermostats migrated=%s', migration and migration.migrated)
        logger.info('')


def cmd_factory_reset(args):
    lock_file = constants.get_init_lockfile()
    if os.path.isfile(lock_file) and not args.force:
        print('already_in_progress')
        exit(1)
    with open(lock_file, 'w') as fd:
        if args.can:
            fd.write('factory_reset_full')
        else: fd.write('factory_reset')


def cmd_shell(args):
    import IPython
    from gateway.initialize import setup_platform
    setup_platform(None)

    @Inject
    def f(cloud_api_client=INJECTED,
          event_sender=INJECTED,
          group_action_controller=INJECTED,
          input_controller=INJECTED,
          maintenance_controller=INJECTED,
          master_controller=INJECTED,
          message_client=INJECTED,
          metrics_cache_controller=INJECTED,
          metrics_controller=INJECTED,
          module_controller=INJECTED,
          output_controller=INJECTED,
          valve_pump_controller=INJECTED,
          plugin_controller=INJECTED,
          energy_module_controller=INJECTED,
          pubsub=INJECTED,
          pulse_counter_controller=INJECTED,
          room_controller=INJECTED,
          scheduling_controller=INJECTED,
          sensor_controller=INJECTED,
          shutter_controller=INJECTED,
          thermostat_controller=INJECTED,
          user_controller=INJECTED,
          ventilation_controller=INJECTED,
          watchdog=INJECTED,
          web_interface=INJECTED,
          web_service=INJECTED):
        # Imports for convenience
        from gateway.events import GatewayEvent
        from gateway.hal.master_event import MasterEvent
        from gateway.pubsub import PubSub
        from platform_utils import Platform
        if Platform.get_platform() in Platform.CoreTypes:
            @Inject
            def _load(ucan_communicator=INJECTED):
                return ucan_communicator
            ucan_communicator = _load()

        IPython.embed(header='''
        Interact with injected controllers using eg. master_controller

            In[1]: master_controller.start()
            In[2]: master_controller.get_status()
            Out[3]:
            {'date': '00/00/0',
             'hw_version': 4,
             'mode': 76,
             'time': '12:55',
             'version': '3.143.103'}
        ''')
    f()


def cmd_top(args):
    from gateway.initialize import setup_platform
    _ = setup_platform

    import psutil
    while True:
        proc = psutil.Process(args.pid)
        total_percent = proc.cpu_percent(10)
        total_time = sum(proc.cpu_times())
        stats = []
        for t in proc.threads():
            thr = psutil.Process(t.id)
            thread_percent = total_percent * ((t.system_time + t.user_time) / total_time)
            thread_user_percent = total_percent * (t.user_time / total_time)
            stats.append((thread_percent, thread_user_percent, t.id, thr.name()))
        logger.info('Threads')
        for thread_percent, thread_user_percent, thread_id, thread_name in sorted(stats, reverse=True):
            if thread_user_percent > 0.1:
                logger.info('{:.2f} {:.2f} {} {}'.format(thread_percent, thread_user_percent, thread_id, thread_name))
        time.sleep(10)


def cmd_scan_energy_bus(args):
    _ = args
    from gateway.initialize import setup_minimal_energy_platform
    from gateway.energy_module_controller import EnergyModuleController
    from serial_utils import RS485
    setup_minimal_energy_platform()

    @Inject
    def scan(energy_module_controller=INJECTED, energy_serial=INJECTED):  # type: (EnergyModuleController, RS485) -> None
        logger.info('Scanning energy bus...')
        energy_serial.start()
        max_address = EnergyModuleController.VALID_ADDRESS_RANGE[1]
        logged_percentage = 0
        for online, module_type, address, firmware_version, hardware_version in energy_module_controller.scan_bus():
            if online is True:
                logger.info('* {0} {1}: {2}{3}'.format(module_type, address, firmware_version, '' if hardware_version is None else ' {0}'.format(hardware_version)))
                if address == EnergyModuleController.DEFAULT_ADDRESS:
                    logger.info('  Note: This module is using the default address, this can cause issues if multiple modules are added')
            percentage = int(address / float(max_address) * 100)
            if percentage % 10 == 0 and 100 > percentage > logged_percentage:
                logger.info('* {0}% ({1}/{2})'.format(percentage, address, max_address))
                logged_percentage = percentage
        logger.info('Scan complete')
    scan()


def cmd_vpn_heartbeat(args):
    logging.getLogger('openmotics').setLevel(logging.DEBUG)
    from ioc import Injectable
    Injectable.value(message_client=None)

    from vpn_service import HeartbeatService
    service = HeartbeatService()

    for _ in range(60):
        try:
            print(service.heartbeat())
        except Exception:
            pass
        finally:
            time.sleep(10)


def cmd_vpn_rotate_client_certs(args):
    logging.getLogger('openmotics').setLevel(logging.DEBUG)
    from ioc import Injectable
    Injectable.value(message_client=None)

    from vpn_service import Cloud, TaskExecutor
    executor = TaskExecutor(cloud=Cloud())
    executor.configure_tasks()
    executor.enqueue({'cloud_enabled': True, 'heartbeat_success': True, 'open_vpn': True, 'update_certs': True})
    executor.execute_tasks()


parser = argparse.ArgumentParser()
parser.add_argument('--version', action='version', version=gateway.__version__)
parser.set_defaults(func=lambda args: parser.print_help())
subparsers = parser.add_subparsers()

feature_parser = subparsers.add_parser('feature')
feature_parser.set_defaults(func=lambda args: feature_parser.print_help())
feature_subparsers = feature_parser.add_subparsers()
feature_thermostats_parser = feature_subparsers.add_parser('thermostats')
feature_thermostats_parser.set_defaults(func=cmd_feature_thermostats)
feature_thermostats_parser.add_argument('--enable', action='store_true')
feature_thermostats_parser.add_argument('--disable', action='store_true')
feature_thermostats_parser.add_argument('--migrate', action='store_true')

operator_parser = subparsers.add_parser('operator')
operator_parser.set_defaults(func=lambda args: operator_parser.print_help())
operator_subparsers = operator_parser.add_subparsers()
factory_reset_parser = operator_subparsers.add_parser('factory-reset')
factory_reset_parser.set_defaults(func=cmd_factory_reset)
factory_reset_parser.add_argument('--force', action='store_true')
factory_reset_parser.add_argument('--can', action='store_true')
shell_parser = operator_subparsers.add_parser('shell')
shell_parser.set_defaults(func=cmd_shell)
top_parser = operator_subparsers.add_parser('top')
top_parser.set_defaults(func=cmd_top)
top_parser.add_argument('-p', '--pid', type=int)
scan_energy_bus_parser = operator_subparsers.add_parser('scan-energy-bus')
scan_energy_bus_parser.set_defaults(func=cmd_scan_energy_bus)

vpn_parser = subparsers.add_parser('vpn')
vpn_parser.set_defaults(func=lambda args: vpn_parser.print_help())
vpn_subparsers = vpn_parser.add_subparsers()
heartbeat_parser = vpn_subparsers.add_parser('heartbeat')
heartbeat_parser.set_defaults(func=cmd_vpn_heartbeat)
rotate_client_certs_parser = vpn_subparsers.add_parser('rotate-client-certs')
rotate_client_certs_parser.set_defaults(func=cmd_vpn_rotate_client_certs)


def main():
    Logs.setup_logger()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
