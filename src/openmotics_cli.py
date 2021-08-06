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
import time

import constants
import gateway
from ioc import INJECTED, Inject

logger = logging.getLogger('openmotics')


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



parser = argparse.ArgumentParser()
parser.add_argument('--version', action='version', version=gateway.__version__)
subparsers = parser.add_subparsers()

operator_parser = subparsers.add_parser('operator')
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


def main():
    args = parser.parse_args()
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.INFO)
    args.func(args)


if __name__ == '__main__':
    main()
