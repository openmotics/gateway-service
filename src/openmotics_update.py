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
    parser = argparse.ArgumentParser(description='Tool to update components')
    parser.add_argument('--update-gateway-service', dest='gateway_service_version',
                        help='Updates the gateway service to a given (prepared) version')
    args = parser.parse_args()

    Logs.setup_logger()

    if not args.gateway_service_version:
        parser.print_help()
        sys.exit(1)

    from gateway.update_controller import UpdateController
    UpdateController.update_gateway_service(args.gateway_service_version)
