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

import logging
import struct
import time
from datetime import datetime
from threading import Timer

from peewee import DoesNotExist

from gateway.daemon_thread import DaemonThread, DaemonThreadWait
from gateway.dto import GroupActionDTO, InputDTO, ModuleDTO, OutputDTO, \
    PulseCounterDTO, SensorDTO, ShutterDTO, ShutterGroupDTO, \
    GlobalFeedbackDTO, OutputStateDTO, LegacyStartupActionDTO, \
    LegacyScheduleDTO
from gateway.enums import ShutterEnums, IndicateType
from gateway.exceptions import UnsupportedException
from gateway.hal.mappers_core import GroupActionMapper, InputMapper, \
    OutputMapper, SensorMapper, ShutterMapper
from gateway.hal.master_controller import CommunicationFailure, \
    MasterController
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject
from master.core.basic_action import BasicAction
from master.core.can_feedback import CANFeedbackController
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer, CoreCommunicator
from master.core.core_updater import CoreUpdater
from master.core.errors import Error
from master.core.events import Event as MasterCoreEvent
from master.core.group_action import GroupActionController
from master.core.memory_file import MemoryFile, MemoryTypes
from master.core.memory_models import CanControlModuleConfiguration, \
    GlobalConfiguration, InputConfiguration, InputModuleConfiguration, \
    OutputConfiguration, OutputModuleConfiguration, SensorConfiguration, \
    SensorModuleConfiguration, ShutterConfiguration
from master.core.memory_types import MemoryAddress, MemoryActivator
from master.core.slave_communicator import SlaveCommunicator
from master.core.system_value import Humidity, Temperature, Timer as SVTTimer
from serial_utils import CommunicationStatus, CommunicationTimedOutException

if False:  # MYPY
    from typing import Any, Dict, List, Literal, Tuple, Optional, Type, Union
    HEALTH = Literal['success', 'unstable', 'failure']

logger = logging.getLogger("openmotics")


