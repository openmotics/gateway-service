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
"""
The maintenance module contains the MaintenanceCommunicator class.
"""
from __future__ import absolute_import

import logging
import time
from threading import Thread, Timer

from gateway.daemon_thread import BaseThread
from gateway.hal.master_event import MasterEvent
from gateway.maintenance_communicator import MaintenanceCommunicator
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject

if False:  # MYPY
    from typing import Callable, Optional
    from master.classic.master_communicator import MasterCommunicator

logger = logging.getLogger(__name__)


class MaintenanceClassicCommunicator(MaintenanceCommunicator):
    """
    The maintenance communicator handles maintenance communication with the Master
    """

    MAINTENANCE_TIMEOUT = 600

    @Inject
    def __init__(self, master_communicator=INJECTED, pubsub=INJECTED):
        # type: (MasterCommunicator, PubSub) -> None
        """
        Construct a MaintenanceCommunicator.

        :param master_communicator: the communication with the master.
        :type master_communicator: master.master_communicator.MasterCommunicator
        """
        self._master_communicator = master_communicator
        self._pubsub = pubsub
        self._deactivated_sent = False
        self._last_maintenance_send_time = 0.0
        self._stopped = False
        self._maintenance_timeout_timer = None  # type: Optional[Timer]
        self._read_data_thread = None  # type: Optional[Thread]
        self._receiver_callback = None  # type: Optional[Callable[[str],None]]

    def start(self):
        # type: () -> None
        pass  # Classic doesn't have a permanent running maintenance

    def stop(self):
        # type: () -> None
        pass  # Classic doesn't have a permanent running maintenance

    def set_receiver(self, callback):
        # type: (Callable[[str],None]) -> None
        self._receiver_callback = callback

    def is_active(self):
        # type: () -> bool
        return self._master_communicator.in_maintenance_mode()

    def activate(self):
        # type: () -> None
        """
        Activates maintenance mode, If no data is send for too long, maintenance mode will be closed automatically.
        """
        logger.info('Activating maintenance mode')
        self._last_maintenance_send_time = time.time()
        self._master_communicator.start_maintenance_mode()
        self._maintenance_timeout_timer = Timer(MaintenanceClassicCommunicator.MAINTENANCE_TIMEOUT, self._check_maintenance_timeout)
        self._maintenance_timeout_timer.start()
        self._stopped = False
        self._read_data_thread = BaseThread(target=self._read_data, name='maintenanceread')
        self._read_data_thread.daemon = True
        self._read_data_thread.start()
        self._deactivated_sent = False

    def deactivate(self, join=True):
        # type: (bool) -> None
        logger.info('Deactivating maintenance mode')
        self._stopped = True
        if join and self._read_data_thread is not None:
            self._read_data_thread.join()
            self._read_data_thread = None
        self._master_communicator.stop_maintenance_mode()

        if self._maintenance_timeout_timer is not None:
            self._maintenance_timeout_timer.cancel()
            self._maintenance_timeout_timer = None

        if self._deactivated_sent is False:
            master_event = MasterEvent(MasterEvent.Types.MAINTENANCE_EXIT, {})
            self._pubsub.publish_master_event(PubSub.MasterTopics.MAINTENANCE, master_event)
            self._deactivated_sent = True

    def _check_maintenance_timeout(self):
        # type: () -> None
        """
        Checks if the maintenance if the timeout is exceeded, and closes maintenance mode
        if required.
        """
        timeout = MaintenanceClassicCommunicator.MAINTENANCE_TIMEOUT
        if self._master_communicator.in_maintenance_mode():
            current_time = time.time()
            if self._last_maintenance_send_time + timeout < current_time:
                logger.info('Stopping maintenance mode because of timeout.')
                self.deactivate()
            else:
                wait_time = self._last_maintenance_send_time + timeout - current_time
                self._maintenance_timeout_timer = Timer(wait_time, self._check_maintenance_timeout)
                self._maintenance_timeout_timer.start()
        else:
            self.deactivate()

    def write(self, message):
        # type: (str) -> None
        self._last_maintenance_send_time = time.time()
        data = '{0}\r\n'.format(message.strip()).encode()
        self._master_communicator.send_maintenance_data(bytearray(data))

    def _read_data(self):
        # type: () -> None
        """ Reads from the serial port and writes to the socket. """
        buffer = ''
        while not self._stopped:
            try:
                data = self._master_communicator.get_maintenance_data()
                if data is None:
                    continue
                buffer += data.decode()
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    if self._receiver_callback is not None:
                        try:
                            self._receiver_callback(message.rstrip())
                        except Exception:
                            logger.exception('Unexpected exception during maintenance callback')
            except Exception:
                logger.exception('Exception in maintenance read thread')
                break
        self.deactivate(join=False)
