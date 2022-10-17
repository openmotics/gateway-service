

import logging
from ioc import INJECTED, Inject
from gateway.models import Database, IndoorLinkValves
from gateway.valve_pump.valve_pump_controller import ValvePumpController

if False:  # MYPY
    from typing import Any, Dict, List, Optional, Union
    from logging import Logger


@Inject
class ValvePumpDriver(object):  
    def __init__(self, indoor_link_id, mode, valve_pump_controller=INJECTED):  # type: (int, str, ValvePumpController) -> None
        self._link_id = indoor_link_id
        self._valve_pump_controller = valve_pump_controller
        self._valve_ids = []  # type: List[int]
        self._mode = mode  # temporary include mode



    def steer(self, percentage):  # type: (int) -> None
        if len(self._valve_ids) > 0:
            self._valve_pump_controller.steer(percentage=percentage, valve_ids=self._valve_ids)



    @property
    def is_ready(self): # type: () -> bool
        # return true if any valve of this cluster is open
        for valve_id in self._valve_ids:
            if self._valve_pump_controller.is_valve_open(valve_id=valve_id, percentage=10) is True:
                return True
        return False



    def update_from_db(self):  # type: () -> None
        # update controller from database
        self._valve_pump_controller.update_from_db()
        
        # fetch links between valves and indoor units
        with Database.get_session() as db:
            indoor_link_valves = db.query(IndoorLinkValves).filter_by(thermostat_link_id=self._link_id).filter_by(mode=self._mode).all()
            valve_ids = []
            for indoor_link_valve in indoor_link_valves:
                valve_ids.append(indoor_link_valve.valve_id)
            self._valve_ids = valve_ids
