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

from simple_pid import PID

from gateway.dto import ThermostatStatusDTO
from gateway.enums import ThermostatState
from gateway.models import Database, Thermostat, ThermostatGroup, IndoorLinkValves
from gateway.valve_pump.valve_pump_driver import ValvePumpDriver
from ioc import INJECTED, Inject
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from typing import Callable, List, Optional
    from gateway.thermostat.gateway.pump_valve_controller import PumpValveController
    from gateway.sensor_controller import SensorController

logger = logging.getLogger(__name__)


@Inject
class ThermostatPid(object):
    DEFAULT_KP = 5.0
    DEFAULT_KI = 0.0
    DEFAULT_KD = 2.0

    def __init__(self, thermostat, valve_pump_controller=INJECTED, sensor_controller=INJECTED):
        # type: (Thermostat, PumpValveController, SensorController) -> None
        self._sensor_controller = sensor_controller
        self._pump_valve_controller = valve_pump_controller  # todo: this is only here to update the status of valve positions, will be changed further down the line
        self._thermostat_change_lock = Lock()
        self._sensor_id = None  # type: Optional[int]
        self._heating_valve_ids = []  # type: List[int]
        self._cooling_valve_ids = []  # type: List[int]
        self._report_state_callbacks = []  # type: List[Callable[[int, str, float, Optional[float], List[int], int, str, str], None]]
        self._number = thermostat.number
        self._mode = thermostat.group.mode
        self._state = thermostat.state
        self._valve_config = thermostat.valve_config
        self._active_preset_type = thermostat.active_preset.type
        self._pid = PID(Kp=ThermostatPid.DEFAULT_KP,
                        Ki=ThermostatPid.DEFAULT_KI,
                        Kd=ThermostatPid.DEFAULT_KD)
        self._current_temperature = None  # type: Optional[float]
        self._errors = 0
        self._current_steering_power = None  # type: Optional[int]
        self._current_enabled = None  # type: Optional[bool]
        self._current_setpoint = None  # type: Optional[float]
        self._driver_heating = None  # type: Optional[ValvePumpDriver]
        self._driver_cooling = None  # type: Optional[ValvePumpDriver]

    @property
    def enabled(self):  # type: () -> bool
        # 1. PID loop is initialized
        # 2. Sensor is valid
        # 3. Outputs configured (heating or cooling)
        if self._sensor_id is None:
            return False
        if len(self._heating_valve_ids) == 0 and len(self._cooling_valve_ids) == 0:
            return False
        if self._state != ThermostatState.ON:
            return False
        if self._errors > 5:
            return False
        return True

    @property
    def valve_ids(self):  # type: () -> List[int]
        return self._heating_valve_ids + self._cooling_valve_ids

    @property
    def current_temperature(self):  # type: () -> Optional[float]
        return self._current_temperature

    def update_thermostat(self):  # type: () -> None
        with self._thermostat_change_lock:
            with Database.get_session() as db:
                thermostat = db.query(Thermostat).filter_by(number=self._number).one()  # type: Thermostat
                # cache these values to avoid DB lookups on every tick
                self._mode = thermostat.group.mode
                self._state = thermostat.state
                self._valve_config = thermostat.valve_config
                self._active_preset_type = thermostat.active_preset.type

                self._sensor_id = thermostat.sensor.id if thermostat.sensor else None
                self._heating_valve_ids = [x.valve_id for x in thermostat.heating_valve_associations]
                self._cooling_valve_ids = [x.valve_id for x in thermostat.cooling_valve_associations]

                if thermostat.group.mode == ThermostatGroup.Modes.HEATING:
                    pid_p = thermostat.pid_heating_p if thermostat.pid_heating_p is not None else self.DEFAULT_KP
                    pid_i = thermostat.pid_heating_i if thermostat.pid_heating_i is not None else self.DEFAULT_KI
                    pid_d = thermostat.pid_heating_d if thermostat.pid_heating_d is not None else self.DEFAULT_KD
                    setpoint = thermostat.active_preset.heating_setpoint
                else:
                    pid_p = thermostat.pid_cooling_p if thermostat.pid_cooling_p is not None else self.DEFAULT_KP
                    pid_i = thermostat.pid_cooling_i if thermostat.pid_cooling_i is not None else self.DEFAULT_KI
                    pid_d = thermostat.pid_cooling_d if thermostat.pid_cooling_d is not None else self.DEFAULT_KD
                    setpoint = thermostat.active_preset.cooling_setpoint

                # create the driver if not exist
                if self._driver_heating is None:
                    self._driver_heating = ValvePumpDriver(thermostat.id, 'heating')
                if self._driver_cooling is None:
                    self._driver_cooling = ValvePumpDriver(thermostat.id, 'cooling')

                # update the driver if exist
                if self._driver_heating is not None:
                    self._driver_heating.update_from_db()
                if self._driver_cooling is not None:
                    self._driver_cooling.update_from_db()

            self._pid.tunings = (pid_p, pid_i, pid_d)
            self._pid.setpoint = setpoint
            self._pid.output_limits = (-100, 100)
            self._errors = 0


    @property
    def steering_power(self):  # type: () -> Optional[int]
        return self._current_steering_power

    def subscribe_state_changes(self, callback):
        # type: (Callable[[int, str, float, Optional[float], List[int], int, str, str], None]) -> None
        self._report_state_callbacks.append(callback)

    def report_state_change(self):  # type: () -> None
        # TODO: Only invoke callback if change occurred
        status = self.get_status()
        for callback in self._report_state_callbacks:
            callback(*status)

    def get_status(self):
        return (self._number, self._active_preset_type, self.setpoint, self._current_temperature,
                self.get_active_valves_percentage(), self._current_steering_power or 0,
                self._state, self._mode)

    def _get_current_temperature_value(self):
        # in the future we might combine multiple sensors, for now we only support one sensor per thermostat
        if self._sensor_id is not None:
            status = self._sensor_controller.get_sensor_status(self._sensor_id)
            if status is not None and status.value is not None:
                return status.value
        raise ValueError('Could not get sensor value')

    def tick(self):  # type: () -> bool
        if self.enabled != self._current_enabled:
            logger.info('Thermostat {0}: {1}abled in {2} mode'.format(self._number, 'En' if self.enabled else 'Dis', self._mode))
            self._current_enabled = self.enabled

        # Always try to get the latest value for the PID loop
        try:
            self._current_temperature = self._get_current_temperature_value()
        except ValueError:
            # Keep using old temperature reading and count the errors
            logger.warning('Thermostat {0}: Could not read current temperature, use last value of {1}'
                           .format(self._number, self._current_temperature))
            self._errors += 1

        if not self.enabled:
            self.steer(0)
            self.report_state_change()
            return False

        if self._current_setpoint != self._pid.setpoint:
            logger.info('Thermostat {0}: Preset {1} setpoint {2} -> {3}'
                        .format(self._number, self._active_preset_type, self._current_setpoint, self._pid.setpoint))
            self._current_setpoint = self._pid.setpoint

        try:
            if self._current_temperature is not None:
                output_power = self._pid(self._current_temperature)
            else:
                logger.error('Thermostat {0}: No known current temperature. Cannot calculate desired output'
                             .format(self._number))
                self._errors += 1
                output_power = 0

            # Heating needed while in cooling mode OR cooling needed while in heating mode
            # -> no active airon required, rely on losses/gains of system to reach equilibrium
            if ((self._mode == ThermostatGroup.Modes.COOLING and output_power > 0) or
                    (self._mode == ThermostatGroup.Modes.HEATING and output_power < 0)):
                output_power = 0
            self.steer(output_power)
            self.report_state_change()
            return True
        except CommunicationTimedOutException:
            logger.error('Thermostat {0}: Error in PID tick'.format(self._number))
            self._errors += 1
            return False

    def get_active_valves_percentage(self):  # type: () -> List[int]
        valve_ids = getattr(self, '_{0}_valve_ids'.format(self._mode))
        return [self._pump_valve_controller.get_valve_driver(x).percentage for x in valve_ids]

    @property
    def setpoint(self):  # type: () -> float
        return self._pid.setpoint

    def steer(self, power):  # type: (int) -> None
        if self._current_steering_power != power:
            logger.info('Thermostat {0}: Steer to {1} '.format(self._number, power))
            self._current_steering_power = power
        else:
            return

        # Steer drivers
        if self._driver_heating is None or self._driver_cooling is None:
            return

        if power > 0:
            self._driver_heating.steer(power)
            self._driver_cooling.steer(0)
        else:
            power = abs(power)
            self._driver_heating.steer(0)
            self._driver_cooling.steer(power)


    @property
    def kp(self):  # type: () -> float
        return self._pid.Kp

    @kp.setter
    def kp(self, kp):  # type: (float) -> None
        self._pid.Kp = kp

    @property
    def ki(self):  # type: () -> float
        return self._pid.Ki

    @ki.setter
    def ki(self, ki):  # type: (float) -> None
        self._pid.Ki = ki

    @property
    def kd(self):  # type: () -> float
        return self._pid.Kd

    @kd.setter
    def kd(self, kd):  # type: (float) -> None
        self._pid.Kd = kd

    def __repr__(self):
        return '<Thermostat PID {0}>'.format(self._number)
