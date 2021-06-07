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

from __future__ import absolute_import

import logging
import os
import time
from subprocess import check_output

import ujson as json

from gateway.daemon_thread import DaemonThread
from gateway.models import Config
from ioc import INJECTED, Inject, Injectable, Singleton
from serial_utils import CommunicationStatus

if False:  # MYPY
    from typing import Callable, Literal, Optional, Union, Dict, Any
    from gateway.hal.master_controller import MasterController
    from power.power_communicator import PowerCommunicator

    HEALTH = Literal['success', 'unstable', 'failure']

logger = logging.getLogger(__name__)


@Injectable.named('watchdog')
@Singleton
class Watchdog(object):
    """
    The watchdog monitors various internal threads
    """

    @Inject
    def __init__(self, power_communicator=INJECTED, master_controller=INJECTED):
        # type: (Optional[PowerCommunicator], MasterController) -> None
        self._master_controller = master_controller
        self._power_communicator = power_communicator
        self._watchdog_thread = None  # type: Optional[DaemonThread]
        self.start_time = 0.0

    def start(self):
        # type: () -> None
        if self._watchdog_thread is None:
            self.start_time = time.time()
            self._watchdog_thread = DaemonThread(name='watchdog',
                                                 target=self._watch,
                                                 interval=60, delay=10)
            self._watchdog_thread.start()

    def stop(self):
        # type: () -> None
        if self._watchdog_thread is not None:
            self._watchdog_thread.stop()
            self._watchdog_thread = None

    def _watch(self):
        # type: () -> None
        self._controller_health('master', self._master_controller, self._master_controller.cold_reset)
        if self._power_communicator:
            self._controller_health('energy', self._power_communicator, self._master_controller.power_cycle_bus)

    def _controller_health(self, name, controller, device_reset):
        # type: (str, Union[PowerCommunicator,MasterController], Callable[[],None]) -> None
        status = controller.get_communicator_health()
        if status == CommunicationStatus.SUCCESS:
            Config.remove_entry('communication_recovery_{0}'.format(name))
            # Cleanup legacy
            Config.remove_entry('communication_recovery')
        elif status == CommunicationStatus.UNSTABLE:
            logger.warning('Observed unstable communication for %s', name)
        else:
            reset_action = self._get_reset_action(name, controller)
            if reset_action is not None:
                device_reset()
                if reset_action == 'service':
                    time.sleep(15)
                    os._exit(1)

    def _get_reset_action(self, name, controller):
        # type: (str, Union[MasterController,PowerCommunicator]) -> Optional[str]
        recovery_data_key = 'communication_recovery_{0}'.format(name)
        recovery_data = Config.get_entry(recovery_data_key, None)  # type: Optional[Dict[str, Any]]
        if recovery_data is None:  # Make mypy happy
            recovery_data = {}

        stats = controller.get_communication_statistics()
        calls_timedout = [call for call in stats['calls_timedout']]
        calls_succeeded = [call for call in stats['calls_succeeded']]

        service_restart = None
        device_reset = None
        backoff = 300
        max_attempts = 3

        last_device_reset = recovery_data.get('device_reset')
        last_service_restart = recovery_data.get('service_restart')
        if len(recovery_data) == 0:
            device_reset = 'communication_errors'
        else:
            backoff = 0 if last_device_reset is None else last_device_reset.get('backoff', backoff)
            if last_device_reset is None or last_device_reset['time'] < time.time() - backoff:
                device_reset = 'communication_errors'
                backoff = min(1200, backoff * 2)
            else:
                if last_service_restart is None:
                    service_restart = 'communication_errors'
                else:
                    backoff = last_service_restart.get('backoff', backoff)
                    if last_service_restart['time'] < time.time() - backoff:
                        service_restart = 'communication_errors'
                        backoff = min(1200, backoff * 2)

        if service_restart is not None or device_reset is not None:
            # Log debug information
            try:
                debug_buffer = controller.get_debug_buffer()
                action = device_reset or service_restart
                debug_data = {'type': 'communication_recovery',
                              'info': {'controller': name, 'action': action},
                              'data': {'buffer': debug_buffer,
                                       'calls': {'timedout': calls_timedout,
                                                 'succeeded': calls_succeeded}}}
                with open('/tmp/debug_{0}_{1}.json'.format(name, int(time.time())), 'w') as recovery_file:
                    recovery_file.write(json.dumps(debug_data, indent=4, sort_keys=True))
                check_output(
                    "ls -tp /tmp/ | grep 'debug_{0}_.*json' | tail -n +10 | while read file; do rm -r /tmp/$file; done".format(name),
                    shell=True
                )
            except Exception as ex:
                logger.exception('Could not store debug file: {0}'.format(ex))

        if service_restart is not None:
            last_service_restart = last_service_restart or {}
            attempts = last_service_restart.get('attempts', 0)
            if attempts < max_attempts:
                logger.critical('Major issues in communication with {0}. Restarting service...'.format(name))
                recovery_data['service_restart'] = {'reason': service_restart,
                                                    'time': time.time(),
                                                    'attempts': attempts + 1,
                                                    'backoff': backoff}
                Config.set_entry(recovery_data_key, recovery_data)
                return 'service'
            else:
                logger.critical('Unable to recover issues in communication with {0}'.format(name))

        if device_reset is not None:
            last_device_reset = last_device_reset or {}
            attempts = last_device_reset.get('attempts', 0)
            if attempts < max_attempts:
                logger.critical('Major issues in communication with {0}. Resetting {0}'.format(name))
                recovery_data['device_reset'] = {'reason': device_reset,
                                                 'time': time.time(),
                                                 'attempts': attempts + 1,
                                                 'backoff': backoff}
                Config.set_entry(recovery_data_key, recovery_data)
                return 'device'
            else:
                logger.critical('Unable to recover issues in communication with {0}'.format(name))

        return None
