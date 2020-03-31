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
"""
Contains a watchdog that monitors internal service threads
"""

import logging
import os
import time
from subprocess import check_output

import ujson as json

from gateway.daemon_thread import DaemonThread
from ioc import INJECTED, Inject, Injectable, Singleton

logger = logging.getLogger("openmotics")


@Injectable.named('watchdog')
@Singleton
class Watchdog(object):
    """
    The watchdog monitors various internal threads
    """

    @Inject
    def __init__(self, power_communicator=INJECTED, master_controller=INJECTED, configuration_controller=INJECTED):
        self._master_controller = master_controller
        self._power_communicator = power_communicator
        self._config_controller = configuration_controller

        self._watchdog_thread = DaemonThread(name='Watchdog watcher',
                                             target=self._watch,
                                             interval=60)

    def start(self):
        # type: () -> None
        self._stopped = False
        self._watchdog_thread.start()

    def stop(self):
        # type: () -> None
        self._watchdog_thread.stop()

    def _watch(self):
        # type: () -> None
        # Cleanup legacy
        self._config_controller.remove('communication_recovery')

        reset_requirement = self._controller_check('master', self._master_controller)
        if reset_requirement is not None:
            if reset_requirement == 'device':
                self._master_controller.cold_reset()
            time.sleep(15)
            os._exit(1)
        reset_requirement = self._controller_check('energy', self._power_communicator)
        if reset_requirement is not None:
            if reset_requirement == 'device':
                self._master_controller.power_cycle_bus()
            time.sleep(15)
            os._exit(1)

    def _controller_check(self, name, controller):
        recovery_data_key = 'communication_recovery_{0}'.format(name)
        recovery_data = self._config_controller.get(recovery_data_key, {})

        calls_timedout = controller.get_communication_statistics()['calls_timedout']
        calls_succeeded = controller.get_communication_statistics()['calls_succeeded']
        all_calls = sorted(calls_timedout + calls_succeeded)

        if len(calls_timedout) == 0:
            # If there are no timeouts at all
            if len(calls_succeeded) > 30:
                self._config_controller.remove(recovery_data_key)
            return
        if len(all_calls) <= 10:
            # Not enough calls made to have a decent view on what's going on
            return
        if not any(t in calls_timedout for t in all_calls[-10:]):
            # The last X calls are successfull
            return
        calls_last_x_minutes = [t for t in all_calls if t > time.time() - 180]
        ratio = len([t for t in calls_last_x_minutes if t in calls_timedout]) / float(len(calls_last_x_minutes))
        if ratio < 0.25:
            # Less than 25% of the calls fail, let's assume everything is just "fine"
            logger.warning('Noticed communication timeouts for \'{0}\', but there\'s only a failure ratio of {1:.2f}%.'.format(
                name, ratio * 100
            ))
            return

        service_restart = None
        device_reset = None
        backoff = 300
        # There's no successful communication.
        if len(recovery_data) == 0:
            service_restart = 'communication_errors'
        else:
            last_service_restart = recovery_data.get('service_restart')
            if last_service_restart is None:
                service_restart = 'communication_errors'
            else:
                backoff = last_service_restart['backoff']
                if last_service_restart['time'] < time.time() - backoff:
                    service_restart = 'communication_errors'
                    backoff = min(1200, backoff * 2)
                else:
                    last_device_reset = recovery_data.get('device_reset')
                    if last_device_reset is None or last_device_reset['time'] < last_service_restart['time']:
                        device_reset = 'communication_errors'

        if service_restart is not None or device_reset is not None:
            # Log debug information
            try:
                debug_buffer = controller.get_debug_buffer()
                debug_data = {'type': 'communication_recovery',
                              'data': {'buffer': debug_buffer,
                                       'calls': {'timedout': calls_timedout,
                                                 'succeeded': calls_succeeded},
                                       'action': 'service_restart' if service_restart is not None else 'device_reset'}}
                with open('/tmp/debug_{0}_{1}.json'.format(name, int(time.time())), 'w') as recovery_file:
                    recovery_file.write(json.dumps(debug_data, indent=4, sort_keys=True))
                check_output(
                    "ls -tp /tmp/ | grep 'debug_{0}_.*json' | tail -n +10 | while read file; do rm -r /tmp/$file; done".format(name),
                    shell=True
                )
            except Exception as ex:
                logger.exception('Could not store debug file: {0}'.format(ex))

        if service_restart is not None:
            logger.fatal('Major issues in communication with {0}. Restarting service...'.format(name))
            recovery_data['service_restart'] = {'reason': service_restart,
                                                'time': time.time(),
                                                'backoff': backoff}
            self._config_controller.set(recovery_data_key, recovery_data)
            return 'service'
        if device_reset is not None:
            logger.fatal('Major issues in communication with {0}. Resetting {0} & service'.format(name))
            recovery_data['device_reset'] = {'reason': device_reset,
                                             'time': time.time()}
            self._config_controller.set(recovery_data_key, recovery_data)
            return 'device'
