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
@author: fryckbos
"""

import logging
from datetime import datetime
from threading import Thread

from gateway.daemon_thread import DaemonThread
import power.power_api as power_api

logger = logging.getLogger("openmotics")


class TimeKeeper(object):
    """ The TimeKeeper keeps track of time and sets the day or night mode on the power modules. """

    def __init__(self, power_communicator, power_controller, period):
        self.__power_communicator = power_communicator
        self.__power_controller = power_controller
        self.__period = period

        self.__mode = {}

        self.__thread = None
        self.__stop = False

    def start(self):
        # type: () -> None
        """ Start the background thread of the TimeKeeper. """
        if self.__thread is None:
            logger.info("Starting TimeKeeper")
            self.__stop = False
            self.__thread = DaemonThread(name='TimeKeeper thread',
                                         target=self.__run,
                                         interval=self.__period)
            self.__thread.start()
        else:
            raise Exception("TimeKeeper thread already running.")

    def stop(self):
        # type: () -> None
        """ Stop the background thread in the TimeKeeper. """
        if self.__thread is not None:
            self.__thread.stop()
            self.__thread = None
        else:
            raise Exception("TimeKeeper thread not running.")

    def __run(self):
        # type: () -> None
        """ One run of the background thread. """
        date = datetime.now()
        for module in self.__power_controller.get_power_modules().values():
            version = module['version']
            if version == power_api.P1_CONCENTRATOR:
                continue
            daynight = []
            for i in range(power_api.NUM_PORTS[version]):
                if self.is_day_time(module['times%d' % i], date):
                    daynight.append(power_api.DAY)
                else:
                    daynight.append(power_api.NIGHT)

            self.__set_mode(version, module['address'], daynight)

    @staticmethod
    def is_day_time(times, date):
        """ Check if a date is in day time. """
        if times is None:
            times = [0 for _ in range(14)]
        else:
            times = [int(t.replace(":", "")) for t in times.split(",")]

        day_of_week = date.weekday()  # 0 = Monday, 6 = Sunday
        current_time = date.hour * 100 + date.minute

        start = times[day_of_week * 2]
        stop = times[day_of_week * 2 + 1]

        return stop > current_time >= start

    def __set_mode(self, version, address, bytes):
        """ Set the power modules mode. """
        if address not in self.__mode or self.__mode[address] != bytes:
            logger.info("Setting day/night mode to " + str(bytes))
            self.__power_communicator.do_command(address, power_api.set_day_night(version), *bytes)
            self.__mode[address] = bytes
