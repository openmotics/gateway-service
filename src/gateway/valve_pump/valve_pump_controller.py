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

from gateway.daemon_thread import DaemonThread
from gateway.models import Database, Pump, Valve, PumpToValveAssociation
from gateway.valve_pump.pump_driver import PumpDriver
from gateway.valve_pump.valve_driver import ValveDriver
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MYPY
    from typing import List, Dict, Set

logger = logging.getLogger(__name__)

@Injectable.named('valve_pump_controller')
@Singleton
class ValvePumpController(object):
    PUMP_UPDATE_INTERVAL = 30

    def __init__(self, ):  # type: () -> None
        # list of valves linked to this specific driver, which is linked to a thermostat:
        self._valve_drivers = {}  # type: Dict[int, ValveDriver]
        self._pump_drivers = {}  # type: Dict[int, PumpDriver]
        self._pump_drivers_per_valve = {}  # type: Dict[int, Set[PumpDriver]]
        self._config_change_lock = Lock()
        self._update_pumps_thread = DaemonThread(name='thermostatpumps',
                                                 target=self.update_system,
                                                 interval=self.PUMP_UPDATE_INTERVAL)

    def start(self):
        self._update_pumps_thread.start()

    def stop(self):
        if self._update_pumps_thread is not None:
            self._update_pumps_thread.stop()


    def update_from_db(self):  # type: () -> None
        with self._config_change_lock, Database.get_session() as db:

            # Collect valve drivers
            current_ids = []
            for valve in db.query(Valve):
                if valve.id in self._valve_drivers:
                    self._valve_drivers[valve.id].update(valve)
                else:
                    self._valve_drivers[valve.id] = ValveDriver(valve)
                current_ids.append(valve.id)

            # remove valve drivers that are no longer needed
            for item_id in list(self._valve_drivers.keys()):
                if item_id not in current_ids:
                    del self._valve_drivers[item_id]

            # Collect pump drivers
            current_ids = []
            pump_drivers_per_valve = {}  # type: Dict[int, Set[PumpDriver]]
            for pump in db.query(Pump):
                if pump.id in self._pump_drivers:
                    pump_driver = self._pump_drivers[pump.id]
                    pump_driver.update(pump)
                else:
                    pump_driver = PumpDriver(pump)
                    self._pump_drivers[pump.id] = pump_driver
                current_ids.append(pump.id)
                for valve_id in pump_driver.valve_ids:
                    if valve_id not in pump_drivers_per_valve:
                        pump_drivers_per_valve[valve_id] = set()
                    pump_drivers_per_valve[valve_id].add(pump_driver)

            # remove pump drivers that are no longer needed
            for item_id in list(self._pump_drivers.keys()):
                if item_id not in current_ids:
                    del self._pump_drivers[item_id]
            self._pump_drivers_per_valve = pump_drivers_per_valve




    @staticmethod
    def _open_valves_cascade(total_percentage, valve_drivers):
        # type: (float, List[ValveDriver]) -> None
        n_valves = len(valve_drivers)
        if n_valves == 0:
            return
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




    def _set_valves(self, percentage, valve_ids, mode='equal'):  # type: (int, List[int], str) -> None
        logger.debug("set valves with id: {} to percentage: {}".format(valve_ids, percentage))
        valve_drivers = [self.get_valve_driver(valve_id) for valve_id in valve_ids]
        if mode == 'cascade':
            self._open_valves_cascade(percentage, valve_drivers)
        else:
            self._open_valves_equal(percentage, valve_drivers)




    def steer(self, percentage, valve_ids, mode='equal'):  # type: (int, List[int], str) -> None
        self._set_valves(percentage, valve_ids, mode)
        self.update_system()




    def update_system(self):
        self._prepare_pumps_for_transition()
        self._steer_valves()
        self._steer_pumps()




    def is_valve_open(self, valve_id, percentage):
        if self._valve_drivers[valve_id].is_open(percentage=percentage) is True:
            return True
        return False



    def _prepare_pumps_for_transition(self):  # type: () -> None
        active_pump_drivers = set()
        potential_inactive_pump_drivers = set()

        # loop over the valves
        for valve_id, valve_driver in self._valve_drivers.items():
            # if valve is open, ior operation: create set with unique pump drivers for open valves
            if valve_driver.is_open(percentage=10) is True:
                active_pump_drivers |= self._pump_drivers_per_valve.get(valve_id, set())
            elif valve_driver.will_close:
                potential_inactive_pump_drivers |= self._pump_drivers_per_valve.get(valve_id, set())

        inactive_pump_drivers = potential_inactive_pump_drivers.difference(active_pump_drivers)
        for pump_driver in inactive_pump_drivers:
            pump_driver.turn_off()




    def _steer_valves(self):  # type: () -> None
        for valve_driver in self._valve_drivers.values():
            valve_driver.steer_output()




    def _steer_pumps(self):  # type: () -> None
        active_pump_drivers = set()
        potential_inactive_pump_drivers = set()
        for valve_id, valve_driver in self._valve_drivers.items():
            logger.debug("is valve with id {} open? {}".format(valve_id, valve_driver.is_open(percentage=10)))
            if valve_driver.is_open(percentage=10) is True:
                active_pump_drivers |= self._pump_drivers_per_valve.get(valve_id, set())
            else:
                potential_inactive_pump_drivers |= self._pump_drivers_per_valve.get(valve_id, set())
        inactive_pump_drivers = potential_inactive_pump_drivers.difference(active_pump_drivers)

        for pump_driver in inactive_pump_drivers:
            pump_driver.turn_off()
        for pump_driver in active_pump_drivers:
            pump_driver.turn_on()




    def get_valve_driver(self, valve_id):  # type: (int) -> ValveDriver
        valve_driver = self._valve_drivers.get(valve_id)
        if valve_driver is None:
            with Database.get_session() as db:
                valve = db.get(Valve, valve_id)
                valve_driver = ValveDriver(valve)
            self._valve_drivers[valve.id] = valve_driver
        return valve_driver
