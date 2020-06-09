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

import argparse
import logging
import os
import sys
import constants
import gateway
import gateway.initialize
from ioc import INJECTED, Inject

logger = logging.getLogger('openmotics')


def cmd_get_realtime_power(args):
    _ = args
    gateway.initialize.setup_platform(message_client_name='openmotics_cli')

    @Inject
    def f(gateway_api=INJECTED):
        return gateway_api.get_realtime_power()
    print(f())


def cmd_get_realtime_p1(args):
    _ = args
    gateway.initialize.setup_platform(message_client_name='openmotics_cli')

    @Inject
    def f(gateway_api=INJECTED):
        return gateway_api.get_realtime_p1()
    print(f())


def cmd_get_total_energy(args):
    _ = args
    gateway.initialize.setup_platform(message_client_name='openmotics_cli')

    @Inject
    def f(gateway_api=INJECTED):
        return gateway_api.get_total_energy()
    print(f())


def cmd_factory_reset(args):
    lock_file = constants.get_init_lockfile()
    if os.path.isfile(lock_file) and not args.force:
        print('already_in_progress')
        exit(1)
    with open(lock_file, 'w') as fd:
        fd.write('factory_reset')


parser = argparse.ArgumentParser()
parser.add_argument('--version', action='version', version=gateway.__version__)
subparsers = parser.add_subparsers()

controller_parser = subparsers.add_parser('controller')
controller_subparsers = controller_parser.add_subparsers()
realtime_power_parser = controller_subparsers.add_parser('realtime-power')
realtime_power_parser.set_defaults(func=cmd_get_realtime_power)
realtime_p1_parser = controller_subparsers.add_parser('realtime-p1')
realtime_p1_parser.set_defaults(func=cmd_get_realtime_p1)
total_energy_parser = controller_subparsers.add_parser('total-energy')
total_energy_parser.set_defaults(func=cmd_get_total_energy)

operator_parser = subparsers.add_parser('operator')
operator_subparsers = operator_parser.add_subparsers()
factory_reset_parser = operator_subparsers.add_parser('factory-reset')
factory_reset_parser.set_defaults(func=cmd_factory_reset)
factory_reset_parser.add_argument('--force', action='store_true')


def main():
    args = parser.parse_args()
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.INFO)
    args.func(args)


if __name__ == '__main__':
    main()
