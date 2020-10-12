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
from ioc import Inject, INJECTED
from serial_utils import CommunicationTimedOutException
from gateway.models import ThermostatGroup

if False:  # MYPY
    from typing import Optional

logger = logging.getLogger('openmotics')


@Inject
class ThermostatPid(object):

    DEFAULT_KP = 5.0
    DEFAULT_KI = 0.0
    DEFAULT_KD = 2.0

    def __init__(self, thermostat, pump_valve_controller, gateway_api=INJECTED):
        self._gateway_api = gateway_api
        self._pump_valve_controller = pump_valve_controller
        self._thermostat_change_lock = Lock()
        self._heating_valve_numbers = []
        self._cooling_valve_numbers = []
        self._report_state_callbacks = []
        self._pid = None
        self._thermostat = None
        self._mode = None
        self._active_preset = None
        self._current_temperature = None
        self._errors = 0
        self._current_steering_power = None  # type: Optional[int]
        self._current_enabled = None  # type: Optional[bool]
        self._current_preset_type = None  # type: Optional[str]
        self._current_setpoint = None  # type: Optional[float]
        self.update_thermostat(thermostat)

    @property
    def enabled(self):
        # 1. PID loop is initialized
        # 2. Sensor is valid
        # 3. Outputs configured (heating or cooling)
        if self._mode is None or self._pid is None:
            return False
        if self._active_preset is None:
            return False
        if self._thermostat.sensor == 255:
            return False
        if len(self._heating_valve_numbers) == 0 and len(self._cooling_valve_numbers) == 0:
            return False
        if not self._thermostat.thermostat_group.on:
            return False
        if self._errors > 5:
            return False
        return True

    @property
    def valve_numbers(self):
        return self.heating_valve_numbers + self.cooling_valve_numbers

    @property
    def heating_valve_numbers(self):
        return self._heating_valve_numbers

    @property
    def cooling_valve_numbers(self):
        return self._cooling_valve_numbers

    def update_thermostat(self, thermostat):
        with self._thermostat_change_lock:
            # cache these values to avoid DB lookups on every tick
            self._mode = thermostat.thermostat_group.mode
            self._active_preset = thermostat.active_preset

            self._heating_valve_numbers = [valve.number for valve in thermostat.heating_valves]
            self._cooling_valve_numbers = [valve.number for valve in thermostat.cooling_valves]

            if thermostat.thermostat_group.mode == ThermostatGroup.Modes.HEATING:
                pid_p = thermostat.pid_heating_p if thermostat.pid_heating_p is not None else self.DEFAULT_KP
                pid_i = thermostat.pid_heating_i if thermostat.pid_heating_i is not None else self.DEFAULT_KI
                pid_d = thermostat.pid_heating_d if thermostat.pid_heating_d is not None else self.DEFAULT_KD
                setpoint = self._active_preset.heating_setpoint if self._active_preset is not None else 14.0
            else:
                pid_p = thermostat.pid_cooling_p if thermostat.pid_cooling_p is not None else self.DEFAULT_KP
                pid_i = thermostat.pid_cooling_i if thermostat.pid_cooling_i is not None else self.DEFAULT_KI
                pid_d = thermostat.pid_cooling_d if thermostat.pid_cooling_d is not None else self.DEFAULT_KD
                setpoint = self._active_preset.cooling_setpoint if self._active_preset is not None else 30.0

            if self._pid is None:
                self._pid = PID(pid_p, pid_i, pid_d, setpoint=setpoint)
            else:
                self._pid.tunings = (pid_p, pid_i, pid_d)
                self._pid.setpoint = setpoint
            self._pid.output_limits = (-100, 100)
            self._thermostat = thermostat
            self._errors = 0

    @property
    def thermostat(self):
        return self._thermostat

    def subscribe_state_changes(self, callback):
        """
        Subscribes a callback to generic events
        :param callback: the callback to call
        """
        self._report_state_callbacks.append(callback)

    def report_state_change(self):
        # TODO: Only invoke callback if change occurred
        for callback in self._report_state_callbacks:
            callback(self.number, self._active_preset.type, self.setpoint, self.current_temperature,
                     self.get_active_valves_percentage(), self.thermostat.room)

    def tick(self):
        if self.enabled != self._current_enabled:
            logger.info('Thermostat {0}: {1}abled in {2} mode'.format(self.thermostat.number, 'En' if self.enabled else 'Dis', self._mode))
            self._current_enabled = self.enabled

        if not self.enabled:
            self.switch_off()
            return

        if self._current_preset_type != self._active_preset.type or self._current_setpoint != self._pid.setpoint:
            logger.info('Thermostat {0}: Preset {1} with setpoint {2}'
                        .format(self.thermostat.number, self._active_preset.type, self._pid.setpoint))
            self._current_preset_type = self._active_preset.type
            self._current_setpoint = self._pid.setpoint

        try:
            current_temperature = None  # type: Optional[float]
            if self.thermostat.sensor is not None:
                current_temperature = self._gateway_api.get_sensor_temperature_status(self.thermostat.sensor.number)
            if current_temperature is not None:
                self._current_temperature = current_temperature
            else:
                # Keep using old temperature reading and count the errors
                logger.warning('Thermostat {0}: Could not read current temperature, use last value of {1}'
                               .format(self.thermostat.number, self._current_temperature))
                self._errors += 1

            if self._current_temperature is not None:
                output_power = self._pid(self._current_temperature)
            else:
                logger.error('Thermostat {0}: No known current temperature. Cannot calculate desired output'
                             .format(self.thermostat.number))
                self._errors += 1
                output_power = 0

            # Heating needed while in cooling mode OR cooling needed while in heating mode
            # -> no active airon required, rely on losses/gains of system to reach equilibrium
            if ((self._mode == ThermostatGroup.Modes.COOLING and output_power > 0) or
                (self._mode == ThermostatGroup.Modes.HEATING and output_power < 0)):
                output_power = 0
            self.steer(output_power)
            self.report_state_change()
        except CommunicationTimedOutException as ex:
            logger.error('Thermostat {0}: Error in PID tick'.format(self.thermostat.number))
            self._errors += 1

    def get_active_valves_percentage(self):
        return [self._pump_valve_controller.get_valve_driver(valve.number).percentage for valve in self.thermostat.active_valves]

    @property
    def errors(self):
        return self._errors

    @property
    def number(self):
        return self.thermostat.number

    @property
    def setpoint(self):
        return self._pid.setpoint

    @property
    def current_temperature(self):
        return self._current_temperature

    def steer(self, power):
        if self._current_steering_power != power:
            logger.info('Thermostat {0}: Steer to {1} '.format(self.thermostat.number, power))
            self._current_steering_power = power

        # Configure valves and set desired opening
        # TODO: Check union to avoid opening same valve_numbers in heating and cooling
        if power > 0:
            self._pump_valve_controller.set_valves(0, self.cooling_valve_numbers, mode=self.thermostat.valve_config)
            self._pump_valve_controller.set_valves(power, self.heating_valve_numbers, mode=self.thermostat.valve_config)
        else:
            power = abs(power)
            self._pump_valve_controller.set_valves(0, self.heating_valve_numbers, mode=self.thermostat.valve_config)
            self._pump_valve_controller.set_valves(power, self.cooling_valve_numbers, mode=self.thermostat.valve_config)

        # Effectively steer pumps and valves according to needs
        self._pump_valve_controller.steer()

    def switch_off(self):
        self.steer(0)

    @property
    def kp(self):
        return self._pid.kp

    @kp.setter
    def kp(self, kp):
        self._pid.kp = kp

    @property
    def ki(self):
        return self._pid.ki

    @ki.setter
    def ki(self, ki):
        self._pid.ki = ki

    @property
    def kd(self):
        return self._pid.kd

    @kd.setter
    def kd(self, kd):
        self._pid.kd = kd
