import logging
from ioc import INJECTED, Inject
from gateway.models import Database, Output, HvacOutputLink
from gateway.dto.hvac_driver import HvacContactDTO

if False:  # MYPY
    from typing import Dict, List, Optional, Set
    from gateway.output_controller import OutputController
    from gateway.sensor_controller import SensorController

logger = logging.getLogger(__name__)

# general class for hvac drivers
class HvacDriverParent(object):
    def __init__(self, hvac_id):
        self._hvac_id      = hvac_id  # TODO: currently hvac_id is the id of the thermostat group
        self._old_mode     = None  # remember previous state to not spam the output with changes
        self._old_delta_t  = None  # remember previous state to not spam the output with changes
        self._old_setpoint = None  # remember previous state to not spam the output with changes


    def _is_updated(self, mode, delta_t=None, setpoint=None):  # type: (str, float, float) -> bool
        if mode is None:
            logger.error('Steering hvac (id: {}) with mode None is not allowed '.format(self._hvac_id))

        # if no new information is provided, return false
        if mode == self._old_mode and delta_t == self._old_delta_t and setpoint == self._old_setpoint:
            return False

        self._old_mode     = mode
        self._old_delta_t  = delta_t
        self._old_setpoint = setpoint

        return True

    def steer(self, mode, delta_t=None, setpoint=None):  # type: (str, Optional[float], Optional[float]) -> None
        raise NotImplementedError()


# class for driving hvac contacts (switching modes)
@Inject
class HvacContactDriver(HvacDriverParent):
    def __init__(self, hvac_id, output_controller=INJECTED):
        super(HvacContactDriver, self).__init__(hvac_id)
        self._output_controller = output_controller
        self._output_list = []  # list of dto's with output information


    def _update_from_database(self):
        with Database.get_session() as db:
            hvac_output_links = db.query(HvacOutputLink).filter_by(hvac_id=self._hvac_id).all()
        if hvac_output_links is None:
            return
        new_output_list = []
        for hvac_output_link in hvac_output_links:
            new_output = HvacContactDTO(
                    output_id = hvac_output_link.output_id,
                    mode      = hvac_output_link.mode,
                    value     = hvac_output_link.value
                )
            new_output_list.append(new_output)
        self._output_list = new_output_list


    # change value of outputs according to setting fetched from database
    def steer(self, mode, delta_t=None, setpoint=None):  # type: (str, Optional[float], Optional[float]) -> None
        # todo: take into account incremental steps        
        if self._is_updated(mode, delta_t, setpoint) == False:  # do nothing if there is no change
            return

        if len(self._output_list) < 1:
            logger.debug("outputs need to be linked to hvac unit with id: {} ".format(self._hvac_id))
            return

        for output in self._output_list:
            if output.mode != mode:
                continue

            value = output.value
            value = max(0, min(value, 100))  # clamping on 0-100
            with Database.get_session() as db:
                output_nr = db.query(Output).filter_by(id=output.output_id).one().number
            self._output_controller.set_output_status(
                                                        output_id=output_nr, 
                                                        is_on=value>0, 
                                                        dimmer=value
                                                    )
