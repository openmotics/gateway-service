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
from platform_utils import System
System.import_libs()

import logging
import argparse
import sys
from logs import Logs

logger = logging.getLogger()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tool to update various components.',
                                     epilog='Some arguments are not documented above, as they are meant '
                                            'for internal use only. This means that they require '
                                            'a specific state on the filesystem before they can be executed')
    parser.add_argument('--execute-gateway-service-update',
                        dest='update_gateway_service',
                        help=argparse.SUPPRESS)
    parser.add_argument('--prepare-gateway-service-for-first-startup',
                        dest='prepare_gateway_service',
                        help=argparse.SUPPRESS)
    args = parser.parse_args()

    Logs.setup_logger()

    update_gateway_service = args.update_gateway_service
    prepare_gateway_service = args.prepare_gateway_service

    if not update_gateway_service and not prepare_gateway_service:
        parser.print_help()
        sys.exit(1)

    from gateway.update_controller import UpdateController
    task = 'unknown'
    version = 'unknown'
    try:
        if update_gateway_service:
            task = 'update gateway service'
            version = update_gateway_service
            component_logger = Logs.get_update_logger('gateway_service')
            UpdateController.update_gateway_service(new_version=version, logger=component_logger)
        elif prepare_gateway_service:
            task = 'prepare gateway service for first startup'
            version = prepare_gateway_service
            component_logger = Logs.get_print_logger('update.gateway_service')
            UpdateController.update_gateway_service_prepare_for_first_startup(logger=component_logger)
        sys.exit(0)
    except Exception as ex:
        with open(UpdateController.SERVICE_BASE_TEMPLATE.format('{0}.failure'.format(version)), 'a') as failure:
            failure.write('Failed to {0} ({1}): {2}\n'.format(task, version, ex))
        sys.exit(1)
