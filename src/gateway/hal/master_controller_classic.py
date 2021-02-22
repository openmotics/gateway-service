# Copyright (C) 2019 OpenMotics BV
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
Module for communicating with the Master
"""
from __future__ import absolute_import

import functools
import logging
import re
import subprocess
import time
from datetime import datetime
from threading import Lock, Timer

import six

from gateway.daemon_thread import DaemonThread, DaemonThreadWait
from gateway.dto import GroupActionDTO, InputDTO, OutputDTO, PulseCounterDTO, \
    SensorDTO, ShutterDTO, ShutterGroupDTO, ThermostatDTO, ModuleDTO, \
    ThermostatGroupDTO, ThermostatAircoStatusDTO, PumpGroupDTO, \
    GlobalRTD10DTO, RTD10DTO
from gateway.enums import ShutterEnums
from gateway.exceptions import UnsupportedException
from gateway.hal.mappers_classic import GroupActionMapper, InputMapper, \
    OutputMapper, PulseCounterMapper, SensorMapper, ShutterGroupMapper, \
    ShutterMapper, ThermostatMapper, ThermostatGroupMapper, PumpGroupMapper, \
    GlobalRTD10Mapper, RTD10Mapper
from gateway.hal.master_controller import CommunicationFailure, \
    MasterController
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject
from master.classic import eeprom_models, master_api
from master.classic.eeprom_controller import EepromAddress, EepromController
from master.classic.eeprom_models import CanLedConfiguration, \
    CoolingPumpGroupConfiguration, DimmerConfiguration, \
    GlobalRTD10Configuration, GlobalThermostatConfiguration, \
    PumpGroupConfiguration, RTD10CoolingConfiguration, \
    RTD10HeatingConfiguration, ScheduledActionConfiguration, \
    StartupActionConfiguration, ThermostatConfiguration, CoolingConfiguration
from master.classic.inputs import InputStatus
from master.classic.master_communicator import BackgroundConsumer, \
    MasterCommunicator, MasterUnavailable
from master.classic.master_heartbeat import MasterHeartbeat
from master.classic.slave_updater import bootload_modules
from master.classic.validationbits import ValidationBitStatus
from serial_utils import CommunicationTimedOutException
from toolbox import Toolbox

if False:  # MYPY
    from typing import Any, Dict, List, Literal, Optional, Tuple, Union
    from serial import Serial

    HEALTH = Literal['success', 'unstable', 'failure']

logger = logging.getLogger("openmotics")


def communication_enabled(f):
    @functools.wraps(f)
    def wrapper(instance, *args, **kwargs):
        if not instance._communication_enabled:
            raise MasterUnavailable()
        return f(instance, *args, **kwargs)
    return wrapper


class MasterClassicController(MasterController):

    @Inject
    def __init__(self, master_communicator=INJECTED, eeprom_controller=INJECTED, pubsub=INJECTED):
        # type: (MasterCommunicator, EepromController, PubSub) -> None
        super(MasterClassicController, self).__init__(master_communicator)
        self._master_communicator = master_communicator  # type: MasterCommunicator
        self._eeprom_controller = eeprom_controller
        self._pubsub = pubsub
        self._heartbeat = MasterHeartbeat()
        self._plugin_controller = None  # type: Optional[Any]

        self._input_status = InputStatus(on_input_change=self._input_changed)
        self._validation_bits = ValidationBitStatus(on_validation_bit_change=self._validation_bit_changed)
        self._settings_last_updated = 0.0
        self._time_last_updated = 0.0
        self._synchronization_thread = DaemonThread(name='mastersync',
                                                    target=self._synchronize,
                                                    interval=30, delay=10)
        self._master_version = None  # type: Optional[Tuple[int, int, int]]
        self._communication_enabled = True
        self._input_interval = 300
        self._input_last_updated = 0.0
        self._input_config = {}  # type: Dict[int, InputDTO]
        self._output_config = {}  # type: Dict[int, OutputDTO]
        self._shutters_interval = 600
        self._shutters_last_updated = 0.0
        self._shutter_config = {}  # type: Dict[int, ShutterDTO]
        self._validation_bits_interval = 1800
        self._validation_bits_last_updated = 0.0

        self._discover_mode_timer = None  # type: Optional[Timer]
        self._module_log = []  # type: List[Dict[str, Any]]

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.EEPROM, self._handle_eeprom_event)
        self._pubsub.subscribe_master_events(PubSub.MasterTopics.MAINTENANCE, self._handle_maintenance_event)

        self._background_consumers_registered = False
        self._master_communicator.register_consumer(
            BackgroundConsumer(master_api.output_list(), 0, self._on_master_output_event, True)
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(master_api.module_initialize(), 0, self._process_module_initialize_message)
        )
        self._module_log_lock = Lock()

    #################
    # Private stuff #
    #################

    def _synchronize(self):
        # type: () -> None
        try:
            if not self._communication_enabled:
                logger.info('synchronization, skipped')
                return

            now = time.time()
            self._get_master_version()
            self._register_version_depending_background_consumers()
            # Validate communicator checks
            if self._time_last_updated < now - 300:
                self._check_master_time()
                self._time_last_updated = now
            if self._settings_last_updated < now - 900:
                self._check_master_settings()
                self._settings_last_updated = now
            # Refresh if required
            if self._validation_bits_last_updated + self._validation_bits_interval < now:
                self._refresh_validation_bits()
            if self._input_last_updated + self._input_interval < now:
                self._refresh_inputs()
            if self._shutters_last_updated + self._shutters_interval < now:
                self._refresh_shutter_states()
        except CommunicationTimedOutException:
            logger.error('Got communication timeout during synchronization, waiting 10 seconds.')
            raise DaemonThreadWait
        except CommunicationFailure:
            # This is an expected situation
            raise DaemonThreadWait

    def _get_master_version(self):
        # type: () -> None
        self._master_version = self.get_firmware_version()

    def _register_version_depending_background_consumers(self):
        if self._background_consumers_registered is True or self._master_version is None:
            return
        self._master_communicator.register_consumer(
            BackgroundConsumer(master_api.event_triggered(self._master_version), 0,
                               self._on_master_event, True)
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(master_api.input_list(self._master_version), 0,
                               self._on_master_input_change)
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(master_api.shutter_status(self._master_version), 0,
                               self._on_master_shutter_change)
        )
        self._background_consumers_registered = True

    @communication_enabled
    def _check_master_time(self):
        # type: () -> None
        """
        Validates the master's time with the Gateway time
        """
        status = self._master_communicator.do_command(master_api.status())
        master_time = datetime(1, 1, 1, status['hours'], status['minutes'], status['seconds'])

        now = datetime.now()
        expected_weekday = now.weekday() + 1
        expected_time = now.replace(year=1, month=1, day=1, microsecond=0)

        sync = False
        if abs((master_time - expected_time).total_seconds()) > 180:  # Allow 3 minutes difference
            sync = True
        if status['weekday'] != expected_weekday:
            sync = True

        if sync is True:
            logger.info('Time - master: {0} ({1}) - gateway: {2} ({3})'.format(
                master_time, status['weekday'], expected_time, expected_weekday)
            )
            if expected_time.hour == 0 and expected_time.minute < 15:
                logger.info('Skip setting time between 00:00 and 00:15')
            else:
                self.sync_time()

    @communication_enabled
    def _check_master_settings(self):
        # type: () -> None
        """
        Checks master settings such as:
        * Enable async messages
        * Enable multi-tenancy
        * Enable 32 thermostats
        * Turn on all leds
        """
        eeprom_data = self._master_communicator.do_command(master_api.eeprom_list(),
                                                           {'bank': 0})['data']
        write = False

        if eeprom_data[11] != 255:
            logger.info('Disabling async RO messages.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 11, 'data': bytearray([255])}
            )
            write = True

        if eeprom_data[18] != 0:
            logger.info('Enabling async OL messages.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 18, 'data': bytearray([0])}
            )
            write = True

        if eeprom_data[20] != 0:
            logger.info('Enabling async IL messages.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 20, 'data': bytearray([0])}
            )
            write = True

        if eeprom_data[28] != 0:
            logger.info('Enabling async SO messages.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 28, 'data': bytearray([0])}
            )
            write = True

        thermostat_mode = eeprom_data[14]
        if thermostat_mode & 64 == 0:
            logger.info('Enabling multi-tenant thermostats.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 14, 'data': bytearray([thermostat_mode | 64])}
            )
            write = True

        if eeprom_data[59] != 32:
            logger.info('Enabling 32 thermostats.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 59, 'data': bytearray([32])}
            )
            write = True

        if eeprom_data[24] != 0:
            logger.info('Disable auto-reset thermostat setpoint')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 24, 'data': bytearray([0])}
            )
            write = True

        if eeprom_data[13] != 0:
            logger.info('Configure master startup mode to: API')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 13, 'data': bytearray([0])}
            )
            write = True

        if write:
            self._master_communicator.do_command(master_api.activate_eeprom(), {'eep': 0},
                                                 timeout=5)
        self.set_status_leds(True)

    def _handle_maintenance_event(self, master_event):
        # type: (MasterEvent) -> None
        if master_event.type == MasterEvent.Types.MAINTENANCE_EXIT:
            self._eeprom_controller.invalidate_cache()

    def _handle_eeprom_event(self, master_event):
        # type: (MasterEvent) -> None
        if master_event.type == MasterEvent.Types.EEPROM_CHANGE:
            self._invalidate_caches()

    def _on_master_event(self, event_data):  # type: (Dict[str, Any]) -> None
        """ Handle an event triggered by the master. """
        event_type = event_data.get('event_type', 0)
        if event_type == 0:  # None or 0 are both event_type for 'code'
            code = str(event_data['bytes'][0])
            if self._plugin_controller is not None:
                self._plugin_controller.process_event(code)
        elif event_type == 1:
            bit_nr = event_data['bytes'][0]
            value = bool(event_data['bytes'][1])
            self._on_master_validation_bit_change(bit_nr, value)
        else:
            logger.warning('Received unknown master event: {0}'.format(event_data))

    def _on_master_output_event(self, data):
        # type: (Dict[str,Any]) -> None
        """ Triggers when the master informs us of an Output state change """
        # Publish status of all outputs. Since the event from the master contains
        # all outputs that are currently on, the output(s) that changed can't be
        # determined here.
        state = {k: (False, None) for k, v in self._output_config.items()}
        for output_id, dimmer in data['outputs']:
            state[output_id] = (True, dimmer)
        for output_id, (status, dimmer) in state.items():
            event_data = {'id': output_id, 'status': status}
            if dimmer is not None:
                event_data['dimmer'] = dimmer
            master_event = MasterEvent(event_type=MasterEvent.Types.OUTPUT_STATUS, data=event_data)
            self._pubsub.publish_master_event(PubSub.MasterTopics.OUTPUT, master_event)

    def _invalidate_caches(self):
        # type: () -> None
        self._input_last_updated = 0.0
        self._shutters_last_updated = 0.0
        self._synchronization_thread.request_single_run()

    #######################
    # Internal management #
    #######################

    def start(self):
        # type: () -> None
        super(MasterClassicController, self).start()
        self._heartbeat.start()
        self._synchronization_thread.start()

    def stop(self):
        # type: () -> None
        self._synchronization_thread.stop()
        self._heartbeat.stop()
        super(MasterClassicController, self).stop()

    def set_plugin_controller(self, plugin_controller):
        """
        Set the plugin controller.
        :param plugin_controller: Plugin controller
        :type plugin_controller: plugins.base.PluginController
        """
        self._plugin_controller = plugin_controller

    ##############
    # Public API #
    ##############

    def get_master_online(self):
        # type: () -> bool
        return self._time_last_updated > time.time() - 900 \
            and self._heartbeat.is_online()

    def get_communicator_health(self):
        # type: () -> HEALTH
        return self._heartbeat.get_communicator_health()

    @communication_enabled
    def get_firmware_version(self):
        out_dict = self._master_communicator.do_command(master_api.status())
        return int(out_dict['f1']), int(out_dict['f2']), int(out_dict['f3'])

    # Input

    @communication_enabled
    def get_input_module_type(self, input_module_id):
        o = self._eeprom_controller.read(eeprom_models.InputConfiguration, input_module_id * 8, ['module_type'])
        return o.module_type

    def get_inputs_with_status(self):
        # type: () -> List[Dict[str,Any]]
        return self._input_status.get_inputs()

    def get_recent_inputs(self):
        # type: () -> List[int]
        return self._input_status.get_recent()

    @communication_enabled
    def load_input(self, input_id):  # type: (int) -> InputDTO
        classic_object = self._eeprom_controller.read(eeprom_models.InputConfiguration, input_id)
        if classic_object.module_type not in ['i', 'I']:  # Only return 'real' inputs
            raise TypeError('The given id {0} is not an input, but {1}'.format(input_id, classic_object.module_type))
        return InputMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_inputs(self):  # type: () -> List[InputDTO]
        return [InputMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(eeprom_models.InputConfiguration)
                if o.module_type in ['i', 'I']]  # Only return 'real' inputs

    @communication_enabled
    def save_inputs(self, inputs):  # type: (List[Tuple[InputDTO, List[str]]]) -> None
        batch = []
        for input_, fields in inputs:
            batch.append(InputMapper.dto_to_orm(input_, fields))
        self._eeprom_controller.write_batch(batch)

    @communication_enabled
    def _refresh_inputs(self):  # type: () -> None
        # 1. refresh input configuration
        self._input_config = {input_configuration.id: input_configuration
                              for input_configuration in self.load_inputs()}
        # 2. poll for latest input status
        try:
            number_of_input_modules = self._master_communicator.do_command(master_api.number_of_io_modules())['in']
            inputs = []
            for i in range(number_of_input_modules):
                # we could be dealing with e.g. a temperature module, skip those
                module_type = self.get_input_module_type(i)
                if module_type not in ['i', 'I']:
                    continue
                result = self._master_communicator.do_command(master_api.read_input_module(self._master_version), {'input_module_nr': i})
                module_status = result['input_status']
                # module_status byte contains bits for each individual input, use mask and bitshift to get status
                for n in range(8):
                    input_nr = i * 8 + n
                    input_status = module_status & (1 << n) != 0
                    data = {'input': input_nr, 'status': input_status}
                    inputs.append(data)
            self._input_status.full_update(inputs)
        except NotImplementedError as e:
            logger.error('Cannot refresh inputs: {}'.format(e))
        self._input_last_updated = time.time()

    def _on_master_input_change(self, data):
        # type: (Dict[str,Any]) -> None
        """ Triggers when the master informs us of an Input state change """
        # Update status tracker
        self._input_status.set_input(data)

    # Outputs

    @communication_enabled
    def set_output(self, output_id, state, dimmer=None, timer=None):
        if output_id is None or output_id < 0 or output_id > 240:
            raise ValueError('Output ID {0} not in range 0 <= id <= 240'.format(output_id))
        if dimmer is not None and dimmer < 0 or dimmer > 100:
            raise ValueError('Dimmer value {0} not in [0, 100]'.format(dimmer))
        if timer is not None and timer not in [150, 450, 900, 1500, 2220, 3120]:
            raise ValueError('Timer value {0} not in [150, 450, 900, 1500, 2220, 3120]'.format(timer))

        if dimmer is not None:
            master_version = self.get_firmware_version()
            if master_version >= (3, 143, 79):
                dimmer = int(0.63 * dimmer)
                self._master_communicator.do_command(
                    master_api.write_dimmer(),
                    {'output_nr': output_id, 'dimmer_value': dimmer}
                )
            else:
                dimmer = int(dimmer) / 10 * 10
                if dimmer == 0:
                    dimmer_action = master_api.BA_DIMMER_MIN
                elif dimmer == 100:
                    dimmer_action = master_api.BA_DIMMER_MAX
                else:
                    dimmer_action = getattr(master_api, 'BA_LIGHT_ON_DIMMER_{0}'.format(dimmer))
                self.do_basic_action(dimmer_action, output_id)

        if not state:
            self.do_basic_action(master_api.BA_LIGHT_OFF, output_id)
            return

        self.do_basic_action(master_api.BA_LIGHT_ON, output_id)

        if timer is not None:
            timer_action = getattr(master_api, 'BA_LIGHT_ON_TIMER_{0}_OVERRULE'.format(timer))
            self.do_basic_action(timer_action, output_id)

    @communication_enabled
    def toggle_output(self, output_id):
        if output_id is None or output_id < 0 or output_id > 240:
            raise ValueError('Output ID {0} not in range 0 <= id <= 240'.format(output_id))

        self.do_basic_action(master_api.BA_LIGHT_TOGGLE, output_id)

    @communication_enabled
    def load_output(self, output_id):  # type: (int) -> OutputDTO
        classic_object = self._eeprom_controller.read(eeprom_models.OutputConfiguration, output_id)
        output_dto = OutputMapper.orm_to_dto(classic_object)
        self._output_config[output_id] = output_dto
        return output_dto

    @communication_enabled
    def load_outputs(self):  # type: () -> List[OutputDTO]
        output_dtos = [OutputMapper.orm_to_dto(o)
                       for o in self._eeprom_controller.read_all(eeprom_models.OutputConfiguration)]
        self._output_config = {output_dto.id: output_dto for output_dto in output_dtos}
        return output_dtos

    @communication_enabled
    def save_outputs(self, outputs):  # type: (List[Tuple[OutputDTO, List[str]]]) -> None
        batch = []
        for output, fields in outputs:
            batch.append(OutputMapper.dto_to_orm(output, fields))
        self._eeprom_controller.write_batch(batch)
        for output, _ in outputs:
            if output.timer is not None:
                self._master_communicator.do_command(
                    master_api.write_timer(),
                    {'id': output.id, 'timer': output.timer}
                )

    @communication_enabled
    def load_output_status(self):
        # type: () -> List[Dict[str,Any]]
        number_of_outputs = self._master_communicator.do_command(master_api.number_of_io_modules())['out'] * 8
        output_status = []
        for i in range(number_of_outputs):
            state_data = self._master_communicator.do_command(master_api.read_output(), {'id': i})
            # Add output locked status via the validation bits
            state_data['locked'] = self._is_output_locked(state_data['id'])
            output_status.append(state_data)
        return output_status

    def _input_changed(self, input_id, status):
        # type: (int, str) -> None
        """ Executed by the Input Status tracker when an input changed state """
        input_configuration = self._input_config.get(input_id)
        if input_configuration is None:
            # An event was received from an input for which the configuration was not yet loaded. As
            # configuraion should not be loaded inside an event handler, the event is discarded.
            # TODO: Detach input even processing from event handler so it can load the configuration if needed
            return
        event_data = {'id': input_id,
                      'status': status,
                      'location': {'room_id': Toolbox.denonify(input_configuration.room, 255)}}
        master_event = MasterEvent(event_type=MasterEvent.Types.INPUT_CHANGE, data=event_data)
        self._pubsub.publish_master_event(PubSub.MasterTopics.INPUT, master_event)

    def _is_output_locked(self, output_id):
        # TODO remove self._output_config cache, this belongs in the output controller.
        output_dto = self._output_config.get(output_id)
        if output_dto is None:
            output_dto = self.load_output(output_id)
        if output_dto.lock_bit_id is not None:
            value = self._validation_bits.get_validation_bit(output_dto.lock_bit_id)
            locked = value
        else:
            locked = False
        return locked

    # Shutters

    @communication_enabled
    def shutter_up(self, shutter_id, timer=None):  # type: (int, Optional[int]) -> None
        if timer is not None:
            if self._master_version is None or self._master_version < (3, 143, 113):
                raise NotImplementedError('Shutter up with a timer is not supported on Master version {0}'.format(self._master_version))
            self.do_basic_action(master_api.BA_SHUTTER_UP, shutter_id, parameter=timer)
        else:
            self.do_basic_action(master_api.BA_SHUTTER_UP, shutter_id)

    @communication_enabled
    def shutter_down(self, shutter_id, timer=None):  # type: (int, Optional[int]) -> None
        if timer is not None:
            if self._master_version is None or self._master_version < (3, 143, 113):
                raise NotImplementedError('Shutter down with a timer is not supported on Master version {0}'.format(self._master_version))
            self.do_basic_action(master_api.BA_SHUTTER_DOWN, shutter_id, parameter=timer)
        else:
            self.do_basic_action(master_api.BA_SHUTTER_DOWN, shutter_id)

    @communication_enabled
    def shutter_stop(self, shutter_id):  # type: (int) -> None
        self.do_basic_action(master_api.BA_SHUTTER_STOP, shutter_id)

    @communication_enabled
    def load_shutter(self, shutter_id):  # type: (int) -> ShutterDTO
        classic_object = self._eeprom_controller.read(eeprom_models.ShutterConfiguration, shutter_id)
        return ShutterMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_shutters(self):  # type: () -> List[ShutterDTO]
        return [ShutterMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(eeprom_models.ShutterConfiguration)]

    @communication_enabled
    def save_shutters(self, shutters):  # type: (List[Tuple[ShutterDTO, List[str]]]) -> None
        batch = []
        for shutter, fields in shutters:
            batch.append(ShutterMapper.dto_to_orm(shutter, fields))
        self._eeprom_controller.write_batch(batch)

    @communication_enabled
    def _refresh_shutter_states(self):
        self._shutter_config = {shutter.id: shutter for shutter in self.load_shutters()}
        number_of_shutter_modules = self._master_communicator.do_command(master_api.number_of_io_modules())['shutter']
        for module_id in range(number_of_shutter_modules):
            self._update_from_master_state(
                {'module_nr': module_id,
                 'status': self._master_communicator.do_command(master_api.shutter_status(self._master_version),
                                                                {'module_nr': module_id})['status']}
            )
        self._shutters_last_updated = time.time()

    def _on_master_shutter_change(self, data):
        self._update_from_master_state(data)

    def _update_from_master_state(self, data):
        """
        Called with Master event information.
        """
        module_id = data['module_nr']
        new_state = self._interprete_output_states(module_id, data['status'])
        if new_state is None:
            return  # Failsafe for master event handler
        for i in range(4):
            shutter_id = module_id * 4 + i
            event_data = {'id': shutter_id,
                          'status': new_state[i],
                          'location': {'room_id': self._shutter_config[shutter_id].room}}
            master_event = MasterEvent(event_type=MasterEvent.Types.SHUTTER_CHANGE, data=event_data)
            self._pubsub.publish_master_event(PubSub.MasterTopics.SHUTTER, master_event)

    def _interprete_output_states(self, module_id, output_states):
        states = []
        for i in range(4):
            shutter_id = module_id * 4 + i
            if shutter_id not in self._shutter_config:
                return  # Failsafe for master event handler

            # first_up = 0 -> output 0 = up, output 1 = down
            # first_up = 1 -> output 0 = down, output 1 = up
            first_up = 0 if self._shutter_config[shutter_id].up_down_config == 0 else 1

            up = (output_states >> (i * 2 + (1 - first_up))) & 0x1
            down = (output_states >> (i * 2 + first_up)) & 0x1

            if up == 1 and down == 0:
                states.append(ShutterEnums.State.GOING_UP)
            elif down == 1 and up == 0:
                states.append(ShutterEnums.State.GOING_DOWN)
            else:  # Both are off or - unlikely - both are on
                states.append(ShutterEnums.State.STOPPED)

        return states

    @communication_enabled
    def shutter_group_up(self, shutter_group_id, timer=None):  # type: (int, Optional[int]) -> None
        if not (0 <= shutter_group_id <= 30):
            raise ValueError('ShutterGroup ID {0} not in range 0 <= id <= 30'.format(shutter_group_id))

        if timer is not None:
            if self._master_version is None or self._master_version < (3, 143, 113):
                raise NotImplementedError(
                    'Shutter group up with a timer is not supported on Master version {0}'.format(self._master_version))
            self.do_basic_action(master_api.BA_SHUTTER_GROUP_UP, shutter_group_id, parameter=timer)
        self.do_basic_action(master_api.BA_SHUTTER_GROUP_UP, shutter_group_id)

    @communication_enabled
    def shutter_group_down(self, shutter_group_id, timer=None):  # type: (int, Optional[int]) -> None
        if not (0 <= shutter_group_id <= 30):
            raise ValueError('ShutterGroup ID {0} not in range 0 <= id <= 30'.format(shutter_group_id))
        if timer is not None:
            if self._master_version is None or self._master_version < (3, 143, 113):
                raise NotImplementedError(
                    'Shutter group down with a timer is not supported on Master version {0}'.format(self._master_version))
            self.do_basic_action(master_api.BA_SHUTTER_GROUP_UP, shutter_group_id, parameter=timer)
        self.do_basic_action(master_api.BA_SHUTTER_GROUP_UP, shutter_group_id)

    @communication_enabled
    def shutter_group_stop(self, shutter_group_id):  # type: (int) -> None
        if not (0 <= shutter_group_id <= 30):
            raise ValueError('ShutterGroup ID {0} not in range 0 <= id <= 30'.format(shutter_group_id))
        self.do_basic_action(master_api.BA_SHUTTER_GROUP_STOP, shutter_group_id)

    @communication_enabled
    def load_shutter_group(self, shutter_group_id):  # type: (int) -> ShutterGroupDTO
        classic_object = self._eeprom_controller.read(eeprom_models.ShutterGroupConfiguration, shutter_group_id)
        return ShutterGroupMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_shutter_groups(self):  # type: () -> List[ShutterGroupDTO]
        return [ShutterGroupMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(eeprom_models.ShutterGroupConfiguration)]

    @communication_enabled
    def save_shutter_groups(self, shutter_groups):  # type: (List[Tuple[ShutterGroupDTO, List[str]]]) -> None
        batch = []
        for shutter_group, fields in shutter_groups:
            batch.append(ShutterGroupMapper.dto_to_orm(shutter_group, fields))
        self._eeprom_controller.write_batch(batch)

    # Thermostats

    @communication_enabled
    def set_thermostat_mode(self, mode):
        # type: (int) -> None
        self.do_basic_action(master_api.BA_THERMOSTAT_MODE, mode)

    @communication_enabled
    def set_thermostat_cooling_heating(self, mode):
        # type: (int) -> None
        self.do_basic_action(master_api.BA_THERMOSTAT_COOLING_HEATING, mode)

    @communication_enabled
    def set_thermostat_automatic(self, action_number):
        # type: (int) -> None
        self.do_basic_action(master_api.BA_THERMOSTAT_AUTOMATIC, action_number)

    @communication_enabled
    def set_thermostat_all_setpoints(self, setpoint):
        # type: (int) -> None
        self.do_basic_action(
            getattr(master_api, 'BA_ALL_SETPOINT_{0}'.format(setpoint)), 0
        )

    @communication_enabled
    def set_thermostat_setpoint(self, thermostat_id, setpoint):
        # type: (int, int) -> None
        self.do_basic_action(
            getattr(master_api, 'BA_ONE_SETPOINT_{0}'.format(setpoint)), thermostat_id
        )

    @communication_enabled
    def write_thermostat_setpoint(self, thermostat_id, temperature):
        # type: (int, float) -> None
        self._master_communicator.do_command(
            master_api.write_setpoint(),
            {'thermostat': thermostat_id,
             'config': 0,
             'temp': master_api.Svt.temp(temperature)}
        )

    @communication_enabled
    def set_thermostat_tenant_auto(self, thermostat_id):
        # type: (int) -> None
        self.do_basic_action(master_api.BA_THERMOSTAT_TENANT_AUTO, thermostat_id)

    @communication_enabled
    def set_thermostat_tenant_manual(self, thermostat_id):
        # type: (int) -> None
        self.do_basic_action(master_api.BA_THERMOSTAT_TENANT_MANUAL, thermostat_id)

    @communication_enabled
    def get_thermostats(self):
        # type: () -> Dict[str,Any]
        return self._master_communicator.do_command(master_api.thermostat_list())

    @communication_enabled
    def get_thermostat_modes(self):
        # type: () -> Dict[str,Any]
        return self._master_communicator.do_command(master_api.thermostat_mode_list())

    @communication_enabled
    def load_airco_status(self):
        # type: () -> ThermostatAircoStatusDTO
        data = self._master_communicator.do_command(master_api.read_airco_status_bits())
        return ThermostatAircoStatusDTO({i: data['ASB{0}'.format(i)] == 1 for i in range(32)})

    @communication_enabled
    def set_airco_status(self, thermostat_id, airco_on):
        # type: (int, bool) -> None
        self.do_basic_action(
            master_api.BA_THERMOSTAT_AIRCO_STATUS, thermostat_id + (0 if airco_on else 100)
        )

    @communication_enabled
    def load_heating_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        classic_object = self._eeprom_controller.read(eeprom_models.ThermostatConfiguration, thermostat_id)
        return ThermostatMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_heating_thermostats(self):  # type: () -> List[ThermostatDTO]
        return [ThermostatMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(eeprom_models.ThermostatConfiguration)]

    @communication_enabled
    def save_heating_thermostats(self, thermostats):  # type: (List[Tuple[ThermostatDTO, List[str]]]) -> None
        batch = []
        for thermostat, fields in thermostats:
            batch.append(ThermostatMapper.dto_to_orm(ThermostatConfiguration, thermostat, fields))
        self._eeprom_controller.write_batch(batch)

    @communication_enabled
    def load_cooling_thermostat(self, thermostat_id):  # type: (int) -> ThermostatDTO
        classic_object = self._eeprom_controller.read(eeprom_models.CoolingConfiguration, thermostat_id)
        return ThermostatMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_cooling_thermostats(self):  # type: () -> List[ThermostatDTO]
        return [ThermostatMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(eeprom_models.CoolingConfiguration)]

    @communication_enabled
    def save_cooling_thermostats(self, thermostats):  # type: (List[Tuple[ThermostatDTO, List[str]]]) -> None
        batch = []
        for thermostat, fields in thermostats:
            batch.append(ThermostatMapper.dto_to_orm(CoolingConfiguration, thermostat, fields))
        self._eeprom_controller.write_batch(batch)

    @communication_enabled
    def load_cooling_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        classic_object = self._eeprom_controller.read(CoolingPumpGroupConfiguration, pump_group_id)
        return PumpGroupMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_cooling_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        return [PumpGroupMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(CoolingPumpGroupConfiguration)]

    @communication_enabled
    def save_cooling_pump_groups(self, pump_groups):  # type: (List[Tuple[PumpGroupDTO, List[str]]]) -> None
        batch = []
        for pump_group, fields in pump_groups:
            batch.append(PumpGroupMapper.dto_to_orm(CoolingPumpGroupConfiguration, pump_group, fields))
        self._eeprom_controller.write_batch(batch)

    @communication_enabled
    def load_global_rtd10(self):  # type: () -> GlobalRTD10DTO
        classic_object = self._eeprom_controller.read(GlobalRTD10Configuration)
        return GlobalRTD10Mapper.orm_to_dto(classic_object)

    @communication_enabled
    def save_global_rtd10(self, global_rtd10):  # type: (Tuple[GlobalRTD10DTO, List[str]]) -> None
        global_rtd10_dto, fields = global_rtd10
        classic_object = GlobalRTD10Mapper.dto_to_orm(global_rtd10_dto, fields)
        self._eeprom_controller.write(classic_object)

    @communication_enabled
    def load_heating_rtd10(self, rtd10_id):  # type: (int) -> RTD10DTO
        classic_object = self._eeprom_controller.read(RTD10HeatingConfiguration, rtd10_id)
        return RTD10Mapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_heating_rtd10s(self):  # type: () -> List[RTD10DTO]
        return [RTD10Mapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(RTD10HeatingConfiguration)]

    @communication_enabled
    def save_heating_rtd10s(self, rtd10s):  # type: (List[Tuple[RTD10DTO, List[str]]]) -> None
        batch = []
        for rtd10_dto, fields in rtd10s:
            batch.append(RTD10Mapper.dto_to_orm(RTD10HeatingConfiguration, rtd10_dto, fields))
        self._eeprom_controller.write_batch(batch)

    @communication_enabled
    def load_cooling_rtd10(self, rtd10_id):  # type: (int) -> RTD10DTO
        classic_object = self._eeprom_controller.read(RTD10CoolingConfiguration, rtd10_id)
        return RTD10Mapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_cooling_rtd10s(self):  # type: () -> List[RTD10DTO]
        return [RTD10Mapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(RTD10CoolingConfiguration)]

    @communication_enabled
    def save_cooling_rtd10s(self, rtd10s):  # type: (List[Tuple[RTD10DTO, List[str]]]) -> None
        batch = []
        for rtd10_dto, fields in rtd10s:
            batch.append(RTD10Mapper.dto_to_orm(RTD10CoolingConfiguration, rtd10_dto, fields))
        self._eeprom_controller.write_batch(batch)

    @communication_enabled
    def load_thermostat_group(self):
        # type: () -> ThermostatGroupDTO
        classic_object = self._eeprom_controller.read(GlobalThermostatConfiguration)
        return ThermostatGroupMapper.orm_to_dto(classic_object)

    @communication_enabled
    def save_thermostat_group(self, thermostat_group):
        # type: (Tuple[ThermostatGroupDTO, List[str]]) -> None
        thermostat_group_dto, fields = thermostat_group
        if thermostat_group_dto.outside_sensor_id is None:
            # Works around a master issue where the thermostat would be turned off in case there is no outside sensor.
            thermostat_group_dto.threshold_temperature = 50
        classic_object = ThermostatGroupMapper.dto_to_orm(thermostat_group_dto, fields)
        self._eeprom_controller.write(classic_object)

    @communication_enabled
    def load_heating_pump_group(self, pump_group_id):  # type: (int) -> PumpGroupDTO
        classic_object = self._eeprom_controller.read(PumpGroupConfiguration, pump_group_id)
        return PumpGroupMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_heating_pump_groups(self):  # type: () -> List[PumpGroupDTO]
        return [PumpGroupMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(PumpGroupConfiguration)]

    @communication_enabled
    def save_heating_pump_groups(self, pump_groups):  # type: (List[Tuple[PumpGroupDTO, List[str]]]) -> None
        batch = []
        for pump_group, fields in pump_groups:
            batch.append(PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, pump_group, fields))
        self._eeprom_controller.write_batch(batch)

    # Virtual modules

    @communication_enabled
    def add_virtual_output_module(self):
        # type: () -> None
        self._master_communicator.do_command(master_api.add_virtual_module(), {'vmt': 'o'})
        self._broadcast_module_discovery()

    @communication_enabled
    def add_virtual_dim_control_module(self):
        # type: () -> None
        self._master_communicator.do_command(master_api.add_virtual_module(), {'vmt': 'd'})
        self._broadcast_module_discovery()

    @communication_enabled
    def add_virtual_input_module(self):
        # type: () -> None
        self._master_communicator.do_command(master_api.add_virtual_module(), {'vmt': 'i'})
        self._broadcast_module_discovery()

    @communication_enabled
    def add_virtual_sensor_module(self):
        # type: () -> None
        raise UnsupportedException()

    # Generic

    @communication_enabled
    def get_status(self):
        """ Get the status of the Master.

        :returns: dict with 'time' (HH:MM), 'date' (DD:MM:YYYY), 'mode', 'version' (a.b.c)
                  and 'hw_version' (hardware version)
        """
        out_dict = self._master_communicator.do_command(master_api.status())
        return {'time': '%02d:%02d' % (out_dict['hours'], out_dict['minutes']),
                'date': '%02d/%02d/%d' % (out_dict['day'], out_dict['month'], out_dict['year']),
                'mode': out_dict['mode'],
                'version': '%d.%d.%d' % (out_dict['f1'], out_dict['f2'], out_dict['f3']),
                'hw_version': out_dict['h']}

    @communication_enabled
    def get_modules(self):
        """ Get a list of all modules attached and registered with the master.

        :returns: Dict with:
        * 'outputs' (list of module types: O,R,D),
        * 'inputs' (list of input module types: I,T,L,C)
        * 'shutters' (List of modules types: S).
        """
        mods = self._master_communicator.do_command(master_api.number_of_io_modules())

        inputs = []
        outputs = []
        shutters = []
        can_inputs = []

        for i in range(mods['in']):
            ret = self._master_communicator.do_command(
                master_api.read_eeprom(),
                {'bank': 2 + i, 'addr': 252, 'num': 1}
            )
            module_type = chr(ret['data'][0])
            is_can = module_type == 'C'
            ret = self._master_communicator.do_command(
                master_api.read_eeprom(),
                {'bank': 2 + i, 'addr': 0, 'num': 1}
            )
            module_type = chr(ret['data'][0])
            if is_can:
                can_inputs.append(module_type)
            else:
                inputs.append(module_type)

        for i in range(mods['out']):
            ret = self._master_communicator.do_command(
                master_api.read_eeprom(),
                {'bank': 33 + i, 'addr': 0, 'num': 1}
            )
            module_type = chr(ret['data'][0])
            outputs.append(module_type)

        for shutter in range(mods['shutter']):
            shutters.append('S')

        if len(can_inputs) > 0 and 'C' not in can_inputs:
            can_inputs.append('C')  # First CAN enabled installations didn't had this in the eeprom yet

        return {'outputs': outputs, 'inputs': inputs, 'shutters': shutters, 'can_inputs': can_inputs}

    @staticmethod
    def _format_address(address_bytes):
        return '{0:03}.{1:03}.{2:03}.{3:03}'.format(address_bytes[0],
                                                    address_bytes[1],
                                                    address_bytes[2],
                                                    address_bytes[3])

    @communication_enabled
    def get_modules_information(self):  # type: () -> List[ModuleDTO]
        """ Gets module information """

        def get_master_version(_module_address):
            try:
                _module_version = self._master_communicator.do_command(master_api.get_module_version(),
                                                                       {'addr': _module_address.bytes},
                                                                       extended_crc=True,
                                                                       timeout=5)
                _firmware_version = '{0}.{1}.{2}'.format(_module_version['f1'], _module_version['f2'], _module_version['f3'])
                return True, _module_version['hw_version'], _firmware_version
            except CommunicationTimedOutException:
                return False, None, None

        information = []
        module_type_lookup = {'c': ModuleDTO.ModuleType.CAN_CONTROL,
                              't': ModuleDTO.ModuleType.SENSOR,
                              'i': ModuleDTO.ModuleType.INPUT,
                              'o': ModuleDTO.ModuleType.OUTPUT,
                              'r': ModuleDTO.ModuleType.SHUTTER,
                              'd': ModuleDTO.ModuleType.DIM_CONTROL}

        no_modules = self._master_communicator.do_command(master_api.number_of_io_modules())
        for i in range(no_modules['in']):
            is_can = self._eeprom_controller.read_address(EepromAddress(2 + i, 252, 1)).bytes == bytearray(b'C')
            module_address = self._eeprom_controller.read_address(EepromAddress(2 + i, 0, 4))
            module_type_letter = chr(module_address.bytes[0]).lower()
            is_virtual = chr(module_address.bytes[0]).islower()
            formatted_address = MasterClassicController._format_address(module_address.bytes)
            hardware_type = ModuleDTO.HardwareType.PHYSICAL
            if is_virtual:
                hardware_type = ModuleDTO.HardwareType.VIRTUAL
            elif is_can and module_type_letter != 'c':
                hardware_type = ModuleDTO.HardwareType.EMULATED
            dto = ModuleDTO(source=ModuleDTO.Source.MASTER,
                            address=formatted_address,
                            module_type=module_type_lookup.get(module_type_letter),
                            hardware_type=hardware_type,
                            order=i)
            if hardware_type == ModuleDTO.HardwareType.PHYSICAL:
                dto.online, dto.hardware_version, dto.firmware_version = get_master_version(module_address)
            information.append(dto)

        for i in range(no_modules['out']):
            module_address = self._eeprom_controller.read_address(EepromAddress(33 + i, 0, 4))
            module_type_letter = chr(module_address.bytes[0]).lower()
            is_virtual = chr(module_address.bytes[0]).islower()
            formatted_address = MasterClassicController._format_address(module_address.bytes)
            dto = ModuleDTO(source=ModuleDTO.Source.MASTER,
                            address=formatted_address,
                            module_type=module_type_lookup.get(module_type_letter),
                            hardware_type=(ModuleDTO.HardwareType.VIRTUAL if is_virtual else
                                           ModuleDTO.HardwareType.PHYSICAL),
                            order=i)
            if not is_virtual:
                dto.online, dto.hardware_version, dto.firmware_version = get_master_version(module_address)
            information.append(dto)

        for i in range(no_modules['shutter']):
            module_address = self._eeprom_controller.read_address(EepromAddress(33 + i, 173, 4))
            module_type_letter = chr(module_address.bytes[0]).lower()
            is_virtual = chr(module_address.bytes[0]).islower()
            formatted_address = MasterClassicController._format_address(module_address.bytes)
            dto = ModuleDTO(source=ModuleDTO.Source.MASTER,
                            address=formatted_address,
                            module_type=module_type_lookup.get(module_type_letter),
                            hardware_type=(ModuleDTO.HardwareType.VIRTUAL if is_virtual else
                                           ModuleDTO.HardwareType.PHYSICAL),
                            order=i)
            if not is_virtual:
                dto.online, dto.hardware_version, dto.firmware_version = get_master_version(module_address)
            information.append(dto)

        return information

    def replace_module(self, old_address, new_address):  # type: (str, str) -> None
        old_address_bytes = bytearray([int(part) for part in old_address.split('.')])
        new_address_bytes = bytearray([int(part) for part in new_address.split('.')])
        no_modules = self._master_communicator.do_command(master_api.number_of_io_modules())

        amount_of_inputs = no_modules['in']
        for i in range(amount_of_inputs):
            eeprom_address = EepromAddress(2 + i, 0, 4)
            module_address = self._eeprom_controller.read_address(eeprom_address).bytes
            if module_address == old_address_bytes:
                new_module_address = self._eeprom_controller.read_address(EepromAddress(2 + amount_of_inputs - 1, 0, 4)).bytes
                if new_module_address == new_address_bytes:
                    self._eeprom_controller.write_address(eeprom_address, new_address_bytes)
                    self._eeprom_controller.write_address(EepromAddress(0, 1, 1), bytearray([amount_of_inputs - 1]))
                    self._eeprom_controller.activate()
                    logger.warn('Replaced {0} by {1}'.format(old_address, new_address))
                    return

        amount_of_outputs = no_modules['out']
        for i in range(amount_of_outputs):
            eeprom_address = EepromAddress(33 + i, 0, 4)
            module_address = self._eeprom_controller.read_address(eeprom_address).bytes
            if module_address == old_address_bytes:
                new_module_address = self._eeprom_controller.read_address(EepromAddress(33 + amount_of_outputs - 1, 0, 4)).bytes
                if new_module_address == new_address_bytes:
                    self._eeprom_controller.write_address(eeprom_address, new_address_bytes)
                    self._eeprom_controller.write_address(EepromAddress(0, 2, 1), bytearray([amount_of_outputs - 1]))
                    self._eeprom_controller.activate()
                    logger.warn('Replaced {0} by {1}'.format(old_address, new_address))
                    return

        amount_of_shutters = no_modules['shutter']
        for i in range(amount_of_shutters):
            eeprom_address = EepromAddress(33 + i, 173, 4)
            module_address = self._eeprom_controller.read_address(eeprom_address).bytes
            if module_address == old_address_bytes:
                new_module_address = self._eeprom_controller.read_address(EepromAddress(33 + amount_of_shutters - 1, 173, 4)).bytes
                if new_module_address == new_address_bytes:
                    self._eeprom_controller.write_address(eeprom_address, new_address_bytes)
                    self._eeprom_controller.write_address(EepromAddress(0, 3, 1), bytearray([amount_of_shutters - 1]))
                    self._eeprom_controller.activate()
                    logger.warn('Replaced {0} by {1}'.format(old_address, new_address))
                    return

        raise RuntimeError('Could not correctly match modules {0} and {1}'.format(old_address, new_address))

    @communication_enabled
    def flash_leds(self, led_type, led_id):
        """ Flash the leds on the module for an output/input/sensor.

        :type led_type: byte
        :param led_type: The module type: output/dimmer (0), input (1), sensor/temperatur (2).
        :type led_id: byte
        :param led_id: The id of the output/input/sensor.
        :returns: dict with 'status' ('OK').
        """
        ret = self._master_communicator.do_command(master_api.indicate(),
                                                   {'type': led_type, 'id': led_id})
        return {'status': ret['resp']}

    @communication_enabled
    def get_backup(self):
        """
        Get a backup of the eeprom of the master.

        :returns: String of bytes (size = 64kb).
        """
        retry = None
        output = bytearray()
        bank = 0
        while bank < 256:
            try:
                output += self._master_communicator.do_command(
                    master_api.eeprom_list(),
                    {'bank': bank}
                )['data']
                bank += 1
            except CommunicationTimedOutException:
                if retry == bank:
                    raise
                retry = bank
                logger.warning('Got timeout reading bank {0}. Retrying...'.format(bank))
                time.sleep(2)  # Doing heavy reads on eeprom can exhaust the master. Give it a bit room to breathe.
        return ''.join(chr(c) for c in output)

    def factory_reset(self):
        # type: () -> None
        # Wipe master EEPROM
        data = chr(255) * (256 * 256)
        self.restore(data)

    def cold_reset(self, power_on=True):
        # type: (bool) -> None
        """
        Perform a cold reset on the master. Turns the power off, waits 5 seconds and turns the power back on.
        """
        MasterClassicController._set_master_power(False)
        if power_on:
            time.sleep(5)
            MasterClassicController._set_master_power(True)
        self._master_communicator.reset_communication_statistics()

    @communication_enabled
    def raw_action(self, action, size, data=None):
        # type: (str, int, Optional[bytearray]) -> Dict[str,Any]
        """
        Send a raw action to the master.
        """
        return self._master_communicator.do_raw_action(action, size, data=data)

    @Inject
    def update_master(self, hex_filename, controller_serial=INJECTED):
        # type: (str, Serial) -> None
        try:
            self._communication_enabled = False
            self._master_communicator.update_mode_start()

            port = controller_serial.port  # type: ignore
            baudrate = str(controller_serial.baudrate)  # type: ignore
            base_command = ['/opt/openmotics/bin/AN1310cl', '-d', port, '-b', baudrate]

            logger.info('Updating master...')
            logger.info('* Enter bootloader...')
            # Setting this condition will assert a break condition on TX to which the bootloader will react.
            controller_serial.break_condition = True
            time.sleep(2)
            MasterClassicController._set_master_power(False)
            time.sleep(2)
            MasterClassicController._set_master_power(True)
            time.sleep(2)
            # After the bootloader is active, release the break condition to free up TX for subsequent communications
            controller_serial.break_condition = False
            time.sleep(2)

            logger.info('* Verify bootloader...')
            try:
                response = str(subprocess.check_output(base_command + ['-s']))
                # Expected response:
                # > Serial Bootloader AN1310 v1.05r
                # > Copyright (c) 2010-2011, Microchip Technology Inc.
                # >
                # > Using /dev/ttyO5 at 115200 bps
                # > Connecting...
                # > Bootloader Firmware v1.05
                # > PIC18F67J11 Revision 10
                match = re.findall(pattern=r'Bootloader Firmware (v[0-9]+\.[0-9]+).*(PIC.*) Revision',
                                   string=response,
                                   flags=re.DOTALL)
                if not match:
                    raise RuntimeError('Bootloader response did not match: {0}'.format(response))
                logger.debug(response)
                logger.info('  * Bootloader information: {1} bootloader {0}'.format(*match[0]))
            except subprocess.CalledProcessError as ex:
                logger.info(ex.output)
                raise

            logger.info('* Flashing...')
            try:
                response = str(subprocess.check_output(base_command + ['-p ', '-c', hex_filename]))
                logger.debug(response)
            except subprocess.CalledProcessError as ex:
                logger.info(ex.output)
                raise

            logger.info('* Verifying...')
            try:
                response = str(subprocess.check_output(base_command + ['-v', hex_filename]))
                logger.debug(response)
            except subprocess.CalledProcessError as ex:
                logger.info(ex.output)
                raise

            logger.info('* Entering application...')
            try:
                response = str(subprocess.check_output(base_command + ['-r']))
                logger.debug(response)
            except subprocess.CalledProcessError as ex:
                logger.info(ex.output)
                raise

            logger.info('Update completed')

        finally:
            self._master_communicator.update_mode_stop()
            self._communication_enabled = True

    @Inject
    def update_slave_modules(self, module_type, hex_filename, controller_serial=INJECTED):
        # type: (str, str, Serial) -> None
        self._communication_enabled = False
        try:
            bootload_modules(module_type, hex_filename)
        finally:
            self._communication_enabled = True

    @staticmethod
    def _set_master_power(on):
        with open('/sys/class/gpio/gpio44/direction', 'w') as gpio:
            gpio.write('out')
        with open('/sys/class/gpio/gpio44/value', 'w') as gpio:
            gpio.write('1' if on else '0')

    @communication_enabled
    def reset(self):
        """ Reset the master.

        :returns: emtpy dict.
        """
        self._master_communicator.do_command(master_api.reset())
        return dict()

    def power_cycle_master(self):
        self.cold_reset()
        return dict()

    @communication_enabled
    @Inject
    def power_cycle_bus(self, power_communicator=INJECTED):
        """ Turns the power of both bussed off for 5 seconds """
        self.do_basic_action(master_api.BA_POWER_CYCLE_BUS, 0)
        if power_communicator:
            power_communicator.reset_communication_statistics()  # TODO cleanup, use an event instead?

    @communication_enabled
    def restore(self, data):
        """
        Restore a backup of the eeprom of the master.

        :param data: The eeprom backup to restore.
        :type data: string of bytes (size = 64 kb).
        :returns: dict with 'output' key (contains an array with the addresses that were written).
        """
        ret = []
        (num_banks, bank_size, write_size) = (256, 256, 10)
        backup_data = bytearray(ord(c) for c in data)

        for bank in range(0, num_banks):
            current_data = self._master_communicator.do_command(master_api.eeprom_list(),
                                                                {'bank': bank})['data']
            for addr in range(0, bank_size, write_size):
                current = current_data[addr:addr + write_size]
                new = backup_data[bank * bank_size + addr: bank * bank_size + addr + len(current)]
                if new != current:
                    ret.append('B' + str(bank) + 'A' + str(addr))

                    self._master_communicator.do_command(
                        master_api.write_eeprom(),
                        {'bank': bank, 'address': addr, 'data': new}
                    )

        self._master_communicator.do_command(master_api.activate_eeprom(), {'eep': 0},
                                             timeout=5)
        ret.append('Activated eeprom')
        self._eeprom_controller.invalidate_cache()

        return {'output': ret}

    @communication_enabled
    def sync_time(self):
        # type: () -> None
        logger.info('Setting the time on the master.')
        now = datetime.now()
        self._master_communicator.do_command(
            master_api.set_time(),
            {'sec': now.second, 'min': now.minute, 'hours': now.hour,
             'weekday': now.isoweekday(), 'day': now.day, 'month': now.month,
             'year': now.year % 100}
        )

    def get_configuration_dirty_flag(self):
        # type: () -> bool
        dirty = self._eeprom_controller.dirty
        # FIXME: this assumes a full sync will finish after this is called eg.
        # a response timeout clears the dirty state while no sync would started
        # on the remote side.
        self._eeprom_controller.dirty = False
        return dirty

    # Module functions

    def _process_module_initialize_message(self, api_data):
        # type: (Dict[str, Any]) -> None
        """
        Create a log entry when the MI message is received.
        > {'instr': 'E', 'module_nr': 0, 'io_type': 2, 'padding': '', 'literal': '', 'data': 1, 'id': 'I@7%'}
        """
        try:
            code_map = {'N': 'New',
                        'E': 'Existing',
                        'D': 'Duplicate'}
            category_map = {0: 'SHUTTER',
                            1: 'OUTPUT',
                            2: 'INPUT'}
            address = MasterClassicController._format_address(api_data['id'])
            module_type = chr(api_data['id'][0])
            with self._module_log_lock:
                self._module_log.append({'code': code_map.get(api_data['instr'], 'UNKNOWN').upper(),
                                         'module_nr': api_data['module_nr'],
                                         'category': category_map[api_data['io_type']],
                                         'module_type': module_type,
                                         'address': address})
            logger.info('Initialize/discovery - {0} module found: {1} ({2})'.format(
                code_map.get(api_data['instr'], 'Unknown'),
                api_data['id'][0],
                address
            ))
        except Exception:
            logger.exception('Could not process initialization message')

    @communication_enabled
    def module_discover_start(self, timeout):  # type: (int) -> None
        def _stop(): self.module_discover_stop()
        self._master_communicator.do_command(master_api.module_discover_start())

        if self._discover_mode_timer is not None:
            self._discover_mode_timer.cancel()
        self._discover_mode_timer = Timer(timeout, _stop)
        self._discover_mode_timer.start()

        with self._module_log_lock:
            self._module_log = []

    @communication_enabled
    def module_discover_stop(self):  # type: () -> None
        if self._discover_mode_timer is not None:
            self._discover_mode_timer.cancel()
            self._discover_mode_timer = None

        self._master_communicator.do_command(master_api.module_discover_stop())
        self._broadcast_module_discovery()

        with self._module_log_lock:
            self._module_log = []

    def module_discover_status(self):  # type: () -> bool
        return self._discover_mode_timer is not None

    def get_module_log(self):  # type: () -> List[Dict[str, Any]]
        with self._module_log_lock:
            (log, self._module_log) = (self._module_log, [])
        return log

    def _broadcast_module_discovery(self):
        # type: () -> None
        self._eeprom_controller.invalidate_cache()
        master_event = MasterEvent(event_type=MasterEvent.Types.MODULE_DISCOVERY, data={})
        self._pubsub.publish_master_event(PubSub.MasterTopics.MODULE, master_event)

    # Error functions

    @communication_enabled
    def error_list(self):
        """ Get the error list per module (input and output modules). The modules are identified by
        O1, O2, I1, I2, ...

        :returns: dict with 'errors' key, it contains list of tuples (module, nr_errors).
        """
        error_list = self._master_communicator.do_command(master_api.error_list())
        return error_list['errors']

    @communication_enabled
    def last_success(self):
        """ Get the number of seconds since the last successful communication with the master.
        """
        return self._master_communicator.get_seconds_since_last_success()

    @communication_enabled
    def clear_error_list(self):
        """ Clear the number of errors.

        :returns: empty dict.
        """
        self._master_communicator.do_command(master_api.clear_error_list())
        return dict()

    @communication_enabled
    def set_status_leds(self, status):
        """ Set the status of the leds on the master.

        :param status: whether the leds should be on or off.
        :type status: boolean.
        :returns: empty dict.
        """
        on = 1 if status is True else 0
        self.do_basic_action(master_api.BA_STATUS_LEDS, on)
        return dict()

    # (Group)Actions

    @communication_enabled
    def do_basic_action(self, action_type, action_number, parameter=0, timeout=2):  # type: (int, int, int, int) -> None
        """
        Execute a basic action.

        :param action_type: The type of the action as defined by the master api.
        :param action_number: The number provided to the basic action, its meaning depends on the action_type.
        :param parameter: An (optional) parameter for the basic action
        :param timeout: An (optional) timeout for the basic action
        """
        if action_type < 0 or action_type > 254:
            raise ValueError('action_type not in [0, 254]: %d' % action_type)

        if action_number < 0 or action_number > 254:
            raise ValueError('action_number not in [0, 254]: %d' % action_number)

        if parameter < 0 or parameter > 240:
            raise ValueError('parameter not in [0, 240]: %d' % parameter)

        logger.info('BA: Execute {0} {1} {2}'.format(action_type, action_number, parameter))
        self._master_communicator.do_command(master_api.basic_action(self._master_version),
                                             fields={'action_type': action_type,
                                                     'action_number': action_number,
                                                     'parameter': parameter},
                                             timeout=timeout)

    @communication_enabled
    def do_group_action(self, group_action_id):  # type: (int) -> None
        if group_action_id < 0 or group_action_id > 159:
            raise ValueError('group_action_id not in [0, 160]: %d' % group_action_id)
        self.do_basic_action(master_api.BA_GROUP_ACTION, group_action_id)

    @communication_enabled
    def load_group_action(self, group_action_id):  # type: (int) -> GroupActionDTO
        classic_object = self._eeprom_controller.read(eeprom_models.GroupActionConfiguration, group_action_id)
        return GroupActionMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_group_actions(self):  # type: () -> List[GroupActionDTO]
        return [GroupActionMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(eeprom_models.GroupActionConfiguration)]

    @communication_enabled
    def save_group_actions(self, group_actions):  # type: (List[Tuple[GroupActionDTO, List[str]]]) -> None
        batch = []
        for group_action, fields in group_actions:
            batch.append(GroupActionMapper.dto_to_orm(group_action, fields))
        self._eeprom_controller.write_batch(batch)

    # Schedules

    @communication_enabled
    def load_scheduled_action_configuration(self, scheduled_action_id, fields=None):
        # type: (int, Any) -> Dict[str,Any]
        return self._eeprom_controller.read(ScheduledActionConfiguration, scheduled_action_id, fields).serialize()

    @communication_enabled
    def load_scheduled_action_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        return [o.serialize() for o in self._eeprom_controller.read_all(ScheduledActionConfiguration, fields)]

    @communication_enabled
    def save_scheduled_action_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(ScheduledActionConfiguration.deserialize(config))

    @communication_enabled
    def save_scheduled_action_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        self._eeprom_controller.write_batch([ScheduledActionConfiguration.deserialize(o) for o in config])

    @communication_enabled
    def load_startup_action_configuration(self, fields=None):
        # type: (Any) -> Dict[str,Any]
        return self._eeprom_controller.read(StartupActionConfiguration, fields).serialize()

    @communication_enabled
    def save_startup_action_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(StartupActionConfiguration.deserialize(config))

    # Dimmer functions

    @communication_enabled
    def load_dimmer_configuration(self, fields=None):
        # type: (Any) -> Dict[str,Any]
        return self._eeprom_controller.read(DimmerConfiguration, fields).serialize()

    @communication_enabled
    def save_dimmer_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(DimmerConfiguration.deserialize(config))

    # Can Led functions

    @communication_enabled
    def load_can_led_configuration(self, can_led_id, fields=None):
        # type: (int, Any) -> Dict[str,Any]
        return self._eeprom_controller.read(CanLedConfiguration, can_led_id, fields).serialize()

    @communication_enabled
    def load_can_led_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        return [o.serialize() for o in self._eeprom_controller.read_all(CanLedConfiguration, fields)]

    @communication_enabled
    def save_can_led_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(CanLedConfiguration.deserialize(config))

    @communication_enabled
    def save_can_led_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        self._eeprom_controller.write_batch([CanLedConfiguration.deserialize(o) for o in config])

    # All lights off functions

    @communication_enabled
    def set_all_lights_off(self):
        # type: () -> None
        """ Turn all lights off. """
        self.do_basic_action(master_api.BA_ALL_LIGHTS_OFF, 0)

    @communication_enabled
    def set_all_lights_floor_off(self, floor):
        # type: (int) -> None
        """ Turn all lights on a given floor off. """
        self.do_basic_action(master_api.BA_LIGHTS_OFF_FLOOR, floor)

    @communication_enabled
    def set_all_lights_floor_on(self, floor):
        # type: (int) -> None
        """ Turn all lights on a given floor on. """
        self.do_basic_action(master_api.BA_LIGHTS_ON_FLOOR, floor)

    # Sensors

    def get_sensor_temperature(self, sensor_id):
        if sensor_id is None or sensor_id < 0 or sensor_id > 31:
            raise ValueError('Sensor ID {0} not in range 0 <= id <= 31'.format(sensor_id))
        return self.get_sensors_temperature()[sensor_id]

    @communication_enabled
    def get_sensors_temperature(self):
        temperatures = []
        sensor_list = self._master_communicator.do_command(master_api.sensor_temperature_list())
        for i in range(32):
            temperatures.append(sensor_list['tmp{0}'.format(i)].get_temperature())
        return temperatures

    @communication_enabled
    def get_sensor_humidity(self, sensor_id):
        if sensor_id is None or sensor_id < 0 or sensor_id > 31:
            raise ValueError('Sensor ID {0} not in range 0 <= id <= 31'.format(sensor_id))
        return self.get_sensors_humidity()[sensor_id]

    @communication_enabled
    def get_sensors_humidity(self):
        humidities = []
        sensor_list = self._master_communicator.do_command(master_api.sensor_humidity_list())
        for i in range(32):
            humidities.append(sensor_list['hum{0}'.format(i)].get_humidity())
        return humidities

    def get_sensor_brightness(self, sensor_id):
        if sensor_id is None or sensor_id < 0 or sensor_id > 31:
            raise ValueError('Sensor ID {0} not in range 0 <= id <= 31'.format(sensor_id))
        return self.get_sensors_brightness()[sensor_id]

    @communication_enabled
    def get_sensors_brightness(self):
        brightnesses = []
        sensor_list = self._master_communicator.do_command(master_api.sensor_brightness_list())
        for i in range(32):
            brightnesses.append(sensor_list['bri{0}'.format(i)].get_brightness())
        return brightnesses

    @communication_enabled
    def set_virtual_sensor(self, sensor_id, temperature, humidity, brightness):
        if sensor_id is None or sensor_id < 0 or sensor_id > 31:
            raise ValueError('Sensor ID {0} not in range 0 <= id <= 31'.format(sensor_id))

        self._master_communicator.do_command(
            master_api.set_virtual_sensor(),
            {'sensor': sensor_id,
             'tmp': master_api.Svt.temp(temperature),
             'hum': master_api.Svt.humidity(humidity),
             'bri': master_api.Svt.brightness(brightness)}
        )

    @communication_enabled
    def load_sensor(self, sensor_id):  # type: (int) -> SensorDTO
        classic_object = self._eeprom_controller.read(eeprom_models.SensorConfiguration, sensor_id)
        return SensorMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_sensors(self):  # type: () -> List[SensorDTO]
        return [SensorMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(eeprom_models.SensorConfiguration)]

    @communication_enabled
    def save_sensors(self, sensors):  # type: (List[Tuple[SensorDTO, List[str]]]) -> None
        batch = []
        for sensor, fields in sensors:
            batch.append(SensorMapper.dto_to_orm(sensor, fields))
        self._eeprom_controller.write_batch(batch)

    # PulseCounters

    @communication_enabled
    def load_pulse_counter(self, pulse_counter_id):  # type: (int) -> PulseCounterDTO
        classic_object = self._eeprom_controller.read(eeprom_models.PulseCounterConfiguration, pulse_counter_id)
        return PulseCounterMapper.orm_to_dto(classic_object)

    @communication_enabled
    def load_pulse_counters(self):  # type: () -> List[PulseCounterDTO]
        return [PulseCounterMapper.orm_to_dto(o)
                for o in self._eeprom_controller.read_all(eeprom_models.PulseCounterConfiguration)]

    @communication_enabled
    def save_pulse_counters(self, pulse_counters):  # type: (List[Tuple[PulseCounterDTO, List[str]]]) -> None
        batch = []
        for pulse_counter, fields in pulse_counters:
            batch.append(PulseCounterMapper.dto_to_orm(pulse_counter, fields))
        self._eeprom_controller.write_batch(batch)

    @communication_enabled
    def get_pulse_counter_values(self):  # type: () -> Dict[int, int]
        out_dict = self._master_communicator.do_command(master_api.pulse_list())
        return {i: out_dict['pv{0}'.format(i)] for i in range(24)}

    # Validation bits

    @communication_enabled
    def load_validation_bits(self):  # type: () -> Optional[Dict[int, bool]]
        if self._master_version is None or self._master_version < (3, 143, 102):
            return None

        number_of_bits = 256
        bytes_per_call = 11

        def load_bits_batch(start_bit):  # type: (int) -> Dict[int, bool]
            batch = {}  # type: Dict[int, bool]
            response = self._master_communicator.do_command(master_api.read_user_information(self._master_version),
                                                            {'information_type': 0, 'number': start_bit})
            for byte_index in range(bytes_per_call):
                for bit_index in range(8):
                    bit_nr = start_bit + (byte_index * 8) + bit_index
                    if bit_nr == number_of_bits:
                        return batch  #
                    bit_value = bool(response['data'][byte_index] & (1 << bit_index))
                    batch[bit_nr] = bit_value
            return batch

        bits = {}
        bit_pointer = 0
        while True:
            bits.update(load_bits_batch(bit_pointer))
            bit_pointer = max(*bits.keys()) + 1
            if bit_pointer == 256:
                break
        return bits

    def _refresh_validation_bits(self):
        current_bit_states = self.load_validation_bits()
        if current_bit_states is not None:
            self._validation_bits.full_update(current_bit_states)
        self._validation_bits_last_updated = time.time()

    def _on_master_validation_bit_change(self, bit_nr, value):  # type: (int, bool) -> None
        self._validation_bits.update(bit_nr, value)

    def _validation_bit_changed(self, bit_nr, value):
        # loop over all outputs and update the locked status if the bit_nr is associated with this output
        for output_id, output_dto in six.iteritems(self._output_config):
            if output_dto.lock_bit_id == bit_nr:
                locked = value  # the bit is set, the output is locked
                event_data = {'id': output_id, 'locked': locked}
                master_event = MasterEvent(event_type=MasterEvent.Types.OUTPUT_STATUS, data=event_data)
                self._pubsub.publish_master_event(PubSub.MasterTopics.OUTPUT, master_event)
