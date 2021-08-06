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
import time

from gateway.daemon_thread import DaemonThread, DaemonThreadWait
from gateway.dto import RTD10DTO, GlobalRTD10DTO, PumpGroupDTO, \
    ThermostatAircoStatusDTO, ThermostatDTO, ThermostatGroupDTO, \
    ThermostatGroupStatusDTO, ThermostatStatusDTO, ThermostatScheduleDTO
from gateway.events import GatewayEvent
from gateway.exceptions import CommunicationFailure
from gateway.hal.master_event import MasterEvent
from gateway.models import Sensor
from gateway.pubsub import PubSub
from gateway.thermostat.master.thermostat_status_master import \
    ThermostatStatusMaster
from gateway.thermostat.thermostat_controller import ThermostatController
from ioc import INJECTED, Inject
from master.classic.master_communicator import CommunicationTimedOutException
from toolbox import Toolbox

if False:  # MYPY
    from typing import Any, List, Dict, Optional, Tuple
    from gateway.dto import OutputStatusDTO
    from gateway.hal.master_controller_classic import MasterClassicController
    from gateway.output_controller import OutputController

logger = logging.getLogger(__name__)

THERMOSTATS = 'THERMOSTATS'


class ThermostatControllerMaster(ThermostatController):
    DEFAULT_TIMINGS = ['07:00', '09:00', '17:00', '22:00']
    DEFAULT_TEMPS_HEATING = [20.0, 21.0, 16.0]
    DEFAULT_TEMPS_COOLING = [24.0, 23.0, 25.0]


    @Inject
    def __init__(self, output_controller=INJECTED, master_controller=INJECTED, pubsub=INJECTED):
        # type: (OutputController, MasterClassicController, PubSub) -> None
        super(ThermostatControllerMaster, self).__init__(output_controller)
        self._master_controller = master_controller  # classic only
        self._pubsub = pubsub

        self._monitor_thread = DaemonThread(name='thermostatctl',
                                            target=self._monitor,
                                            interval=1, delay=10)

        self._thermostat_status = ThermostatStatusMaster(on_thermostat_change=self._thermostat_changed,
                                                         on_thermostat_group_change=self._thermostat_group_changed)
        self._thermostats_original_interval = 60
        self._thermostats_interval = self._thermostats_original_interval
        self._thermostats_last_updated = 0.0
        self._thermostats_restore = 0
        self._thermostats_config = {}  # type: Dict[int, ThermostatDTO]

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.EEPROM, self._handle_master_event)

    def start(self):
        # type: () -> None
        self._monitor_thread.start()

    def stop(self):
        # type: () -> None
        self._monitor_thread.stop()

    def _handle_master_event(self, master_event):
        # type: (MasterEvent) -> None
        if master_event.type in [MasterEvent.Types.EEPROM_CHANGE]:
            self.invalidate_cache(THERMOSTATS)
            gateway_event = GatewayEvent(GatewayEvent.Types.CONFIG_CHANGE, {'type': 'thermostats'})
            self._pubsub.publish_gateway_event(PubSub.GatewayTopics.CONFIG, gateway_event)

    def _thermostat_changed(self, thermostat_id, status):
        # type: (int, Dict[str,Any]) -> None
        """ Executed by the Thermostat Status tracker when an output changed state """
        location = {'room_id': Toolbox.denonify(self._thermostats_config[thermostat_id].room, 255)}
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE,
                                     {'id': thermostat_id,
                                      'status': {'preset': status['preset'],
                                                 'current_setpoint': status['current_setpoint'],
                                                 'actual_temperature': status['actual_temperature'],
                                                 'output_0': status['output_0'],
                                                 'output_1': status['output_1']},
                                      'location': location})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    def _thermostat_group_changed(self, status):
        # type: (Dict[str,Any]) -> None
        gateway_event = GatewayEvent(GatewayEvent.Types.THERMOSTAT_GROUP_CHANGE,
                                     {'id': 0,
                                      'status': {'state': status['state'],
                                                 'mode': status['mode']},
                                      'location': {}})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)

    @staticmethod
    def check_basic_action(ret_dict):
        """ Checks if the response is 'OK', throws a ValueError otherwise. """
        if ret_dict['resp'] != 'OK':
            raise ValueError('Basic action did not return OK.')

    def increase_interval(self, object_type, interval, window):
        """ Increases a certain interval to a new setting for a given amount of time """
        if object_type == THERMOSTATS:
            self._thermostats_interval = interval
            self._thermostats_restore = time.time() + window

    def invalidate_cache(self, object_type=None):
        """
        Triggered when an external service knows certain settings might be changed in the background.
        For example: maintenance mode or module discovery
        """
        if object_type is None or object_type == THERMOSTATS:
            self._thermostats_last_updated = 0

    ################################
    # New API
    ################################

    def get_current_preset(self, thermostat_number):
        raise NotImplementedError()

    def set_current_preset(self, thermostat_number, preset_type):
        raise NotImplementedError()

    ################################
    # Legacy API
    ################################

    @staticmethod
    def _patch_thermostat(ref_thermostat, mode):  # type: (ThermostatDTO, str) -> bool
        # The parameter `ref_thermostat` is passed by reference and might be updated
        was_incorrect = False
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            schedule_dto = getattr(ref_thermostat, 'auto_{0}'.format(day))  # type: Optional[ThermostatScheduleDTO]
            if schedule_dto is None:
                schedule_dto = ThermostatScheduleDTO(None, None, None, '', '', '', '')  # Invalid
                setattr(ref_thermostat, 'auto_{0}'.format(day), schedule_dto)
            incorrect_timing = '42:30' in [schedule_dto.start_day_1, schedule_dto.end_day_1,
                                           schedule_dto.start_day_2, schedule_dto.end_day_2]
            incorrect_temps = None in [schedule_dto.temp_day_1, schedule_dto.temp_day_2, schedule_dto.temp_night]
            if incorrect_temps or incorrect_timing:
                schedule_dto.start_day_1 = ThermostatControllerMaster.DEFAULT_TIMINGS[0]
                schedule_dto.end_day_1 = ThermostatControllerMaster.DEFAULT_TIMINGS[1]
                schedule_dto.start_day_2 = ThermostatControllerMaster.DEFAULT_TIMINGS[2]
                schedule_dto.end_day_2 = ThermostatControllerMaster.DEFAULT_TIMINGS[3]
                if mode == 'heating':
                    schedule_dto.temp_day_1 = ThermostatControllerMaster.DEFAULT_TEMPS_HEATING[0]
                    schedule_dto.temp_day_2 = ThermostatControllerMaster.DEFAULT_TEMPS_HEATING[1]
                    schedule_dto.temp_night = ThermostatControllerMaster.DEFAULT_TEMPS_HEATING[2]
                else:
                    schedule_dto.temp_day_1 = ThermostatControllerMaster.DEFAULT_TEMPS_COOLING[0]
                    schedule_dto.temp_day_2 = ThermostatControllerMaster.DEFAULT_TEMPS_COOLING[1]
                    schedule_dto.temp_night = ThermostatControllerMaster.DEFAULT_TEMPS_COOLING[2]
                was_incorrect = True
        return was_incorrect

    def load_heating_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        thermostat_dto = self._master_controller.load_heating_thermostat(thermostat_id)
        thermostat_dto.sensor = self._sensor_to_orm(thermostat_dto.sensor)
        if ThermostatControllerMaster._patch_thermostat(ref_thermostat=thermostat_dto,
                                                        mode='heating'):
            # Make sure that times/temperature are always set to a valid value
            self.save_heating_thermostats([thermostat_dto])
        return thermostat_dto

    def load_heating_thermostats(self):  # type: () -> List[ThermostatDTO]
        thermostats = self._master_controller.load_heating_thermostats()
        changed_thermostat_dtos = []
        for thermostat_dto in thermostats:
            thermostat_dto.sensor = self._sensor_to_orm(thermostat_dto.sensor)
            if ThermostatControllerMaster._patch_thermostat(ref_thermostat=thermostat_dto,
                                                            mode='heating'):
                # Make sure that times/temperature are always set to a valid value
                changed_thermostat_dtos.append(thermostat_dto)
        if changed_thermostat_dtos:
            self.save_heating_thermostats(changed_thermostat_dtos)
        return thermostats

    def save_heating_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        for thermostat_dto in thermostats:
            thermostat_dto.sensor = self._sensor_to_master(thermostat_dto.sensor)
            # Make sure that times/temperature are always set to a valid value
            ThermostatControllerMaster._patch_thermostat(ref_thermostat=thermostat_dto,
                                                         mode='heating')
        self._master_controller.save_heating_thermostats(thermostats)
        self.invalidate_cache(THERMOSTATS)

    def load_cooling_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        thermostat_dto = self._master_controller.load_cooling_thermostat(thermostat_id)
        thermostat_dto.sensor = self._sensor_to_orm(thermostat_dto.sensor)
        if ThermostatControllerMaster._patch_thermostat(ref_thermostat=thermostat_dto,
                                                        mode='cooling'):
            # Make sure that times/temperature are always set to a valid value
            self.save_cooling_thermostats([thermostat_dto])
        return thermostat_dto

    def load_cooling_thermostats(self):  # type: () -> List[ThermostatDTO]
        thermostats = self._master_controller.load_cooling_thermostats()
        changed_thermostat_dtos = []
        for thermostat_dto in thermostats:
            thermostat_dto.sensor = self._sensor_to_orm(thermostat_dto.sensor)
            if ThermostatControllerMaster._patch_thermostat(ref_thermostat=thermostat_dto,
                                                            mode='cooling'):
                # Make sure that times/temperature are always set to a valid value
                changed_thermostat_dtos.append(thermostat_dto)
        self.save_cooling_thermostats(changed_thermostat_dtos)
        return thermostats

    def save_cooling_thermostats(self, thermostats):  # type: (List[ThermostatDTO]) -> None
        for thermostat_dto in thermostats:
            thermostat_dto.sensor = self._sensor_to_master(thermostat_dto.sensor)
            # Make sure that times/temperature are always set to a valid value
            ThermostatControllerMaster._patch_thermostat(ref_thermostat=thermostat_dto,
                                                         mode='cooling')
        self._master_controller.save_cooling_thermostats(thermostats)
        self.invalidate_cache(THERMOSTATS)

    def _sensor_to_orm(self, sensor_id):  # type: (Optional[int]) -> Optional[int]
        if sensor_id in (None, 240, 255):
            return sensor_id
        else:
            sensor = Sensor.select() \
                .where(Sensor.source == Sensor.Sources.MASTER) \
                .where(Sensor.physical_quantity == Sensor.PhysicalQuantities.TEMPERATURE) \
                .where(Sensor.external_id == str(sensor_id)) \
                .first()
            if sensor is None:
                logger.warning('Invalid <Sensor external_id={}> configured on thermostat'.format(sensor_id))
                return None
            else:
                return sensor.id

    def _sensor_to_master(self, sensor_id):  # type: (Optional[int]) -> Optional[int]
        if sensor_id in (None, 240, 255):
            return sensor_id
        else:
            sensor = Sensor.get(Sensor.id == sensor_id)
            if sensor.source != Sensor.Sources.MASTER:
                raise ValueError('Invalid <Sensor {}> {} for thermostats'.format(sensor_id, sensor.source))
            if sensor.physical_quantity != Sensor.PhysicalQuantities.TEMPERATURE:
                raise ValueError('Invalid <Sensor {}> {} for thermostats'.format(sensor_id, sensor.physical_quantity))
            return int(sensor.external_id)

    def load_cooling_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        return self._master_controller.load_cooling_pump_group(pump_group_id)

    def load_cooling_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        return self._master_controller.load_cooling_pump_groups()

    def save_cooling_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        self._master_controller.save_cooling_pump_groups(pump_groups)

    def load_global_rtd10(self):  # type: () -> GlobalRTD10DTO
        return self._master_controller.load_global_rtd10()

    def save_global_rtd10(self, global_rtd10):  # type: (GlobalRTD10DTO) -> None
        self._master_controller.save_global_rtd10(global_rtd10)

    def load_heating_rtd10(self, rtd10_id):  # type: (int) -> RTD10DTO
        return self._master_controller.load_heating_rtd10(rtd10_id)

    def load_heating_rtd10s(self):  # type: () -> List[RTD10DTO]
        return self._master_controller.load_heating_rtd10s()

    def save_heating_rtd10s(self, rtd10s):  # type: (List[RTD10DTO]) -> None
        self._master_controller.save_heating_rtd10s(rtd10s)

    def load_cooling_rtd10(self, rtd10_id):  # type: (int) -> RTD10DTO
        return self._master_controller.load_cooling_rtd10(rtd10_id)

    def load_cooling_rtd10s(self):  # type: () -> List[RTD10DTO]
        return self._master_controller.load_cooling_rtd10s()

    def save_cooling_rtd10s(self, rtd10s):  # type: (List[RTD10DTO]) -> None
        self._master_controller.save_cooling_rtd10s(rtd10s)

    def load_thermostat_group(self):
        # type: () -> ThermostatGroupDTO
        return self._master_controller.load_thermostat_group()

    def save_thermostat_group(self, thermostat_group):  # type: (ThermostatGroupDTO) -> None
        self._master_controller.save_thermostat_group(thermostat_group)
        self.invalidate_cache(THERMOSTATS)

    def load_heating_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        return self._master_controller.load_heating_pump_group(pump_group_id)

    def load_heating_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        return self._master_controller.load_heating_pump_groups()

    def save_heating_pump_groups(self, pump_groups):  # type: (List[PumpGroupDTO]) -> None
        self._master_controller.save_heating_pump_groups(pump_groups)

    def set_thermostat_mode(self, thermostat_on, cooling_mode=False, cooling_on=False, automatic=None, setpoint=None):
        # type: (bool, bool, bool, Optional[bool], Optional[int]) -> None
        """ Set the mode of the thermostats. """
        _ = thermostat_on  # Still accept `thermostat_on` for backwards compatibility

        # Figure out whether the system should be on or off
        set_on = False
        if cooling_mode is True and cooling_on is True:
            set_on = True
        if cooling_mode is False:
            # Heating means threshold based
            thermostat_group = self.load_thermostat_group()
            outside_sensor = Toolbox.denonify(thermostat_group.outside_sensor_id, 255)
            current_temperatures = self._master_controller.get_sensors_temperature()[:32]
            if len(current_temperatures) < 32:
                current_temperatures += [None] * (32 - len(current_temperatures))
            if len(current_temperatures) > outside_sensor:
                current_temperature = current_temperatures[outside_sensor]
                set_on = thermostat_group.threshold_temperature > current_temperature
            else:
                set_on = True

        # Calculate and set the global mode
        mode = 0
        mode |= (1 if set_on is True else 0) << 7
        mode |= 1 << 6  # multi-tenant mode
        mode |= (1 if cooling_mode else 0) << 4
        if automatic is not None:
            mode |= (1 if automatic else 0) << 3
        self._master_controller.set_thermostat_mode(mode)

        # Caclulate and set the cooling/heating mode
        cooling_heating_mode = 0
        if cooling_mode is True:
            cooling_heating_mode = 1 if cooling_on is False else 2
        self._master_controller.set_thermostat_cooling_heating(cooling_heating_mode)

        # Then, set manual/auto
        if automatic is not None:
            action_number = 1 if automatic is True else 0
            self._master_controller.set_thermostat_automatic(action_number)

        # If manual, set the setpoint if appropriate
        if automatic is False and setpoint is not None and 3 <= setpoint <= 5:
            self._master_controller.set_thermostat_all_setpoints(setpoint)

        self.invalidate_cache(THERMOSTATS)
        self.increase_interval(THERMOSTATS, interval=2, window=10)

    def set_per_thermostat_mode(self, thermostat_id, automatic, setpoint):
        # type: (int, bool, int) -> None
        """ Set the setpoint/mode for a certain thermostat. """
        if thermostat_id < 0 or thermostat_id > 31:
            raise ValueError('Thermostat_id not in [0, 31]: %d' % thermostat_id)

        if setpoint < 0 or setpoint > 5:
            raise ValueError('Setpoint not in [0, 5]: %d' % setpoint)

        if automatic:
            self._master_controller.set_thermostat_tenant_auto(thermostat_id)
        else:
            self._master_controller.set_thermostat_tenant_manual(thermostat_id)
            self._master_controller.set_thermostat_setpoint(thermostat_id, setpoint)

        self.invalidate_cache(THERMOSTATS)
        self.increase_interval(THERMOSTATS, interval=2, window=10)

    def set_airco_status(self, thermostat_id, airco_on):
        # type: (int, bool) -> None
        """ Set the mode of the airco attached to a given thermostat. """
        if thermostat_id < 0 or thermostat_id > 31:
            raise ValueError('Thermostat id not in [0, 31]: {0}'.format(thermostat_id))
        self._master_controller.set_airco_status(thermostat_id, airco_on)

    def load_airco_status(self):
        # type: () -> ThermostatAircoStatusDTO
        """ Get the mode of the airco attached to a all thermostats. """
        return self._master_controller.load_airco_status()

    @staticmethod
    def __check_thermostat(thermostat):
        """ :raises ValueError if thermostat not in range [0, 32]. """
        if thermostat not in range(0, 32):
            raise ValueError('Thermostat not in [0,32]: %d' % thermostat)

    def set_current_setpoint(self, thermostat_number, temperature=None, heating_temperature=None, cooling_temperature=None):
        # type: (int, Optional[float], Optional[float], Optional[float]) -> None
        """ Set the current setpoint of a thermostat. """
        if temperature is None:
            temperature = heating_temperature
        if temperature is None:
            temperature = cooling_temperature

        self.__check_thermostat(thermostat_number)
        self._master_controller.write_thermostat_setpoint(thermostat_number, temperature)

        self.invalidate_cache(THERMOSTATS)
        self.increase_interval(THERMOSTATS, interval=2, window=10)

    def _monitor(self):
        # type: () -> None
        """ Monitors certain system states to detect changes without events """
        try:
            # Refresh if required
            if self._thermostats_last_updated + self._thermostats_interval < time.time():
                self._refresh_thermostats()
            # Restore interval if required
            if self._thermostats_restore < time.time():
                self._thermostats_interval = self._thermostats_original_interval
        except CommunicationTimedOutException:
            logger.error('Got communication timeout during thermostat monitoring, waiting 10 seconds.')
            raise DaemonThreadWait

    def _refresh_thermostats(self):
        # type: () -> None
        """
        Get basic information about all thermostats and pushes it in to the Thermostat Status tracker
        """

        def get_automatic_setpoint(_mode):
            _automatic = bool(_mode & 1 << 3)
            return _automatic, 0 if _automatic else (_mode & 0b00000111)

        try:
            thermostat_info = self._master_controller.get_thermostats()
            thermostat_mode = self._master_controller.get_thermostat_modes()
            aircos = self._master_controller.load_airco_status()
        except CommunicationFailure:
            return

        status = {state.id: state for state in self._output_controller.get_output_statuses()}  # type: Dict[int,OutputStatusDTO]

        mode = thermostat_info['mode']
        thermostats_on = bool(mode & 1 << 7)
        cooling = bool(mode & 1 << 4)
        automatic, setpoint = get_automatic_setpoint(thermostat_mode['mode0'])

        try:
            if cooling:
                self._thermostats_config = {thermostat.id: thermostat
                                            for thermostat in self.load_cooling_thermostats()}
            else:
                self._thermostats_config = {thermostat.id: thermostat
                                            for thermostat in self.load_heating_thermostats()}
        except CommunicationFailure:
            return

        thermostats = []
        for thermostat_id in range(32):
            thermostat_dto = self._thermostats_config[thermostat_id]  # type: ThermostatDTO
            if thermostat_dto.in_use:
                t_mode = thermostat_mode['mode{0}'.format(thermostat_id)]
                t_automatic, t_setpoint = get_automatic_setpoint(t_mode)
                thermostat = {'id': thermostat_id,
                              'act': thermostat_info['tmp{0}'.format(thermostat_id)].get_temperature(),
                              'csetp': thermostat_info['setp{0}'.format(thermostat_id)].get_temperature(),
                              'outside': thermostat_info['outside'].get_temperature(),
                              'mode': t_mode,
                              'automatic': t_automatic,
                              'setpoint': t_setpoint,
                              'name': thermostat_dto.name,
                              'sensor_nr': thermostat_dto.sensor,
                              'airco': 1 if aircos.status[thermostat_id] else 0}
                for output in [0, 1]:
                    output_id = getattr(thermostat_dto, 'output{0}'.format(output))
                    output_state_dto = status.get(output_id)
                    if output_id is not None and output_state_dto is not None and output_state_dto.status:
                        thermostat['output{0}'.format(output)] = output_state_dto.dimmer
                    else:
                        thermostat['output{0}'.format(output)] = 0
                thermostats.append(thermostat)

        self._thermostat_status.full_update({'thermostats_on': thermostats_on,
                                             'automatic': automatic,
                                             'setpoint': setpoint,
                                             'cooling': cooling,
                                             'status': thermostats})
        self._thermostats_last_updated = time.time()

    def get_thermostat_status(self):
        # type: () -> ThermostatGroupStatusDTO
        """ Returns thermostat information """
        self._refresh_thermostats()  # Always return the latest information
        master_status = self._thermostat_status.get_thermostats()
        return ThermostatGroupStatusDTO(id=0,
                                        on=master_status['thermostats_on'],
                                        automatic=master_status['automatic'],
                                        setpoint=master_status['setpoint'],
                                        cooling=master_status['cooling'],
                                        statusses=[ThermostatStatusDTO(id=thermostat['id'],
                                                                       actual_temperature=thermostat['act'],
                                                                       setpoint_temperature=thermostat['csetp'],
                                                                       outside_temperature=thermostat['outside'],
                                                                       mode=thermostat['mode'],
                                                                       automatic=thermostat['automatic'],
                                                                       setpoint=thermostat['setpoint'],
                                                                       name=thermostat['name'],
                                                                       sensor_id=thermostat['sensor_nr'],
                                                                       airco=thermostat['airco'],
                                                                       output_0_level=thermostat['output0'],
                                                                       output_1_level=thermostat['output1'])
                                                   for thermostat in master_status['status']])
        return self._thermostat_status.get_thermostats()
