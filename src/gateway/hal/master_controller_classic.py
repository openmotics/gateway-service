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
import logging
import time
from datetime import datetime
from threading import Thread, Timer

from gateway.hal.master_controller import MasterController, MasterEvent
from gateway.maintenance_communicator import InMaintenanceModeException
from ioc import INJECTED, Inject, Injectable, Singleton
from master import eeprom_models, master_api
from master.eeprom_models import CanLedConfiguration, DimmerConfiguration, \
    EepromAddress, GroupActionConfiguration, RoomConfiguration, \
    ScheduledActionConfiguration, ShutterConfiguration, \
    ShutterGroupConfiguration, StartupActionConfiguration
from master.inputs import InputStatus
from master.master_communicator import BackgroundConsumer
from master.outputs import OutputStatus
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("openmotics")


@Injectable.named('master_controller')
@Singleton
class MasterClassicController(MasterController):

    @Inject
    def __init__(self,
                 master_communicator=INJECTED,
                 configuration_controller=INJECTED,
                 eeprom_controller=INJECTED):
        """
        :type master_communicator: master.master_communicator.MasterCommunicator
        :type eeprom_controller: master.eeprom_controller.EepromController
        """
        super(MasterClassicController, self).__init__(master_communicator)
        self._config_controller = configuration_controller
        self._eeprom_controller = eeprom_controller
        self._plugin_controller = None  # type: Optional[Any]

        self._input_status = InputStatus(on_input_change=self._input_changed)
        self._output_status = OutputStatus(on_output_change=self._output_changed)
        self._settings_last_updated = 0.0
        self._time_last_updated = 0.0
        self._synchronization_thread = Thread(target=self._synchronize, name='ClassicMasterSynchronization')
        self._synchronization_thread.daemon = True
        self._master_version = None
        self._master_online = False
        self._input_interval = 300
        self._input_last_updated = 0
        self._input_config = {}
        self._output_interval = 600
        self._output_last_updated = 0
        self._output_config = {}

        self._discover_mode_timer = None  # type: Optional[Timer]
        self._module_log = []  # type: List[Tuple[str,str]]

        self._master_communicator.register_consumer(
            BackgroundConsumer(master_api.output_list(), 0, self._on_master_output_change, True)
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(master_api.event_triggered(), 0, self._on_master_event, True)
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(master_api.module_initialize(), 0, self._update_modules)
        )

    #################
    # Private stuff #
    #################

    def _synchronize(self):
        # type: () -> None
        while True:
            try:
                now = time.time()
                self._get_master_version()
                # Validate communicator checks
                if self._time_last_updated < now - 300:
                    self._check_master_time()
                    self._time_last_updated = now
                if self._settings_last_updated < now - 900:
                    self._check_master_settings()
                    self._settings_last_updated = now
                # Refresh if required
                if self._output_last_updated + self._output_interval < now:
                    self._refresh_outputs()
                    self._set_master_state(True)
                if self._input_last_updated + self._input_interval < now:
                    self._refresh_inputs()
                    self._set_master_state(True)
                time.sleep(1)
            except CommunicationTimedOutException:
                logger.error('Got communication timeout during synchronization, waiting 10 seconds.')
                self._set_master_state(False)
                time.sleep(10)
            except InMaintenanceModeException:
                # This is an expected situation
                time.sleep(10)
            except Exception as ex:
                logger.exception('Unexpected error during synchronization: {0}'.format(ex))
                time.sleep(10)

    def _get_master_version(self):
        if self._master_version is None:
            self._master_version = self.get_firmware_version()
            self._set_master_state(True)
            self._register_version_depending_background_consumers()

    def _set_master_state(self, online):
        if online != self._master_online:
            self._master_online = online

    def _register_version_depending_background_consumers(self):
        self._master_communicator.register_consumer(
            BackgroundConsumer(master_api.input_list(self._master_version), 0,
                               self._on_master_input_change)
        )

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

        if eeprom_data[11] != chr(255):
            logger.info('Disabling async RO messages.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 11, 'data': chr(255)}
            )
            write = True

        if eeprom_data[18] != chr(0):
            logger.info('Enabling async OL messages.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 18, 'data': chr(0)}
            )
            write = True

        if eeprom_data[20] != chr(0):
            logger.info('Enabling async IL messages.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 20, 'data': chr(0)}
            )
            write = True

        if eeprom_data[28] != chr(0):
            logger.info('Enabling async SO messages.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 28, 'data': chr(0)}
            )
            write = True

        thermostat_mode = ord(eeprom_data[14])
        if thermostat_mode & 64 == 0:
            logger.info('Enabling multi-tenant thermostats.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 14, 'data': chr(thermostat_mode | 64)}
            )
            write = True

        if eeprom_data[59] != chr(32):
            logger.info('Enabling 32 thermostats.')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 59, 'data': chr(32)}
            )
            write = True

        if eeprom_data[24] != chr(0):
            logger.info('Disable auto-reset thermostat setpoint')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 24, 'data': chr(0)}
            )
            write = True

        if eeprom_data[13] != chr(0):
            logger.info('Configure master startup mode to: API')
            self._master_communicator.do_command(
                master_api.write_eeprom(),
                {'bank': 0, 'address': 13, 'data': chr(0)}
            )
            write = True

        if write:
            self._master_communicator.do_command(master_api.activate_eeprom(), {'eep': 0})
        self.set_status_leds(True)

    def _on_master_event(self, event_data):
        # type: (Dict[str,Any]) -> None
        """ Handle an event triggered by the master. """
        code = event_data['code']
        if self._plugin_controller is not None:
            self._plugin_controller.process_event(code)

    #######################
    # Internal management #
    #######################

    def start(self):
        super(MasterClassicController, self).start()
        self._synchronization_thread.start()

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

    def invalidate_caches(self):
        # type: () -> None
        self._eeprom_controller.invalidate_cache()  # Eeprom can be changed in maintenance mode.
        self._eeprom_controller.dirty = True
        self._input_last_updated = 0
        self._output_last_updated = 0

    def get_firmware_version(self):
        out_dict = self._master_communicator.do_command(master_api.status())
        return int(out_dict['f1']), int(out_dict['f2']), int(out_dict['f3'])

    # Memory (eeprom/fram)

    def eeprom_read_page(self, page):
        # TODO: Use eeprom controller
        return self._master_communicator.do_command(master_api.eeprom_list(), {'bank': page})['data']

    def fram_read_page(self, page):
        raise NotImplementedError('A classic master does not support FRAM')

    # Input

    def get_input_module_type(self, input_module_id):
        o = self._eeprom_controller.read(eeprom_models.InputConfiguration, input_module_id * 8, ['module_type'])
        return o.module_type

    def get_inputs_with_status(self):
        # type: () -> List[Dict[str,Any]]
        return self._input_status.get_inputs()

    def get_recent_inputs(self):
        # type: () -> List[int]
        return self._input_status.get_recent()

    def load_input(self, input_id, fields=None):
        o = self._eeprom_controller.read(eeprom_models.InputConfiguration, input_id, fields)
        if o.module_type not in ['i', 'I']:  # Only return 'real' inputs
            raise TypeError('The given id {0} is not an input, but {1}'.format(input_id, o.module_type))
        return o.serialize()

    def load_inputs(self, fields=None):
        return [o.serialize() for o in self._eeprom_controller.read_all(eeprom_models.InputConfiguration, fields)
                if o.module_type in ['i', 'I']]  # Only return 'real' inputs

    def save_inputs(self, inputs, fields=None):
        self._eeprom_controller.write_batch([eeprom_models.InputConfiguration.deserialize(input_)
                                             for input_ in inputs])

    def _refresh_inputs(self):
        # type: () -> None
        # 1. refresh input configuration
        self._input_config = {input_configuration['id']: input_configuration
                              for input_configuration in self.load_inputs()}
        # 2. poll for latest input status
        try:
            number_of_input_modules = self._master_communicator.do_command(master_api.number_of_io_modules())['in']
            inputs = []
            for i in xrange(number_of_input_modules):
                # we could be dealing with e.g. a temperature module, skip those
                module_type = self.get_input_module_type(i)
                if module_type not in ['i', 'I']:
                    continue
                result = self._master_communicator.do_command(master_api.read_input_module(self._master_version), {'input_module_nr': i})
                module_status = result['input_status']
                # module_status byte contains bits for each individual input, use mask and bitshift to get status
                for n in xrange(8):
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
                self._master_communicator.do_command(
                    master_api.basic_action(),
                    {'action_type': dimmer_action, 'action_number': output_id}
                )

        if not state:
            self._master_communicator.do_command(
                master_api.basic_action(),
                {'action_type': master_api.BA_LIGHT_OFF, 'action_number': output_id}
            )
            return

        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_LIGHT_ON, 'action_number': output_id}
        )

        if timer is not None:
            timer_action = getattr(master_api, 'BA_LIGHT_ON_TIMER_{0}_OVERRULE'.format(timer))
            self._master_communicator.do_command(
                master_api.basic_action(),
                {'action_type': timer_action, 'action_number': output_id}
            )

    def toggle_output(self, output_id):
        if output_id is None or output_id < 0 or output_id > 240:
            raise ValueError('Output ID {0} not in range 0 <= id <= 240'.format(output_id))

        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_LIGHT_TOGGLE, 'action_number': output_id}
        )

    def load_output(self, output_id, fields=None):
        return self._eeprom_controller.read(eeprom_models.OutputConfiguration, output_id, fields).serialize()

    def load_outputs(self, fields=None):
        return [o.serialize() for o in self._eeprom_controller.read_all(eeprom_models.OutputConfiguration, fields)]

    def save_outputs(self, outputs, fields=None):
        self._eeprom_controller.write_batch([eeprom_models.OutputConfiguration.deserialize(output)
                                             for output in outputs])
        for output in outputs:
            output_nr, timer = output['id'], output.get('timer')
            if timer is not None:
                self._master_communicator.do_command(
                    master_api.write_timer(),
                    {'id': output_nr, 'timer': timer}
                )
        self._output_last_updated = 0

    def get_output_statuses(self):
        return self._output_status.get_outputs()

    def get_output_status(self, output_id):
        return self._output_status.get_output(output_id)

    def _input_changed(self, input_id, status):
        # type: (int, str) -> None
        """ Executed by the Input Status tracker when an input changed state """
        input_configuration = self._input_config.get(input_id)
        if input_configuration is None:
            # An event was received from an input for which the configuration was not yet loaded. As
            # configuraion should not be loaded inside an event handler, the event is discarded.
            # TODO: Detach input even processing from event handler so it can load the configuration if needed
            return
        for callback in self._event_callbacks:
            event_data = {'id': input_id,
                          'status': status,
                          'location': {'room_id': input_configuration.get('room', 255)}}
            callback(MasterEvent(event_type=MasterEvent.Types.INPUT_CHANGE, data=event_data))

    def _refresh_outputs(self):
        self._output_config = self.load_outputs()
        number_of_outputs = self._master_communicator.do_command(master_api.number_of_io_modules())['out'] * 8
        outputs = []
        for i in xrange(number_of_outputs):
            outputs.append(self._master_communicator.do_command(master_api.read_output(), {'id': i}))
        self._output_status.full_update(outputs)
        self._output_last_updated = time.time()

    def _output_changed(self, output_id, status):
        """ Executed by the Output Status tracker when an output changed state """
        event_status = {'on': status['on']}
        # 1. only add value to status when handling dimmers
        if self._output_config[output_id]['module_type'] in ['d', 'D']:
            event_status['value'] = status['value']
        # 2. format response data
        event_data = {'id': output_id,
                      'status': event_status,
                      'location': {'room_id': self._output_config[output_id]['room']}}
        for callback in self._event_callbacks:
            callback(MasterEvent(event_type=MasterEvent.Types.OUTPUT_CHANGE, data=event_data))

    def _on_master_output_change(self, data):
        """ Triggers when the master informs us of an Output state change """
        self._output_status.partial_update(data['outputs'])

    # Shutters

    def shutter_up(self, shutter_id):
        self._master_communicator.do_basic_action(master_api.BA_SHUTTER_UP, shutter_id)

    def shutter_down(self, shutter_id):
        self._master_communicator.do_basic_action(master_api.BA_SHUTTER_DOWN, shutter_id)

    def shutter_stop(self, shutter_id):
        self._master_communicator.do_basic_action(master_api.BA_SHUTTER_STOP, shutter_id)

    def shutter_group_up(self, group_id):
        """ Make a shutter group go up. The shutters stop automatically when the up position is
        reached (after the predefined number of seconds).

        :param group_id: The id of the shutter group.
        :type group_id: Byte
        :returns:'status': 'OK'.
        """
        if group_id < 0 or group_id > 30:
            raise ValueError('id not in [0, 30]: %d' % group_id)

        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_SHUTTER_GROUP_UP, 'action_number': id}
        )

        return {'status': 'OK'}

    def shutter_group_down(self, group_id):
        """ Make a shutter group go down. The shutters stop automatically when the down position is
        reached (after the predefined number of seconds).

        :param group_id: The id of the shutter group.
        :type group_id: Byte
        :returns:'status': 'OK'.
        """
        if group_id < 0 or group_id > 30:
            raise ValueError('id not in [0, 30]: %d' % group_id)

        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_SHUTTER_GROUP_DOWN, 'action_number': group_id}
        )

        return {'status': 'OK'}

    def shutter_group_stop(self, group_id):
        """ Make a shutter group stop.

        :param group_id: The id of the shutter group.
        :type group_id: Byte
        :returns:'status': 'OK'.
        """
        if group_id < 0 or group_id > 30:
            raise ValueError('id not in [0, 30]: %d' % group_id)

        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_SHUTTER_GROUP_STOP, 'action_number': group_id}
        )

        return {'status': 'OK'}

    def load_shutter_configuration(self, shutter_id, fields=None):
        # type: (int, Any) -> Dict[str,Any]
        # TODO: work with shutter controller
        return self._eeprom_controller.read(ShutterConfiguration, shutter_id, fields).serialize()

    def load_shutter_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        # TODO: work with shutter controller
        return [o.serialize() for o in self._eeprom_controller.read_all(ShutterConfiguration, fields)]

    def save_shutter_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        # TODO: work with shutter controller
        self._eeprom_controller.write(ShutterConfiguration.deserialize(config))

    def save_shutter_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        # TODO: work with shutter controller
        self._eeprom_controller.write_batch([ShutterConfiguration.deserialize(o) for o in config])

    def load_shutter_group_configuration(self, group_id, fields=None):
        # type: (int, Any) -> Dict[str,Any]
        # TODO: work with shutter controller
        return self._eeprom_controller.read(ShutterGroupConfiguration, group_id, fields).serialize()

    def load_shutter_group_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        # TODO: work with shutter controller
        return [o.serialize() for o in self._eeprom_controller.read_all(ShutterGroupConfiguration, fields)]

    def save_shutter_group_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        # TODO: work with shutter controller
        self._eeprom_controller.write(ShutterGroupConfiguration.deserialize(config))

    def save_shutter_group_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        # TODO: work with shutter controller
        self._eeprom_controller.write_batch([ShutterGroupConfiguration.deserialize(o) for o in config])

    # Virtual modules

    def add_virtual_output_module(self):
        """ Adds a virtual output module.
        :returns: dict with 'status'.
        """
        module = self._master_communicator.do_command(master_api.add_virtual_module(), {'vmt': 'o'})
        return {'status': module.get('resp')}

    def add_virtual_dim_module(self):
        """ Adds a virtual dim module.
        :returns: dict with 'status'.
        """
        module = self._master_communicator.do_command(master_api.add_virtual_module(), {'vmt': 'd'})
        return {'status': module.get('resp')}

    def add_virtual_input_module(self):
        """ Adds a virtual input module.
        :returns: dict with 'status'.
        """
        module = self._master_communicator.do_command(master_api.add_virtual_module(), {'vmt': 'i'})
        return {'status': module.get('resp')}

    # Generic

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
            is_can = ret['data'][0] == 'C'
            ret = self._master_communicator.do_command(
                master_api.read_eeprom(),
                {'bank': 2 + i, 'addr': 0, 'num': 1}
            )
            if is_can:
                can_inputs.append(ret['data'][0])
            else:
                inputs.append(ret['data'][0])

        for i in range(mods['out']):
            ret = self._master_communicator.do_command(
                master_api.read_eeprom(),
                {'bank': 33 + i, 'addr': 0, 'num': 1}
            )
            outputs.append(ret['data'][0])

        for shutter in range(mods['shutter']):
            shutters.append('S')

        if len(can_inputs) > 0 and 'C' not in can_inputs:
            can_inputs.append('C')  # First CAN enabled installations didn't had this in the eeprom yet

        return {'outputs': outputs, 'inputs': inputs, 'shutters': shutters, 'can_inputs': can_inputs}

    def get_modules_information(self):
        """ Gets module information """

        def get_master_version(eeprom_address, _is_can=False):
            _module_address = self._eeprom_controller.read_address(eeprom_address)
            formatted_address = '{0:03}.{1:03}.{2:03}.{3:03}'.format(ord(_module_address.bytes[0]),
                                                                     ord(_module_address.bytes[1]),
                                                                     ord(_module_address.bytes[2]),
                                                                     ord(_module_address.bytes[3]))
            try:
                if _is_can or _module_address.bytes[0].lower() == _module_address.bytes[0]:
                    return formatted_address, None, None
                _module_version = self._master_communicator.do_command(master_api.get_module_version(),
                                                                       {'addr': _module_address.bytes},
                                                                       extended_crc=True,
                                                                       timeout=1)
                _firmware_version = '{0}.{1}.{2}'.format(_module_version['f1'], _module_version['f2'], _module_version['f3'])
                return formatted_address, _module_version['hw_version'], _firmware_version
            except CommunicationTimedOutException:
                return formatted_address, None, None

        information = {}

        # Master slave modules
        no_modules = self._master_communicator.do_command(master_api.number_of_io_modules())
        for i in range(no_modules['in']):
            is_can = self._eeprom_controller.read_address(EepromAddress(2 + i, 252, 1)).bytes == 'C'
            version_info = get_master_version(EepromAddress(2 + i, 0, 4), is_can)
            module_address, hardware_version, firmware_version = version_info
            module_type = self._eeprom_controller.read_address(EepromAddress(2 + i, 0, 1)).bytes
            information[module_address] = {'type': module_type,
                                           'hardware': hardware_version,
                                           'firmware': firmware_version,
                                           'address': module_address,
                                           'is_can': is_can}
        for i in range(no_modules['out']):
            version_info = get_master_version(EepromAddress(33 + i, 0, 4))
            module_address, hardware_version, firmware_version = version_info
            module_type = self._eeprom_controller.read_address(EepromAddress(33 + i, 0, 1)).bytes
            information[module_address] = {'type': module_type,
                                           'hardware': hardware_version,
                                           'firmware': firmware_version,
                                           'address': module_address}
        for i in range(no_modules['shutter']):
            version_info = get_master_version(EepromAddress(33 + i, 173, 4))
            module_address, hardware_version, firmware_version = version_info
            module_type = self._eeprom_controller.read_address(EepromAddress(33 + i, 173, 1)).bytes
            information[module_address] = {'type': module_type,
                                           'hardware': hardware_version,
                                           'firmware': firmware_version,
                                           'address': module_address}

        return information

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

    def get_backup(self):
        """
        Get a backup of the eeprom of the master.

        :returns: String of bytes (size = 64kb).
        """
        retry = None
        output = ""
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
        return output

    def factory_reset(self):
        # Wipe master EEPROM
        data = chr(255) * (256 * 256)
        self.restore(data)

    def cold_reset(self):
        """ Perform a cold reset on the master. Turns the power off, waits 5 seconds and
        turns the power back on.

        :returns: 'status': 'OK'.
        """
        _ = self  # Must be an instance method
        gpio_direction = open('/sys/class/gpio/gpio44/direction', 'w')
        gpio_direction.write('out')
        gpio_direction.close()

        def power(master_on):
            """ Set the power on the master. """
            gpio_file = open('/sys/class/gpio/gpio44/value', 'w')
            gpio_file.write('1' if master_on else '0')
            gpio_file.close()

        power(False)
        time.sleep(5)
        power(True)

        return {'status': 'OK'}

    def reset(self):
        """ Reset the master.

        :returns: emtpy dict.
        """
        self._master_communicator.do_command(master_api.reset())
        return dict()

    def power_cycle_bus(self):
        """ Turns the power of both bussed off for 5 seconds """
        self._master_communicator.do_basic_action(master_api.BA_POWER_CYCLE_BUS, 0)

    def restore(self, data):
        """
        Restore a backup of the eeprom of the master.

        :param data: The eeprom backup to restore.
        :type data: string of bytes (size = 64 kb).
        :returns: dict with 'output' key (contains an array with the addresses that were written).
        """
        ret = []
        (num_banks, bank_size, write_size) = (256, 256, 10)

        for bank in range(0, num_banks):
            read = self._master_communicator.do_command(master_api.eeprom_list(),
                                                        {'bank': bank})['data']
            for addr in range(0, bank_size, write_size):
                orig = read[addr:addr + write_size]
                new = data[bank * bank_size + addr: bank * bank_size + addr + len(orig)]
                if new != orig:
                    ret.append('B' + str(bank) + 'A' + str(addr))

                    self._master_communicator.do_command(
                        master_api.write_eeprom(),
                        {'bank': bank, 'address': addr, 'data': new}
                    )

        self._master_communicator.do_command(master_api.activate_eeprom(), {'eep': 0})
        ret.append('Activated eeprom')
        self._eeprom_controller.invalidate_cache()

        return {'output': ret}

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

    def _update_modules(self, api_data):
        # type: (Dict[str,Any]) -> None
        """ Create a log entry when the MI message is received. """
        module_map = {'O': 'output', 'I': 'input', 'T': 'temperature', 'D': 'dimmer'}
        message_map = {'N': 'New %s module found.',
                       'E': 'Existing %s module found.',
                       'D': 'The %s module tried to register but the registration failed, '
                            'please presse the init button again.'}
        default_message = 'Unknown module type %s discovered.'
        log_level_map = {'N': 'INFO', 'E': 'WARN', 'D': 'ERROR'}
        default_level = log_level_map['D']

        module_type = module_map.get(api_data['id'][0])
        message = message_map.get(api_data['instr'], default_message) % module_type
        log_level = log_level_map.get(api_data['instr'], default_level)

        self._module_log.append((log_level, message))

    def module_discover_start(self, timeout):
        # type: (int) -> Dict[str,Any]
        def _stop(): self.module_discover_stop()

        ret = self._master_communicator.do_command(master_api.module_discover_start())

        if self._discover_mode_timer is not None:
            self._discover_mode_timer.cancel()
        self._discover_mode_timer = Timer(timeout, _stop)
        self._discover_mode_timer.start()

        self._module_log = []

        return {'status': ret['resp']}

    def module_discover_stop(self):
        # type: () -> Dict[str,Any]
        if self._discover_mode_timer is not None:
            self._discover_mode_timer.cancel()
            self._discover_mode_timer = None

        self._eeprom_controller.invalidate_cache()
        self._eeprom_controller.dirty = True
        ret = self._master_communicator.do_command(master_api.module_discover_stop())
        self._module_log = []
        return {'status': ret['resp']}

    def module_discover_status(self):
        # type: () -> Dict[str,bool]
        return {'running': self._discover_mode_timer is not None}

    def get_module_log(self):
        # type: () -> Dict[str,Any]
        (log, self._module_log) = (self._module_log, [])
        return {'log': log}

    # Error functions

    def error_list(self):
        """ Get the error list per module (input and output modules). The modules are identified by
        O1, O2, I1, I2, ...

        :returns: dict with 'errors' key, it contains list of tuples (module, nr_errors).
        """
        error_list = self._master_communicator.do_command(master_api.error_list())
        return error_list['errors']

    def last_success(self):
        """ Get the number of seconds since the last successful communication with the master.
        """
        return self._master_communicator.get_seconds_since_last_success()

    def clear_error_list(self):
        """ Clear the number of errors.

        :returns: empty dict.
        """
        self._master_communicator.do_command(master_api.clear_error_list())
        return dict()

    def set_status_leds(self, status):
        """ Set the status of the leds on the master.

        :param status: whether the leds should be on or off.
        :type status: boolean.
        :returns: empty dict.
        """
        on = 1 if status is True else 0
        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_STATUS_LEDS, 'action_number': on}
        )
        return dict()

    # Actions

    def do_basic_action(self, action_type, action_number):
        """ Execute a basic action.

        :param action_type: The type of the action as defined by the master api.
        :type action_type: Integer [0, 254]
        :param action_number: The number provided to the basic action, its meaning depends on the \
        action_type.
        :type action_number: Integer [0, 254]
        """
        if action_type < 0 or action_type > 254:
            raise ValueError('action_type not in [0, 254]: %d' % action_type)

        if action_number < 0 or action_number > 254:
            raise ValueError('action_number not in [0, 254]: %d' % action_number)

        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': action_type,
             'action_number': action_number}
        )

        return dict()

    def do_group_action(self, group_action_id):
        """ Execute a group action.

        :param group_action_id: The id of the group action
        :type group_action_id: Integer (0 - 159)
        :returns: empty dict.
        """
        if group_action_id < 0 or group_action_id > 159:
            raise ValueError('group_action_id not in [0, 160]: %d' % group_action_id)

        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_GROUP_ACTION,
             'action_number': group_action_id}
        )

        return dict()

    # Actions functions

    def load_group_action_configuration(self, group_action_id, fields=None):
        # type: (int, Any) -> Dict[str,Any]
        return self._eeprom_controller.read(GroupActionConfiguration, group_action_id, fields).serialize()

    def load_group_action_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        return [o.serialize() for o in self._eeprom_controller.read_all(GroupActionConfiguration, fields)]

    def save_group_action_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(GroupActionConfiguration.deserialize(config))

    def save_group_action_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        self._eeprom_controller.write_batch([GroupActionConfiguration.deserialize(o) for o in config])

    def load_scheduled_action_configuration(self, scheduled_action_id, fields=None):
        # type: (int, Any) -> Dict[str,Any]
        return self._eeprom_controller.read(ScheduledActionConfiguration, scheduled_action_id, fields).serialize()

    def load_scheduled_action_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        return [o.serialize() for o in self._eeprom_controller.read_all(ScheduledActionConfiguration, fields)]

    def save_scheduled_action_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(ScheduledActionConfiguration.deserialize(config))

    def save_scheduled_action_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        self._eeprom_controller.write_batch([ScheduledActionConfiguration.deserialize(o) for o in config])

    def load_startup_action_configuration(self, fields=None):
        # type: (Any) -> Dict[str,Any]
        return self._eeprom_controller.read(StartupActionConfiguration, fields).serialize()

    def save_startup_action_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(StartupActionConfiguration.deserialize(config))

    # Dimmer functions

    def load_dimmer_configuration(self, fields=None):
        # type: (Any) -> Dict[str,Any]
        return self._eeprom_controller.read(DimmerConfiguration, fields).serialize()

    def save_dimmer_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(DimmerConfiguration.deserialize(config))

    # Can Led functions

    def load_can_led_configuration(self, can_led_id, fields=None):
        # type: (int, Any) -> Dict[str,Any]
        return self._eeprom_controller.read(CanLedConfiguration, can_led_id, fields).serialize()

    def load_can_led_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        return [o.serialize() for o in self._eeprom_controller.read_all(CanLedConfiguration, fields)]

    def save_can_led_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(CanLedConfiguration.deserialize(config))

    def save_can_led_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        self._eeprom_controller.write_batch([CanLedConfiguration.deserialize(o) for o in config])

    # Room functions

    def load_room_configuration(self, room_id, fields=None):
        # type: (int, Any) -> Dict[str,Any]
        return self._eeprom_controller.read(RoomConfiguration, room_id, fields).serialize()

    def load_room_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        return [o.serialize() for o in self._eeprom_controller.read_all(RoomConfiguration, fields)]

    def save_room_configuration(self, config):
        # type: (Dict[str,Any]) -> None
        self._eeprom_controller.write(RoomConfiguration.deserialize(config))

    def save_room_configurations(self, config):
        # type: (List[Dict[str,Any]]) -> None
        self._eeprom_controller.write_batch([RoomConfiguration.deserialize(o) for o in config])

    # All lights off functions

    def set_all_lights_off(self):
        """ Turn all lights off.

        :returns: empty dict.
        """
        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_ALL_LIGHTS_OFF, 'action_number': 0}
        )
        return dict()

    def set_all_lights_floor_off(self, floor):
        """ Turn all lights on a given floor off.

        :returns: empty dict.
        """

        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_LIGHTS_OFF_FLOOR, 'action_number': floor}
        )
        return dict()

    def set_all_lights_floor_on(self, floor):
        """ Turn all lights on a given floor on.

        :returns: empty dict.
        """
        self._master_communicator.do_command(
            master_api.basic_action(),
            {'action_type': master_api.BA_LIGHTS_ON_FLOOR, 'action_number': floor}
        )
        return dict()

    # Sensors

    def get_sensor_temperature(self, sensor_id):
        if sensor_id is None or sensor_id < 0 or sensor_id > 31:
            raise ValueError('Sensor ID {0} not in range 0 <= id <= 31'.format(sensor_id))
        return self.get_sensors_temperature()[sensor_id]

    def get_sensors_temperature(self):
        temperatures = []
        sensor_list = self._master_communicator.do_command(master_api.sensor_temperature_list())
        for i in xrange(32):
            temperatures.append(sensor_list['tmp{0}'.format(i)].get_temperature())
        return temperatures

    def get_sensor_humidity(self, sensor_id):
        if sensor_id is None or sensor_id < 0 or sensor_id > 31:
            raise ValueError('Sensor ID {0} not in range 0 <= id <= 31'.format(sensor_id))
        return self.get_sensors_humidity()[sensor_id]

    def get_sensors_humidity(self):
        humidities = []
        sensor_list = self._master_communicator.do_command(master_api.sensor_humidity_list())
        for i in xrange(32):
            humidities.append(sensor_list['hum{0}'.format(i)].get_humidity())
        return humidities

    def get_sensor_brightness(self, sensor_id):
        if sensor_id is None or sensor_id < 0 or sensor_id > 31:
            raise ValueError('Sensor ID {0} not in range 0 <= id <= 31'.format(sensor_id))
        return self.get_sensors_brightness()[sensor_id]

    def get_sensors_brightness(self):
        brightnesses = []
        sensor_list = self._master_communicator.do_command(master_api.sensor_brightness_list())
        for i in xrange(32):
            brightnesses.append(sensor_list['bri{0}'.format(i)].get_brightness())
        return brightnesses

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

    def load_sensor(self, sensor_id, fields=None):
        return self._eeprom_controller.read(eeprom_models.SensorConfiguration, sensor_id, fields).serialize()

    def load_sensors(self, fields=None):
        return [o.serialize() for o in self._eeprom_controller.read_all(eeprom_models.SensorConfiguration, fields)]

    def save_sensors(self, config):
        self._eeprom_controller.write_batch([eeprom_models.SensorConfiguration.deserialize(o) for o in config])