class MasterCoreController(MasterController):

    @Inject
    def __init__(self, master_communicator=INJECTED, slave_communicator=INJECTED, memory_file=INJECTED, pubsub=INJECTED):
        # type: (CoreCommunicator, SlaveCommunicator, MemoryFile, PubSub) -> None
        super(MasterCoreController, self).__init__(master_communicator)
        self._master_communicator = master_communicator
        self._slave_communicator = slave_communicator
        self._memory_file = memory_file
        self._pubsub = pubsub
        self._synchronization_thread = None  # type: Optional[DaemonThread]
        self._master_online = False
        self._discover_mode_timer = None  # type: Optional[Timer]
        self._input_state = MasterInputState()
        self._output_states = {}  # type: Dict[int,OutputStateDTO]
        self._sensor_interval = 300
        self._sensor_last_updated = 0.0
        self._sensor_states = {}  # type: Dict[int,Dict[str,None]]
        self._shutters_interval = 600
        self._shutters_last_updated = 0.0
        self._shutter_status = {}  # type: Dict[int, Tuple[bool, bool]]
        self._time_last_updated = 0.0
        self._output_shutter_map = {}  # type: Dict[int, int]
        self._firmware_versions = {}  # type: Dict[str, Optional[str]]

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.EEPROM, self._handle_eeprom_event)

        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.firmware_information(), 0, self._handle_firmware_information)
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.error_information(), 0, lambda e: logger.info('Got master error: {0}'.format(Error(e))))
            # TODO: Reduce flood of errors if something is wrong:
            #  Log the first error immediately, then, if the same error occurs within 1 minute, just count it. When
            #  the minute is over, log the amount of skipped errors (e.g. `X similar ERORR_CODE master errors were supressed`)
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.ucan_module_information(), 0, lambda i: logger.info('Got ucan module information: {0}'.format(i)))
        )

    #################
    # Private stuff #
    #################

    def _handle_eeprom_event(self, master_event):
        # type: (MasterEvent) -> None
        if master_event.type == MasterEvent.Types.EEPROM_CHANGE:
            self._output_shutter_map = {}
            self._shutters_last_updated = 0.0
            self._sensor_last_updated = 0.0
            self._input_last_updated = 0.0
            self._output_last_updated = 0.0

    def _handle_event(self, data):
        # type: (Dict[str, Any]) -> None
        core_event = MasterCoreEvent(data)
        if core_event.type not in [MasterCoreEvent.Types.LED_BLINK,
                                   MasterCoreEvent.Types.LED_ON,
                                   MasterCoreEvent.Types.BUTTON_PRESS]:
            # Interesting for debug purposes, but not for everything
            logger.info('Got master event: {0}'.format(core_event))
        if core_event.type == MasterCoreEvent.Types.OUTPUT:
            output_id = core_event.data['output']
            if core_event.data['type'] == MasterCoreEvent.OutputEventTypes.STATUS:
                # Update internal state cache
                state_dto = OutputStateDTO(id=output_id,
                                           status=core_event.data['status'],
                                           dimmer=core_event.data['dimmer_value'],
                                           ctimer=core_event.data['timer'])
            else:  # elif core_event.data['type'] == MasterCoreEvent.OutputEventTypes.LOCKING:
                state_dto = OutputStateDTO(id=output_id,
                                           locked=core_event.data['locked'])
            self._handle_output_state(output_id, state_dto)
        elif core_event.type == MasterCoreEvent.Types.INPUT:
            master_event = self._input_state.handle_event(core_event)
            self._pubsub.publish_master_event(PubSub.MasterTopics.INPUT, master_event)
        elif core_event.type == MasterCoreEvent.Types.SENSOR:
            sensor_id = core_event.data['sensor']
            if sensor_id not in self._sensor_states:
                return
            self._sensor_states[sensor_id][core_event.data['type']] = core_event.data['value']
        elif core_event.type == MasterCoreEvent.Types.EXECUTE_GATEWAY_API:
            self._handle_execute_event(action=core_event.data['action'],
                                       device_nr=core_event.data['device_nr'],
                                       extra_parameter=core_event.data['extra_parameter'])

    def _handle_execute_event(self, action, device_nr, extra_parameter):  # type: (int, int, int) -> None
        if action == 0:
            if extra_parameter not in [0, 1, 2]:
                return
            floor_id = None  # type: Optional[int]
            if device_nr != 65535:
                floor_id = device_nr
            event_action = {0: 'OFF', 1: 'ON', 2: 'TOGGLE'}[extra_parameter]
            self._pubsub.publish_master_event(topic=PubSub.MasterTopics.OUTPUT,
                                              master_event=MasterEvent(event_type=MasterEvent.Types.EXECUTE_GATEWAY_API,
                                                                       data={'type': MasterEvent.APITypes.SET_LIGHTS,
                                                                             'data': {'action': event_action,
                                                                                      'floor_id': floor_id}}))

    def _handle_output_state(self, output_id, state_dto):
        # type: (int, OutputStateDTO) -> None
        master_event = MasterEvent(MasterEvent.Types.OUTPUT_STATUS, {'state': state_dto})
        self._pubsub.publish_master_event(PubSub.MasterTopics.OUTPUT, master_event)
        shutter_id = self._output_shutter_map.get(output_id)
        if shutter_id:
            shutter = ShutterConfiguration(shutter_id)
            output_0_on, output_1_on = (None, None)
            if output_id == shutter.outputs.output_0:
                output_0_on = state_dto.status
            if output_id == shutter.outputs.output_1:
                output_1_on = state_dto.status
            self._handle_shutter(shutter, output_0_on, output_1_on)

    def _handle_shutter(self, shutter, output_0_on, output_1_on):
        # type: (ShutterConfiguration, Optional[bool], Optional[bool]) -> None
        if shutter.outputs.output_0 == 255 * 2:
            return
        if output_0_on is None:
            output_0_on = self._shutter_status[shutter.id][0]
        if output_1_on is None:
            output_1_on = self._shutter_status[shutter.id][1]
        if (output_0_on, output_1_on) == self._shutter_status.get(shutter.id, (None, None)):
            logger.error('shutter status did not change')
            return

        output_module = OutputConfiguration(shutter.outputs.output_0).module
        if getattr(output_module.shutter_config, 'set_{0}_direction'.format(shutter.output_set)):
            up, down = output_0_on, output_1_on
        else:
            up, down = output_1_on, output_0_on

        if up == 1 and down == 0:
            state = ShutterEnums.State.GOING_UP
        elif down == 1 and up == 0:
            state = ShutterEnums.State.GOING_DOWN
        else:  # Both are off or - unlikely - both are on
            state = ShutterEnums.State.STOPPED

        event_data = {'id': shutter.id,
                      'status': state,
                      'location': {'room_id': 255}}  # TODO: rooms
        master_event = MasterEvent(event_type=MasterEvent.Types.SHUTTER_CHANGE, data=event_data)
        self._pubsub.publish_master_event(PubSub.MasterTopics.SHUTTER, master_event)
        self._shutter_status[shutter.id] = (output_0_on, output_1_on)

    def _synchronize(self):
        # type: () -> None
        try:
            # Refresh if required
            if self._time_last_updated + 300 < time.time():
                self._check_master_time()
            if self._refresh_input_states():
                self._set_master_state(True)
            if self._sensor_last_updated + self._sensor_interval < time.time():
                self._refresh_sensor_states()
                self._set_master_state(True)
            if self._shutters_last_updated + self._shutters_interval < time.time():
                self._refresh_shutter_states()
                self._set_master_state(True)
        except CommunicationTimedOutException:
            logger.error('Got communication timeout during synchronization.')
            self._set_master_state(False)
            raise DaemonThreadWait()
        except CommunicationFailure:
            # This is an expected situation
            raise DaemonThreadWait()

    def _set_master_state(self, online):
        if online != self._master_online:
            self._master_online = online

    def _enumerate_io_modules(self, module_type, amount_per_module=8):
        cmd = CoreAPI.general_configuration_number_of_modules()
        module_count = self._master_communicator.do_command(cmd, {})[module_type]
        return range(module_count * amount_per_module)

    def _check_master_time(self):
        # type: () -> None
        date_time = self._master_communicator.do_command(CoreAPI.get_date_time(), {})
        if date_time is None:
            return
        try:
            core_value = datetime(2000 + date_time['year'], date_time['month'], date_time['day'],
                                  date_time['hours'], date_time['minutes'], date_time['seconds'])
            core_weekday = date_time['weekday']
        except ValueError:
            core_value = datetime(2000, 1, 1, 0, 0, 0)
            core_weekday = 0

        now = datetime.now()
        expected_weekday = now.weekday() + 1
        expected_value = now.replace(microsecond=0)

        sync = False
        if abs((core_value - expected_value).total_seconds()) > 180:  # Allow 3 minutes difference
            sync = True
        if core_weekday != expected_weekday:
            sync = True

        if sync is True:
            if expected_value.hour == 0 and expected_value.minute < 15:
                logger.info('Skip setting time between 00:00 and 00:15')
            else:
                logger.info('Time - core: {0} ({1}) - gateway: {2} ({3})'.format(
                    core_value, core_weekday, expected_value, expected_weekday)
                )
                self.sync_time()
        self._time_last_updated = time.time()

    #######################
    # Internal management #
    #######################

    def start(self):
        super(MasterCoreController, self).start()
        self._synchronization_thread = DaemonThread(name='mastersync',
                                                    target=self._synchronize,
                                                    interval=1, delay=10)
        self._synchronization_thread.start()
        try:
            self._log_stats()
        except Exception:
            pass

    def stop(self):
        if self._synchronization_thread is not None:
            self._synchronization_thread.stop()
            self._synchronization_thread = None
        super(MasterCoreController, self).stop()

    def set_plugin_controller(self, plugin_controller):
        """ Set the plugin controller. """
        pass  # TODO: implement

    def _log_stats(self):
        def _default_if_255(value, default):
            return value if value != 255 else default

        max_specs = self._master_communicator.do_command(CoreAPI.general_configuration_max_specs(), {})
        global_configuration = GlobalConfiguration()
        logger.info('General core information:')
        logger.info('* Modules:')
        logger.info('  * Auto discovery: {0}'.format(global_configuration.automatic_module_discovery))
        logger.info('  * Output: {0}/{1}'.format(_default_if_255(global_configuration.number_of_output_modules, 0),
                                                 max_specs['output']))
        logger.info('  * Input: {0}/{1}'.format(_default_if_255(global_configuration.number_of_input_modules, 0),
                                                max_specs['input']))
        logger.info('  * Sensor: {0}/{1}'.format(_default_if_255(global_configuration.number_of_sensor_modules, 0),
                                                 max_specs['sensor']))
        logger.info('  * uCAN: {0}/{1}'.format(_default_if_255(global_configuration.number_of_ucan_modules, 0),
                                               max_specs['ucan']))
        logger.info('  * CAN Control: {0}'.format(_default_if_255(global_configuration.number_of_can_control_modules, 0)))
        logger.info('* CAN:')
        logger.info('  * Inputs: {0}'.format(global_configuration.number_of_can_inputs))
        logger.info('  * Sensors: {0}'.format(global_configuration.number_of_can_sensors))
        logger.info('  * Termination: {0}'.format(global_configuration.can_bus_termination))
        logger.info('* Scan times:')
        logger.info('  * General bus: {0}ms'.format(_default_if_255(global_configuration.scan_time_rs485_bus, 8)))
        logger.info('  * Sensor modules: {0}ms'.format(_default_if_255(global_configuration.scan_time_rs485_sensor_modules, 50) * 100))
        logger.info('  * CAN Control modules: {0}ms'.format(_default_if_255(global_configuration.scan_time_rs485_can_control_modules, 50) * 100))
        logger.info('* Runtime stats:')
        logger.info('  * Debug: {0}'.format(global_configuration.debug_mode))
        logger.info('  * Uptime: {0}d {1}h'.format(global_configuration.uptime_hours / 24,
                                                   global_configuration.uptime_hours % 24))
        # noinspection PyStringFormat
        logger.info('  * Started at 20{0}/{1}/{2} {3}:{4}:{5}'.format(*(list(reversed(global_configuration.startup_date)) +
                                                                        global_configuration.startup_time)))

    ##############
    # Public API #
    ##############

    def get_master_online(self):
        # type: () -> bool
        return self._master_online

    def get_communicator_health(self):
        # type: () -> HEALTH
        stats = self._master_communicator.get_communication_statistics()
        calls_timedout = [call for call in stats['calls_timedout']]
        calls_succeeded = [call for call in stats['calls_succeeded']]
        all_calls = sorted(calls_timedout + calls_succeeded)

        if len(calls_timedout) == 0:
            # If there are no timeouts at all
            return CommunicationStatus.SUCCESS

        if len(all_calls) <= 10:
            # Not enough calls made to have a decent view on what's going on
            logger.warning('Observed master communication failures, but not enough calls')
            return CommunicationStatus.UNSTABLE

        calls_last_x_minutes = [t for t in all_calls if t > time.time() - 180]
        if len(calls_last_x_minutes) <= 5:
            # Not enough calls in the last 3 minutes to have a decent view on what's going on
            logger.warning('Observed master communication failures, but not recent enough')
            return CommunicationStatus.UNSTABLE

        if len(all_calls) >= 30 and not any(t in calls_timedout for t in all_calls[-30:]):
            # The last 30 calls are successfull, consider "recoverd"
            return CommunicationStatus.SUCCESS
        if not any(t in calls_timedout for t in all_calls[-10:]):
            # The last 10 calls are successfull, consider "recovering"
            logger.warning('Observed master communication failures, but recovering')
            return CommunicationStatus.UNSTABLE

        ratio = len([t for t in calls_last_x_minutes if t in calls_timedout]) / float(len(calls_last_x_minutes))
        if ratio < 0.25:
            # Less than 25% of the calls fail, let's assume everything is just "fine"
            logger.warning('Observed master communication failures, but there\'s only a failure ratio of {:.2f}%'.format(ratio * 100))
            return CommunicationStatus.UNSTABLE

        return CommunicationStatus.FAILURE

    def get_firmware_version(self):
        version = self._master_communicator.do_command(CoreAPI.get_firmware_version(), {})['version']
        return tuple(version.split('.'))

    def sync_time(self):
        # type: () -> None
        logger.info('Setting the time on the core.')
        now = datetime.now()
        self._master_communicator.do_command(
            CoreAPI.set_date_time(),
            {'hours': now.hour, 'minutes': now.minute, 'seconds': now.second,
             'weekday': now.isoweekday(), 'day': now.day, 'month': now.month, 'year': now.year % 100}
        )

    # Input

    def get_input_module_type(self, input_module_id):
        input_module = InputConfiguration(input_module_id)
        return input_module.module.device_type

    def get_inputs_with_status(self):
        # type: () -> List[Dict[str,Any]]
        return self._input_state.get_inputs()

    def get_recent_inputs(self):
        # type: () -> List[int]
        return self._input_state.get_recent()

    def load_input(self, input_id):  # type: (int) -> InputDTO
        input_ = InputConfiguration(input_id)
        return InputMapper.orm_to_dto(input_)

    def load_inputs(self):  # type: () -> List[InputDTO]
        inputs = []
        for i in self._enumerate_io_modules('input'):
            inputs.append(self.load_input(i))
        return inputs

    def save_inputs(self, inputs):  # type: (List[InputDTO]) -> None
        for input_dto in inputs:
            input_ = InputMapper.dto_to_orm(input_dto)
            input_.save(activate=False)
        MemoryActivator.activate()

    def _refresh_input_states(self):
        # type: () -> bool
        refresh = self._input_state.should_refresh()
        if refresh:
            cmd = CoreAPI.device_information_list_inputs()
            data = self._master_communicator.do_command(cmd, {})
            if data is not None:
                for master_event in self._input_state.refresh(data['information']):
                    self._pubsub.publish_master_event(PubSub.MasterTopics.INPUT, master_event)
        return refresh

    def set_input(self, input_id, state):
        raise NotImplementedError()

    # Outputs

    def set_output(self, output_id, state, dimmer=None, timer=None):
        output = OutputConfiguration(output_id)
        if output.is_shutter:
            # Shutter outputs cannot be controlled
            return
        self._master_communicator.do_basic_action(BasicAction(action_type=0,
                                                              action=1 if state else 0,
                                                              device_nr=output_id))
        if dimmer is not None:
            self._master_communicator.do_basic_action(BasicAction(action_type=0,
                                                                  action=9,
                                                                  device_nr=output_id,
                                                                  extra_parameter=int(2.55 * dimmer)))  # Map 0-100 to 0-255
        if timer is not None:
            self._master_communicator.do_basic_action(BasicAction(action_type=0,
                                                                  action=11,
                                                                  device_nr=output_id,
                                                                  extra_parameter=timer))

    def toggle_output(self, output_id):
        output = OutputConfiguration(output_id)
        if output.is_shutter:
            # Shutter outputs cannot be controlled
            return
        self._master_communicator.do_basic_action(BasicAction(action_type=0,
                                                              action=16,
                                                              device_nr=output_id))

    def load_output(self, output_id):  # type: (int) -> OutputDTO
        output = OutputConfiguration(output_id)
        if output.is_shutter:
            # Outputs that are used by a shutter are returned as unconfigured (read-only) outputs
            return OutputDTO(id=output.id)
        output_dto = OutputMapper.orm_to_dto(output)
        CANFeedbackController.load_output_led_feedback_configuration(output, output_dto)
        return output_dto

    def load_outputs(self):  # type: () -> List[OutputDTO]
        outputs = []
        for i in self._enumerate_io_modules('output'):
            outputs.append(self.load_output(i))
        return outputs

    def save_outputs(self, outputs):  # type: (List[OutputDTO]) -> None
        for output_dto in outputs:
            output = OutputMapper.dto_to_orm(output_dto)
            if output.is_shutter:
                # Shutter outputs cannot be changed
                continue
            output.save(activate=False)
            CANFeedbackController.save_output_led_feedback_configuration(output, output_dto, activate=False)
        MemoryActivator.activate()

    def load_output_status(self):
        # type: () -> List[OutputStateDTO]
        output_status = []
        for i in self._enumerate_io_modules('output'):
            data = self._master_communicator.do_command(CoreAPI.output_detail(), {'device_nr': i})
            timer = SVTTimer.event_timer_type_to_seconds(data['timer_type'], data['timer'])
            output = OutputConfiguration(i)
            output_status.append(OutputStateDTO(id=i,
                                                status=bool(data['status']),
                                                ctimer=timer,
                                                dimmer=int(data['dimmer']),
                                                locked=output.locking.locked))
        return output_status

    # Shutters

    def shutter_up(self, shutter_id, timer=None):
        if timer:
            raise NotImplementedError('Shutter timers are not supported')
        self._master_communicator.do_basic_action(BasicAction(action_type=10,
                                                              action=1,
                                                              device_nr=shutter_id))

    def shutter_down(self, shutter_id, timer=None):
        if timer:
            raise NotImplementedError('Shutter timers are not supported')
        self._master_communicator.do_basic_action(BasicAction(action_type=10,
                                                              action=2,
                                                              device_nr=shutter_id))

    def shutter_stop(self, shutter_id):
        self._master_communicator.do_basic_action(BasicAction(action_type=10,
                                                              action=0,
                                                              device_nr=shutter_id))

    def load_shutter(self, shutter_id):  # type: (int) -> ShutterDTO
        shutter = ShutterConfiguration(shutter_id)
        shutter_dto = ShutterMapper.orm_to_dto(shutter)
        # Load information that is set on the Output(Module)Configuration
        if shutter.outputs.output_0 == 255 * 2:
            shutter_dto.up_down_config = 1
        else:
            output_module = OutputConfiguration(shutter.outputs.output_0).module
            if getattr(output_module.shutter_config, 'set_{0}_direction'.format(shutter.output_set)):
                shutter_dto.up_down_config = 1
            else:
                shutter_dto.up_down_config = 0
        return shutter_dto

    def load_shutters(self):  # type: () -> List[ShutterDTO]
        # At this moment, the system expects a given amount of Shutter modules to be physically
        # installed. However, in the Core+, this is not the case as a Shutter isn't a physical module
        # but instead a virtual layer over physical Output modules. For easy backwards compatible
        # implementation, a Shutter will map 1-to-1 to the Outputs with the same ID. This means we only need
        # to emulate such a Shutter module foreach Output module.
        shutters = []
        for shutter_id in self._enumerate_io_modules('output', amount_per_module=4):
            shutters.append(self.load_shutter(shutter_id))
        return shutters

    def save_shutters(self, shutters):  # type: (List[ShutterDTO]) -> None
        for shutter_dto in shutters:
            # Validate whether output module exists
            output_module = OutputConfiguration(shutter_dto.id * 2).module
            # Configure shutter
            shutter = ShutterMapper.dto_to_orm(shutter_dto)
            if shutter.timer_down not in [0, 65535] and shutter.timer_up not in [0, 65535]:
                # Shutter is "configured"
                shutter.outputs.output_0 = shutter.id * 2
                output_set = shutter.output_set
                self._output_shutter_map[shutter.outputs.output_0] = shutter.id
                self._output_shutter_map[shutter.outputs.output_1] = shutter.id
                is_configured = True
            else:
                output_set = shutter.output_set  # Previous outputs need to be restored
                self._output_shutter_map.pop(shutter.outputs.output_0, None)
                self._output_shutter_map.pop(shutter.outputs.output_1, None)
                shutter.outputs.output_0 = 255 * 2
                is_configured = False
            shutter.save(activate=False)
            # Mark related Outputs as "occupied by shutter"
            setattr(output_module.shutter_config, 'are_{0}_outputs'.format(output_set), not is_configured)
            setattr(output_module.shutter_config, 'set_{0}_direction'.format(shutter.output_set), shutter_dto.up_down_config == 1)
            output_module.save(activate=False)
        MemoryActivator.activate()

    def _refresh_shutter_states(self):
        status_data = {x.id: x for x in self.load_output_status()}  # type: Dict[int, OutputStateDTO]
        for shutter_id in range(len(status_data) // 2):
            shutter = ShutterConfiguration(shutter_id)
            output_0 = status_data.get(shutter.outputs.output_0)
            output_1 = status_data.get(shutter.outputs.output_1)
            if output_0 and output_1:
                self._output_shutter_map[shutter.outputs.output_0] = shutter.id
                self._output_shutter_map[shutter.outputs.output_1] = shutter.id
                self._handle_shutter(shutter, output_0.status, output_1.status)
            else:
                self._shutter_status.pop(shutter.id, None)
                self._output_shutter_map.pop(shutter.outputs.output_0, None)
                self._output_shutter_map.pop(shutter.outputs.output_1, None)
        self._shutters_last_updated = time.time()

    def shutter_group_up(self, shutter_group_id):  # type: (int) -> None
        device_nr = shutter_group_id + 256
        self._master_communicator.do_basic_action(BasicAction(action_type=10,
                                                              action=1,
                                                              device_nr=device_nr))

    def shutter_group_down(self, shutter_group_id):  # type: (int) -> None
        device_nr = shutter_group_id + 256
        self._master_communicator.do_basic_action(BasicAction(action_type=10,
                                                              action=2,
                                                              device_nr=device_nr))

    def shutter_group_stop(self, shutter_group_id):  # type: (int) -> None
        device_nr = shutter_group_id + 256
        self._master_communicator.do_basic_action(BasicAction(action_type=10,
                                                              action=0,
                                                              device_nr=device_nr))

    def load_shutter_group(self, shutter_group_id):  # type: (int) -> ShutterGroupDTO
        return ShutterGroupDTO(id=shutter_group_id)

    def load_shutter_groups(self):  # type: () -> List[ShutterGroupDTO]
        shutter_groups = []
        for i in range(16):
            shutter_groups.append(ShutterGroupDTO(id=i))
        return shutter_groups

    def save_shutter_groups(self, shutter_groups):  # type: (List[ShutterGroupDTO]) -> None
        raise UnsupportedException()

    # Thermostats

    def load_heating_thermostat(self, thermostat_id):
        raise UnsupportedException()

    def load_heating_thermostats(self):
        raise UnsupportedException()

    def save_heating_thermostats(self, thermostats):
        raise UnsupportedException()

    def load_cooling_thermostat(self, thermostat_id):
        raise UnsupportedException()

    def load_cooling_thermostats(self):
        raise UnsupportedException()

    def save_cooling_thermostats(self, thermostats):
        raise UnsupportedException()

    def load_thermostat_group(self):
        raise UnsupportedException()

    def save_thermostat_group(self, thermostat_group):
        raise UnsupportedException()

    # Can Led functions

    def load_global_feedback(self, global_feedback_id):  # type: (int) -> GlobalFeedbackDTO
        global_feedbacks = CANFeedbackController.load_global_led_feedback_configuration()
        return global_feedbacks.get(global_feedback_id, GlobalFeedbackDTO(id=global_feedback_id))

    def load_global_feedbacks(self):  # type: () -> List[GlobalFeedbackDTO]
        global_feedbacks = CANFeedbackController.load_global_led_feedback_configuration()
        return [global_feedbacks.get(i, GlobalFeedbackDTO(id=i)) for i in range(32)]

    def save_global_feedbacks(self, global_feedbacks):  # type: (List[GlobalFeedbackDTO]) -> None
        CANFeedbackController.save_global_led_feedback_configuration(global_feedbacks, activate=True)

    # Sensors

    def get_sensor_temperature(self, sensor_id):
        return self._sensor_states.get(sensor_id, {}).get('TEMPERATURE')

    def get_sensors_temperature(self):
        amount_sensor_modules = self._master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})['sensor']
        temperatures = []
        for sensor_id in range(amount_sensor_modules * 8):
            temperatures.append(self.get_sensor_temperature(sensor_id))
        return temperatures

    def get_sensor_humidity(self, sensor_id):
        return self._sensor_states.get(sensor_id, {}).get('HUMIDITY')

    def get_sensors_humidity(self):
        amount_sensor_modules = self._master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})['sensor']
        humidities = []
        for sensor_id in range(amount_sensor_modules * 8):
            humidities.append(self.get_sensor_humidity(sensor_id))
        return humidities

    def get_sensor_brightness(self, sensor_id):
        # TODO: This is a lux value and must somehow be converted to legacy percentage
        brightness = self._sensor_states.get(sensor_id, {}).get('BRIGHTNESS')
        if brightness is None or brightness in [65535]:
            return None
        return int(float(brightness) / 65535.0 * 100)

    def get_sensors_brightness(self):
        amount_sensor_modules = self._master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})['sensor']
        brightnesses = []
        for sensor_id in range(amount_sensor_modules * 8):
            brightnesses.append(self.get_sensor_brightness(sensor_id))
        return brightnesses

    def load_sensor(self, sensor_id):  # type: (int) -> SensorDTO
        sensor = SensorConfiguration(sensor_id)
        return SensorMapper.orm_to_dto(sensor)

    def load_sensors(self):  # type: () -> List[SensorDTO]
        sensors = []
        for i in self._enumerate_io_modules('sensor'):
            sensors.append(self.load_sensor(i))
        return sensors

    def save_sensors(self, sensors):  # type: (List[SensorDTO]) -> None
        for sensor_dto in sensors:
            sensor = SensorMapper.dto_to_orm(sensor_dto)
            sensor.save(activate=False)
        MemoryActivator.activate()

    def _refresh_sensor_states(self):
        amount_sensor_modules = self._master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})['sensor']
        for module_nr in range(amount_sensor_modules):
            temperature_values = self._master_communicator.do_command(CoreAPI.sensor_temperature_values(), {'module_nr': module_nr})['values']
            brightness_values = self._master_communicator.do_command(CoreAPI.sensor_brightness_values(), {'module_nr': module_nr})['values']
            humidity_values = self._master_communicator.do_command(CoreAPI.sensor_humidity_values(), {'module_nr': module_nr})['values']
            for i in range(8):
                sensor_id = module_nr * 8 + i
                self._sensor_states[sensor_id] = {'TEMPERATURE': temperature_values[i],
                                                  'BRIGHTNESS': brightness_values[i],
                                                  'HUMIDITY': humidity_values[i]}
        self._sensor_last_updated = time.time()

    def set_virtual_sensor(self, sensor_id, temperature, humidity, brightness):
        sensor_configuration = SensorConfiguration(sensor_id)
        if sensor_configuration.module.device_type != 't':
            raise ValueError('Sensor ID {0} does not map to a virtual Sensor'.format(sensor_id))
        self._master_communicator.do_basic_action(BasicAction(action_type=3,
                                                              action=sensor_id,
                                                              device_nr=Temperature.temperature_to_system_value(temperature)))
        self._master_communicator.do_basic_action(BasicAction(action_type=4,
                                                              action=sensor_id,
                                                              device_nr=Humidity.humidity_to_system_value(humidity)))
        self._master_communicator.do_basic_action(BasicAction(action_type=5,
                                                              action=sensor_id,
                                                              device_nr=brightness if brightness is not None else (2 ** 16 - 1),
                                                              extra_parameter=3))  # Store full word-size brightness value
        self._refresh_sensor_states()

    # PulseCounters

    def load_pulse_counter(self, pulse_counter_id):  # type: (int) -> PulseCounterDTO
        # TODO: Implement PulseCounters
        raise DoesNotExist('Could not find a PulseCounter with id {0}'.format(pulse_counter_id))

    def load_pulse_counters(self):  # type: () -> List[PulseCounterDTO]
        # TODO: Implement PulseCounters
        return []

    def save_pulse_counters(self, pulse_counters):  # type: (List[PulseCounterDTO]) -> None
        # TODO: Implement PulseCounters
        return

    def get_pulse_counter_values(self):  # type: () -> Dict[int, int]
        # TODO: Implement PulseCounters
        return {}

    # (Group)Actions

    def do_basic_action(self, action_type, action_number):  # type: (int, int) -> None
        basic_actions = GroupActionMapper.classic_actions_to_core_actions([action_type, action_number])
        for basic_action in basic_actions:
            self._master_communicator.do_basic_action(basic_action)

    def do_group_action(self, group_action_id):  # type: (int) -> None
        self._master_communicator.do_basic_action(BasicAction(action_type=19, action=0, device_nr=group_action_id))

    def load_group_action(self, group_action_id):  # type: (int) -> GroupActionDTO
        return GroupActionMapper.orm_to_dto(GroupActionController.load_group_action(group_action_id))

    def load_group_actions(self):  # type: () -> List[GroupActionDTO]
        return [GroupActionMapper.orm_to_dto(o)
                for o in GroupActionController.load_group_actions()]

    def save_group_actions(self, group_actions):  # type: (List[GroupActionDTO]) -> None
        for group_action_dto in group_actions:
            group_action = GroupActionMapper.dto_to_orm(group_action_dto)
            GroupActionController.save_group_action(group_action, group_action_dto.loaded_fields, activate=False)
        MemoryActivator.activate()

    # Module management

    def module_discover_start(self, timeout):  # type: (int) -> None
        def _stop(): self.module_discover_stop()

        self._master_communicator.do_basic_action(BasicAction(action_type=200,
                                                              action=0,
                                                              extra_parameter=0))

        if self._discover_mode_timer is not None:
            self._discover_mode_timer.cancel()
        self._discover_mode_timer = Timer(timeout, _stop)
        self._discover_mode_timer.start()

    def module_discover_stop(self):  # type: () -> None
        if self._discover_mode_timer is not None:
            self._discover_mode_timer.cancel()
            self._discover_mode_timer = None

        self._master_communicator.do_basic_action(BasicAction(action_type=200,
                                                              action=0,
                                                              extra_parameter=255))
        self._broadcast_module_discovery()

    def module_discover_status(self):  # type: () -> bool
        return self._discover_mode_timer is not None

    def _broadcast_module_discovery(self):
        # type: () -> None
        master_event = MasterEvent(event_type=MasterEvent.Types.MODULE_DISCOVERY, data={})
        self._pubsub.publish_master_event(PubSub.MasterTopics.MODULE, master_event)

    def get_module_log(self):  # type: () -> List[Dict[str, Any]]
        raise NotImplementedError()  # No need to implement. Not used and rather obsolete code anyway

    def get_modules(self):
        def _default_if_255(value, default):
            return value if value != 255 else default

        global_configuration = GlobalConfiguration()

        outputs = []
        nr_of_output_modules = _default_if_255(global_configuration.number_of_output_modules, 0)
        for module_id in range(nr_of_output_modules):
            output_module_info = OutputModuleConfiguration(module_id)
            device_type = output_module_info.device_type
            if device_type == 'o' and output_module_info.address[4:15] in ['000.000.000',
                                                                           '000.000.001',
                                                                           '000.000.002']:
                outputs.append('P')  # Internal output module
            else:
                # Use device_type, except for shutters, which are now kinda output module alike
                outputs.append({'r': 'o',
                                'R': 'O'}.get(device_type, device_type))

        inputs = []
        can_inputs = []
        nr_of_input_modules = _default_if_255(global_configuration.number_of_input_modules, 0)
        nr_of_sensor_modules = _default_if_255(global_configuration.number_of_sensor_modules, 0)
        nr_of_can_controls = _default_if_255(global_configuration.number_of_can_control_modules, 0)
        for module_id in range(nr_of_input_modules):
            input_module_info = InputModuleConfiguration(module_id)
            device_type = input_module_info.device_type
            if device_type == 'i' and input_module_info.address.endswith('000.000.000'):
                inputs.append('J')  # Internal input module
            elif device_type == 'b':
                can_inputs.append('I')  # uCAN input "module"
            elif device_type in ['I', 'i']:
                inputs.append(device_type)  # Slave and virtual input module
        for module_id in range(nr_of_sensor_modules):
            sensor_module_info = SensorModuleConfiguration(module_id)
            device_type = sensor_module_info.device_type
            if device_type == 'T':
                inputs.append('T')
            elif device_type == 's':
                can_inputs.append('T')  # uCAN sensor "module"
        for module_id in range(nr_of_can_controls - 1):
            can_inputs.append('C')
        can_inputs.append('E')

        # i/I/J = Virtual/physical/internal Input module
        # o/O/P = Virtual/physical/internal Ouptut module
        # l = OpenCollector module
        # T/t = Physical/internal Temperature module
        # C/E = Physical/internal CAN Control
        return {'outputs': outputs, 'inputs': inputs, 'shutters': [], 'can_inputs': can_inputs}

    def get_modules_information(self, address=None):  # type: (Optional[str]) -> List[ModuleDTO]
        """ Gets module information """

        def _default_if_255(value, default):
            return value if value != 255 else default

        self._firmware_versions = {}
        self._master_communicator.do_command(command=CoreAPI.request_slave_firmware_versions(),
                                             fields={})

        def _wait_for_version(address_, timeout=3):
            threshold = time.time() + timeout
            while address_ not in self._firmware_versions and time.time() < threshold:
                time.sleep(0.1)
            version_info = self._firmware_versions.get(address_)
            if version_info is None:
                return False, None, None
            return True, None, version_info

        information = []
        module_type_lookup = {'c': ModuleDTO.ModuleType.CAN_CONTROL,
                              't': ModuleDTO.ModuleType.SENSOR,
                              's': ModuleDTO.ModuleType.SENSOR,  # uCAN sensor
                              'i': ModuleDTO.ModuleType.INPUT,
                              'b': ModuleDTO.ModuleType.INPUT,  # uCAN input
                              'o': ModuleDTO.ModuleType.OUTPUT,
                              'l': ModuleDTO.ModuleType.OPEN_COLLECTOR,
                              'r': ModuleDTO.ModuleType.SHUTTER,
                              'd': ModuleDTO.ModuleType.DIM_CONTROL}

        global_configuration = GlobalConfiguration()
        nr_of_input_modules = _default_if_255(global_configuration.number_of_input_modules, 0)
        for module_id in range(nr_of_input_modules):
            input_module_info = InputModuleConfiguration(module_id)
            device_type = input_module_info.device_type
            hardware_type = ModuleDTO.HardwareType.PHYSICAL
            if device_type == 'i':
                if '.000.000.' in input_module_info.address:
                    hardware_type = ModuleDTO.HardwareType.INTERNAL
                else:
                    hardware_type = ModuleDTO.HardwareType.VIRTUAL
            elif device_type == 'b':
                hardware_type = ModuleDTO.HardwareType.EMULATED
            dto = ModuleDTO(source=ModuleDTO.Source.MASTER,
                            address=input_module_info.address,
                            module_type=module_type_lookup.get(device_type.lower()),
                            hardware_type=hardware_type,
                            order=module_id)
            if hardware_type == ModuleDTO.HardwareType.PHYSICAL:
                dto.online, dto.hardware_version, dto.firmware_version = _wait_for_version(input_module_info.address)
            information.append(dto)

        nr_of_output_modules = _default_if_255(global_configuration.number_of_output_modules, 0)
        for module_id in range(nr_of_output_modules):
            output_module_info = OutputModuleConfiguration(module_id)
            device_type = output_module_info.device_type
            hardware_type = ModuleDTO.HardwareType.PHYSICAL
            if device_type in ['l', 'o', 'd']:
                if '.000.000.' in output_module_info.address:
                    hardware_type = ModuleDTO.HardwareType.INTERNAL
                else:
                    hardware_type = ModuleDTO.HardwareType.VIRTUAL
            dto = ModuleDTO(source=ModuleDTO.Source.MASTER,
                            address=output_module_info.address,
                            module_type=module_type_lookup.get(device_type.lower()),
                            hardware_type=hardware_type,
                            order=module_id)
            if hardware_type == ModuleDTO.HardwareType.PHYSICAL:
                dto.online, dto.hardware_version, dto.firmware_version = _wait_for_version(output_module_info.address)
            information.append(dto)

        nr_of_sensor_modules = _default_if_255(global_configuration.number_of_sensor_modules, 0)
        for module_id in range(nr_of_sensor_modules):
            sensor_module_info = SensorModuleConfiguration(module_id)
            device_type = sensor_module_info.device_type
            hardware_type = ModuleDTO.HardwareType.PHYSICAL
            if device_type == 't':
                if '.000.000.' in sensor_module_info.address:
                    hardware_type = ModuleDTO.HardwareType.INTERNAL
                else:
                    hardware_type = ModuleDTO.HardwareType.VIRTUAL
            dto = ModuleDTO(source=ModuleDTO.Source.MASTER,
                            address=sensor_module_info.address,
                            module_type=module_type_lookup.get(device_type.lower()),
                            hardware_type=hardware_type,
                            order=module_id)
            if hardware_type == ModuleDTO.HardwareType.PHYSICAL:
                dto.online, dto.hardware_version, dto.firmware_version = _wait_for_version(sensor_module_info.address)
            information.append(dto)

        nr_of_can_controls = _default_if_255(global_configuration.number_of_can_control_modules, 0)
        for module_id in range(nr_of_can_controls):
            can_control_module_info = CanControlModuleConfiguration(module_id)
            device_type = can_control_module_info.device_type
            hardware_type = ModuleDTO.HardwareType.PHYSICAL
            if module_id == 0:
                hardware_type = ModuleDTO.HardwareType.INTERNAL
            dto = ModuleDTO(source=ModuleDTO.Source.MASTER,
                            address=can_control_module_info.address,
                            module_type=module_type_lookup.get(device_type.lower()),
                            hardware_type=hardware_type,
                            order=module_id)
            if hardware_type == ModuleDTO.HardwareType.PHYSICAL:
                dto.online, dto.hardware_version, dto.firmware_version = _wait_for_version(can_control_module_info.address)
            information.append(dto)

        return information

    def _handle_firmware_information(self, information):  # type: (Dict[str, str]) -> None
        raw_version = information['version']
        version = None if raw_version == '0.0.0' else raw_version
        self._firmware_versions[information['address']] = version

    def replace_module(self, old_address, new_address):  # type: (str, str) -> None
        raise NotImplementedError('Module replacement not supported')

    def flash_leds(self, led_type, led_id):  # type: (int, int) -> str
        """
        Flash the leds on the module for an output/input/sensor.
        :param led_type: The module type, see `IndicateType`.
        :param led_id: The id of the output/input/sensor.
        """
        all_types = [IndicateType.INPUT,
                     IndicateType.OUTPUT,
                     IndicateType.SENSOR]
        if led_type not in all_types:
            raise ValueError('Module indication can only be executed on types: {0}'.format(', '.join(str(t) for t in all_types)))
        if led_type == IndicateType.OUTPUT:
            output = OutputConfiguration(led_id)
            if output.is_shutter:
                self._master_communicator.do_basic_action(BasicAction(action_type=10, action=200, device_nr=led_id // 2))
            else:
                self._master_communicator.do_basic_action(BasicAction(action_type=0, action=200, device_nr=led_id))
        elif led_type == IndicateType.INPUT:
            self._master_communicator.do_basic_action(BasicAction(action_type=1, action=200, device_nr=led_id))
        elif led_type == IndicateType.SENSOR:
            self._master_communicator.do_basic_action(BasicAction(action_type=8, action=200, device_nr=led_id))
        return 'OK'

    # Virtual modules

    def add_virtual_output_module(self):
        # type: () -> None
        self._add_virtual_module(OutputModuleConfiguration, 'output', 'o')
        self._broadcast_module_discovery()

    def add_virtual_dim_control_module(self):
        # type: () -> None
        self._add_virtual_module(OutputModuleConfiguration, 'output', 'd')
        self._broadcast_module_discovery()

    def add_virtual_input_module(self):
        # type: () -> None
        self._add_virtual_module(InputModuleConfiguration, 'input', 'i')
        self._broadcast_module_discovery()

    def add_virtual_sensor_module(self):
        # type: () -> None
        self._add_virtual_module(SensorModuleConfiguration, 'sensor', 't')
        self._broadcast_module_discovery()

    def _add_virtual_module(self, configuration_type, module_type_name, module_type):
        # type: (Union[Type[OutputModuleConfiguration], Type[InputModuleConfiguration], Type[SensorModuleConfiguration]], str, str) -> None
        def _default_if_255(value, default):
            return value if value != 255 else default

        global_configuration = GlobalConfiguration()
        number_of_modules = _default_if_255(getattr(global_configuration, 'number_of_{0}_modules'.format(module_type_name)), 0)
        addresses = []  # type: List[int]
        for module_id in range(number_of_modules):
            module_info = configuration_type(module_id)
            device_type = module_info.device_type
            if device_type == module_type:
                parts = [int(part) for part in module_info.address[4:15].split('.')]
                address = parts[0] * 256 * 256 + parts[1] * 256 + parts[2]
                if address >= 256:
                    addresses.append(address)
        addresses_and_none = [a for a in sorted(addresses)]  # type: List[Optional[int]]  # Iterate through the sorted list to work around List invariance
        addresses_and_none.append(None)
        next_address = next(i for i, e in enumerate(addresses_and_none, 256) if i != e)
        new_address = bytearray([ord(module_type)]) + struct.pack('>I', next_address)[-3:]
        self._master_communicator.do_basic_action(BasicAction(action_type={'output': 201,
                                                                           'input': 202,
                                                                           'sensor': 203}[module_type_name],
                                                              action=number_of_modules,  # 0-based, so no +1 needed here
                                                              device_nr=struct.unpack('>H', new_address[0:2])[0],
                                                              extra_parameter=struct.unpack('>H', new_address[2:4])[0]))
        self._master_communicator.do_basic_action(BasicAction(action_type=200,
                                                              action=4,
                                                              device_nr={'output': 0,
                                                                         'input': 1,
                                                                         'sensor': 2}[module_type_name],
                                                              extra_parameter=number_of_modules + 1))

    # Generic

    def power_cycle_bus(self):
        raise NotImplementedError()

    def get_status(self):
        firmware_version = self._master_communicator.do_command(CoreAPI.get_firmware_version(), {})['version']
        rs485_mode = self._master_communicator.do_command(CoreAPI.get_master_modes(), {})['rs485_mode']
        date_time = self._master_communicator.do_command(CoreAPI.get_date_time(), {})
        return {'time': '{0:02}:{1:02}'.format(date_time['hours'], date_time['minutes']),
                'date': '{0:02}/{1:02}/20{2:02}'.format(date_time['day'], date_time['month'], date_time['year']),
                'mode': {CoreAPI.SlaveBusMode.INIT: 'I',
                         CoreAPI.SlaveBusMode.LIVE: 'L',
                         CoreAPI.SlaveBusMode.TRANSPARENT: 'T'}[rs485_mode],
                'version': firmware_version,
                'hw_version': 1}  # TODO: Hardware version

    def reset(self):
        # type: () -> None
        self._master_communicator.do_basic_action(BasicAction(action_type=254, action=0), timeout=None)

    def cold_reset(self, power_on=True):
        # type: (bool) -> None
        _ = self  # Must be an instance method
        with open('/sys/class/gpio/gpio49/direction', 'w') as gpio_direction:
            gpio_direction.write('out')

        def power(master_on):
            """ Set the power on the master. """
            with open('/sys/class/gpio/gpio49/value', 'w') as gpio_file:
                gpio_file.write('0' if master_on else '1')

        power(False)
        if power_on:
            time.sleep(5)
            power(True)

        self._master_communicator.reset_communication_statistics()

    def update_master(self, hex_filename):
        # type: (str) -> None
        CoreUpdater.update(hex_filename=hex_filename)

    def get_backup(self):
        data = bytearray()
        pages, page_length = MemoryFile.SIZES[MemoryTypes.EEPROM]
        for page in range(pages):
            page_address = MemoryAddress(memory_type=MemoryTypes.EEPROM, page=page, offset=0, length=page_length)
            data += self._memory_file.read([page_address])[page_address]
        return ''.join(str(chr(entry)) for entry in data)

    def restore(self, data):
        pages, page_length = MemoryFile.SIZES[MemoryTypes.EEPROM]
        data_structure = {}  # type: Dict[int, bytearray]
        for page in range(pages):
            page_data = bytearray([ord(entry) for entry in data[page * page_length:(page + 1) * page_length]])
            if len(page_data) < page_length:
                page_data += bytearray([255] * (page_length - len(page_data)))
            data_structure[page] = page_data
        self._restore(data_structure)

    def factory_reset(self):
        pages, page_length = MemoryFile.SIZES[MemoryTypes.EEPROM]
        data_set = {page: bytearray([255] * page_length) for page in range(pages)}
        # data_set[0][0] = 1  # Needed to validate Brain+ with no front panel attached
        self._restore(data_set)

    def _restore(self, data):  # type: (Dict[int, bytearray]) -> None
        amount_of_pages, page_length = MemoryFile.SIZES[MemoryTypes.EEPROM]
        page_retry = None
        current_page = amount_of_pages - 1
        while current_page >= 0:
            try:
                page_address = MemoryAddress(memory_type=MemoryTypes.EEPROM, page=current_page, offset=0, length=page_length)
                self._memory_file.write({page_address: data[current_page]})
                current_page -= 1
            except CommunicationTimedOutException:
                if page_retry == current_page:
                    raise
                page_retry = current_page
                time.sleep(10)
        time.sleep(5)  # Give the master some time to settle
        self.cold_reset()  # Cold reset, enforcing a reload of all settings

    def error_list(self):
        return []  # TODO: Implement

    def last_success(self):
        return 0.0  # TODO: Implement

    def clear_error_list(self):
        raise NotImplementedError()

    def set_status_leds(self, status):
        raise NotImplementedError()

    # All lights actions

    def set_all_lights(self, action, floor_id=None, output_ids=None):
        # type: (Literal['ON', 'OFF', 'TOGGLE'], Optional[int], Optional[List[int]]) -> None
        _ = floor_id  # Ignored, the Core Master does not know about floors

        if output_ids is None and action == 'OFF':
            # All lights off
            self._master_communicator.do_basic_action(BasicAction(action_type=0,
                                                                  action=255,
                                                                  device_nr=1))
            return

        ba_action = {'ON': 1, 'OFF': 0, 'TOGGLE': 16}[action]

        if output_ids is None:
            # None means "all lights"
            output_ids = list(self._enumerate_io_modules('output'))
        filtered_output_ids = []
        for output_id in output_ids:
            output = OutputConfiguration(output_id)
            if not output.is_shutter and output.output_type >= 128:
                filtered_output_ids.append(output.id)

        # Execute action in batch; either a single BA (for 1 device) or a BA series (for 2 to 40 devices)
        for i in range(0, len(output_ids), 40):
            chunk_output_ids = output_ids[i:i + 40]
            if len(chunk_output_ids) == 1:
                self._master_communicator.do_basic_action(BasicAction(action_type=0,
                                                                      action=ba_action,
                                                                      device_nr=chunk_output_ids[0]))
            else:
                self._master_communicator.do_command(command=CoreAPI.execute_basic_action_series(len(chunk_output_ids)),
                                                     fields={'type': 0, 'action': ba_action, 'extra_parameter': 0,
                                                             'device_nrs': chunk_output_ids})

    def get_configuration_dirty_flag(self):
        return False  # TODO: Implement

    # Legacy

    def load_scheduled_actions(self):
        # type: (Any) -> List[LegacyScheduleDTO]
        return []

    def load_startup_action(self):
        # type: (Any) -> LegacyStartupActionDTO
        return LegacyStartupActionDTO(actions=[])

    def load_dimmer_configuration(self, fields=None):
        # type: (Any) -> Dict[str,Any]
        return {'min_dim_level': 0,  # TODO: Implement
                'dim_step': 0,
                'dim_wait_cycle': 0,
                'dim_memory': 0}


class MasterInputState(object):
    def __init__(self, interval=300):
        # type: (int) -> None
        self._interval = interval
        self._last_updated = 0  # type: float
        self._values = {}  # type: Dict[int,MasterInputValue]

    def get_inputs(self):
        # type: () -> List[Dict[str,Any]]
        return [x.serialize() for x in self._values.values()]

    def get_recent(self):
        # type: () -> List[int]
        sorted_inputs = sorted(list(self._values.values()), key=lambda x: x.changed_at)
        recent_events = [x.input_id for x in sorted_inputs
                         if x.changed_at > time.time() - 10]
        return recent_events[-5:]

    def handle_event(self, core_event):
        # type: (MasterCoreEvent) -> MasterEvent
        value = MasterInputValue.from_core_event(core_event)
        if value.input_id not in self._values:
            self._values[value.input_id] = value
        self._values[value.input_id].update(value)
        return value.master_event()

    def should_refresh(self):
        # type: () -> bool
        return self._last_updated + self._interval < time.time()

    def refresh(self, info):
        # type: (List[int]) -> List[MasterEvent]
        events = []
        for i, byte in enumerate(info):
            for j in range(0, 8):
                current_status = byte >> j & 0x1
                input_id = (i * 8) + j
                if input_id not in self._values:
                    self._values[input_id] = MasterInputValue(input_id, current_status)
                state = self._values[input_id]
                if state.update_status(current_status):
                    events.append(state.master_event())
        self._last_updated = time.time()
        return events


class MasterInputValue(object):
    def __init__(self, input_id, status, changed_at=0):
        # type: (int, int, float) -> None
        self.input_id = input_id
        self.status = status
        self.changed_at = changed_at

    @classmethod
    def from_core_event(cls, event):
        # type: (MasterCoreEvent) -> MasterInputValue
        status = 1 if event.data['status'] else 0
        changed_at = time.time()
        return cls(event.data['input'], status, changed_at=changed_at)

    def serialize(self):
        # type: () -> Dict[str,Any]
        return {'id': self.input_id, 'status': self.status}  # TODO: output?

    def update(self, other_value):
        # type: (MasterInputValue) -> None
        self.update_status(other_value.status)

    def update_status(self, current_status):
        # type: (int) -> bool
        is_changed = self.status != current_status
        if is_changed:
            self.status = current_status
            self.changed_at = time.time()
        return is_changed

    def master_event(self):
        # type: () -> MasterEvent
        return MasterEvent(event_type=MasterEvent.Types.INPUT_CHANGE,
                           data={'id': self.input_id,
                                 'status': bool(self.status),
                                 'location': {'room_id': 255}})  # TODO: missing room

    def __repr__(self):
        # type: () -> str
        return '<MasterInputValue {} {} {}>'.format(self.input_id, self.status, self.changed_at)
