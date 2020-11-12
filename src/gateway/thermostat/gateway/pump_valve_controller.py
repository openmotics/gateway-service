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

import logging
from threading import Lock
from ioc import Inject
from gateway.models import Valve
from gateway.thermostat.gateway.valve_driver import ValveDriver

if False:  # MYPY
    from typing import List, Dict

logger = logging.getLogger('openmotics')


@Inject
class PumpValveController(object):
    def __init__(self):  # type: () -> None
        self._valve_drivers = {}  # type: Dict[int, ValveDriver]
        self._config_change_lock = Lock()

    def refresh_from_db(self):  # type: () -> None
        with self._config_change_lock:
            existing_driver_numbers = set(self._valve_drivers.keys())
            new_driver_numbers = set()
            for valve in Valve.select():
                if valve.number in existing_driver_numbers:
                    self._valve_drivers[valve.number].update_valve(valve)
                else:
                    self._valve_drivers[valve.number] = ValveDriver(valve)
                new_driver_numbers.add(valve.number)

            drivers_to_be_deleted = existing_driver_numbers.difference(new_driver_numbers)
            for driver_number in drivers_to_be_deleted:
                valve_driver = self._valve_drivers.get(driver_number)
                if valve_driver is not None:
                    valve_driver.close()
                    del self._valve_drivers[driver_number]

    @staticmethod
    def _open_valves_cascade(total_percentage, valve_drivers):
        # type: (float, List[ValveDriver]) -> None
        n_valves = len(valve_drivers)
        percentage_per_valve = 100.0 / n_valves
        n_valves_fully_open = int(total_percentage / percentage_per_valve)
        last_valve_open_percentage = 100.0 * (total_percentage - n_valves_fully_open * percentage_per_valve) / percentage_per_valve
        for n in range(n_valves_fully_open):
            valve_driver = valve_drivers[n]
            valve_driver.set(100)
        for n in range(n_valves_fully_open, n_valves):
            valve_driver = valve_drivers[n]
            percentage = last_valve_open_percentage if n == n_valves_fully_open else 0
            valve_driver.set(percentage)

    @staticmethod
    def _open_valves_equal(percentage, valve_drivers):
        # type: (float, List[ValveDriver]) -> None
        for valve_driver in valve_drivers:
            valve_driver.set(percentage)

    def set_valves(self, percentage, valve_numbers, mode='cascade'):
        # type: (float, List[int], str) -> None
        if len(valve_numbers) > 0:
            valve_drivers = [self.get_valve_driver(valve_number) for valve_number in valve_numbers]
            if mode == 'cascade':
                self._open_valves_cascade(percentage, valve_drivers)
            else:
                self._open_valves_equal(percentage, valve_drivers)

    def steer(self):  # type: () -> None
        self.prepare_pumps_for_transition()
        self.steer_valves()
        self.steer_pumps()

    def prepare_pumps_for_transition(self):  # type: () -> None
        active_pump_drivers = set()
        potential_inactive_pump_drivers = set()
        for valve_number, valve_driver in self._valve_drivers.items():
            if valve_driver.is_open:
                for pump_driver in valve_driver.pump_drivers:
                    active_pump_drivers.add(pump_driver)
            elif valve_driver.will_close:
                for pump_driver in valve_driver.pump_drivers:
                    potential_inactive_pump_drivers.add(pump_driver)

        inactive_pump_drivers = potential_inactive_pump_drivers.difference(active_pump_drivers)
        for pump_driver in inactive_pump_drivers:
            pump_driver.turn_off()

    def steer_valves(self):  # type: () -> None
        for valve_number, valve_driver in self._valve_drivers.items():
            valve_driver.steer_output()

    def steer_pumps(self):  # type: () -> None
        active_pump_drivers = set()
        potential_inactive_pump_drivers = set()
        for valve_number, valve_driver in self._valve_drivers.items():
            if valve_driver.is_open:
                for pump_driver in valve_driver.pump_drivers:
                    active_pump_drivers.add(pump_driver)
            else:
                for pump_driver in valve_driver.pump_drivers:
                    potential_inactive_pump_drivers.add(pump_driver)
        inactive_pump_drivers = potential_inactive_pump_drivers.difference(active_pump_drivers)

        for pump_driver in inactive_pump_drivers:
            pump_driver.turn_off()
        for pump_driver in active_pump_drivers:
            pump_driver.turn_on()

    def get_valve_driver(self, valve_number):  # type: (int) -> ValveDriver
        valve_driver = self._valve_drivers.get(valve_number)
        if valve_driver is None:
            valve = Valve.get(number=valve_number)
            valve_driver = ValveDriver(valve)
            self._valve_drivers[valve.number] = valve_driver
        return valve_driver
