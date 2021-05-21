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
The passthrough module contains the PassthroughService. This service uses the GatewayApi
to communicate with the master.

@author: fryckbos
"""

from __future__ import absolute_import

import logging

from gateway.daemon_thread import BaseThread
from gateway.maintenance_communicator import InMaintenanceModeException
from ioc import INJECTED, Inject, Injectable, Singleton
from master.classic.master_command import printable

logger = logging.getLogger(__name__)


@Injectable.named('passthrough_service')
@Singleton
class PassthroughService(object):
    """ The Passthrough service creates two threads: one for reading from and one for writing
    to the master.
    """

    @Inject
    def __init__(self, master_communicator=INJECTED, passthrough_serial=INJECTED, verbose=False):
        self.__master_communicator = master_communicator
        self.__passthrough_serial = passthrough_serial
        self.__verbose = verbose

        self.__stopped = False
        self.__reader_thread = None
        self.__writer_thread = None

        self.__master_communicator.enable_passthrough()

    def start(self):
        """ Start the Passthrough service, this launches the two threads. """
        self.__reader_thread = BaseThread(name='passthroughread', target=self.__reader)
        self.__reader_thread.daemon = True
        self.__reader_thread.start()

        self.__writer_thread = BaseThread(name='passthroughwrite', target=self.__writer)
        self.__writer_thread.daemon = True
        self.__writer_thread.start()

    def __reader(self):
        """ Reads from the master and writes to the passthrough serial. """
        while not self.__stopped:
            data = self.__master_communicator.get_passthrough_data()
            if data and len(data) > 0:
                if self.__verbose:
                    logger.info("Data for passthrough: %s", printable(data))
                self.__passthrough_serial.write(data)

    def __writer(self):
        """ Reads from the passthrough serial and writes to the master. """
        while not self.__stopped:
            data = self.__passthrough_serial.read(1)
            if data and len(data) > 0:
                num_bytes = self.__passthrough_serial.inWaiting()
                if num_bytes > 0:
                    data += self.__passthrough_serial.read(num_bytes)
                try:
                    if self.__verbose:
                        logger.info("Data from passthrough: %s", printable(data))
                    self.__master_communicator.send_passthrough_data(data)
                except InMaintenanceModeException:
                    logger.info("Dropped passthrough communication in maintenance mode.")

    def stop(self):
        """ Stop the Passthrough service. """
        self.__stopped = True
