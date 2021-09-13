# Copyright (C) 2021 OpenMotics BV
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
"""
CLI update tool
"""
from __future__ import absolute_import
from platform_utils import System, Platform
System.import_libs()

import os
import logging
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter, SUPPRESS
from gateway.enums import UpdateEnums
from logs import Logs
from ioc import INJECTED, Inject

if False:  # MYPY
    from typing import Optional
    from serial_utils import RS485
    from master.classic.master_communicator import MasterCommunicator

logger = logging.getLogger()


if __name__ == '__main__':
    from gateway.update_controller import UpdateController

    parser = ArgumentParser(description='Tool to update various components.',
                            epilog='Footnotes:\n'
                                   '  1. The --version argument is required. The --file argument is optional.\n'
                                   '  2. When the --file argument is not specified, the firmware will be download.\n'
                                   '  3. Address in format xxx.xxx.xxx.xxx (rs485 slaves) or xxx.xxx.xxx (uCAN)',
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('--execute-gateway-service-update',
                        dest='update_gateway_service',
                        help=SUPPRESS)
    parser.add_argument('--prepare-gateway-service-for-first-startup',
                        dest='prepare_gateway_service',
                        help=SUPPRESS)
    group = parser.add_mutually_exclusive_group()
    for module_type in UpdateController.MODULE_TYPE_MAP.keys():
        if module_type in ['master_core', 'master_classic']:
            platform = Platform.get_platform()
            supported = ((platform in Platform.CoreTypes and module_type == 'master_core') or
                         (platform in Platform.ClassicTypes and module_type == 'master_classic'))
            if supported:
                group.add_argument('--update-master', action='store_true',
                                   dest='update_{0}'.format(module_type),
                                   help='Update {0} (1)'.format('master' if module_type == 'master_classic' else 'brain(+)'))
        else:
            group.add_argument('--update-{0}'.format(module_type.replace('_', '-')), action='store_true',
                               dest='update_{0}'.format(module_type),
                               help='Update {0} modules (1)'.format(module_type.replace('_', '')))
    parser.add_argument('--file',
                        dest='filename',
                        help='Filename of the hex file to use (2)')
    parser.add_argument('--version',
                        dest='version',
                        help='Firmware version of the specified hex file')
    parser.add_argument('--force',
                        dest='force', action='store_true',
                        help='Force an update, even if the module(s) is/are already on the correct version')
    parser.add_argument('--address',
                        dest='address',
                        help='Only update a single module, specified by this address (3)')
    args = parser.parse_args()

    if args.update_gateway_service or args.prepare_gateway_service:
        Logs.setup_logger()
        from gateway.update_controller import UpdateController
        task = 'unknown'
        version = 'unknown'
        try:
            if args.update_gateway_service:
                task = 'update gateway service'
                version = args.update_gateway_service
                component_logger = Logs.get_update_logger('gateway_service')
                component_logger.propagate = False
                UpdateController.update_gateway_service(new_version=version, logger=component_logger)
            elif args.prepare_gateway_service:
                task = 'prepare gateway service for first startup'
                version = args.prepare_gateway_service
                component_logger = Logs.get_print_logger('update.gateway_service')
                UpdateController.update_gateway_service_prepare_for_first_startup(logger=component_logger)
            sys.exit(0)
        except Exception as ex:
            with open(UpdateController.SERVICE_BASE_TEMPLATE.format('{0}.failure'.format(version)), 'a') as failure:
                failure.write('Failed to {0} ({1}): {2}\n'.format(task, version, ex))
            sys.exit(1)

    if args.version:
        @Inject
        def _get_update_controller(update_controller=INJECTED):
            # type: (UpdateController) -> UpdateController
            return update_controller

        @Inject
        def _get_energy_stack(energy_serial=INJECTED):
            # type: (RS485) -> RS485
            return energy_serial

        @Inject
        def _get_master_stack(master_communicator=INJECTED):
            # type: (MasterCommunicator) -> MasterCommunicator
            # Could technically also be a CoreCommunicator, but doesn't matter that
            # much here, as both implemnt the start() method
            return master_communicator

        firmware_filename = None  # type: Optional[str]
        if args.filename and os.path.exists(args.filename):
            firmware_filename = args.filename

        start_energy_stack = False
        start_master_stack = False

        for module_type in UpdateController.MODULE_TYPE_MAP.keys():
            args_key = 'update_{0}'.format(module_type)
            update_requested = hasattr(args, args_key) and getattr(args, args_key)
            if update_requested:
                if module_type in ['energy', 'p1_concentrator']:
                    start_energy_stack = True
                else:
                    start_master_stack = True

                if module_type is not None:
                    Logs.setup_logger()
                    from gateway.initialize import setup_platform
                    setup_platform(message_client_name=None)
                    if start_energy_stack:
                        serial = _get_energy_stack()
                        serial.start()
                    if start_master_stack:
                        communicator = _get_master_stack()
                        communicator.start()

                    controller = _get_update_controller()
                    mode = UpdateEnums.Modes.FORCED if args.force else UpdateEnums.Modes.MANUAL
                    successes, failures = controller.update_module_firmware(module_type=module_type,
                                                                            target_version=args.version,
                                                                            mode=mode,
                                                                            module_address=args.address,
                                                                            firmware_filename=firmware_filename)
                    total_updates = successes + failures
                    logger.info('Updated {0} module{1}: {2} success{3}, {4} failure{5}'.format(
                        total_updates, 's' if total_updates != 1 else '',
                        successes, 'es' if successes != 1 else '',
                        failures, 's' if failures != 1 else ''
                    ))
                    sys.exit(0)

    parser.print_help()
    sys.exit(1)
