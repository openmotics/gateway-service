from __future__ import absolute_import

import time
import unittest

import mock
from six.moves import map
from six.moves.queue import Queue

import gateway.hal.master_controller_core
from gateway.dto import InputDTO, OutputStateDTO, OutputDTO, FeedbackLedDTO, \
    GlobalFeedbackDTO
from gateway.hal.master_controller_core import MasterCoreController
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import SetTestMode
from master.core.core_api import CoreAPI
from master.core.core_communicator import BackgroundConsumer
from master.core.group_action import GroupActionController
from master.core.basic_action import BasicAction
from master.core.memory_models import InputConfiguration, \
    InputModuleConfiguration, OutputConfiguration, OutputModuleConfiguration, \
    SensorModuleConfiguration, ShutterConfiguration, GlobalConfiguration
from master.core.memory_types import MemoryActivator
from mocked_core_helper import MockedCore


class MasterCoreControllerTest(unittest.TestCase):
    """ Tests for MasterCoreController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.mocked_core = MockedCore()
        self.controller = self.mocked_core.controller
        self.pubsub = self.mocked_core.pubsub
        self.return_data = self.mocked_core.return_data

        # For testing purposes, remove read-only flag from certain properties
        for field_name in ['device_type', 'address', 'firmware_version']:
            for model_type in [OutputModuleConfiguration, InputModuleConfiguration, SensorModuleConfiguration]:
                if hasattr(model_type, '_{0}'.format(field_name)):
                    getattr(model_type, '_{0}'.format(field_name))._read_only = False
                else:
                    getattr(model_type, field_name)._read_only = False

    def test_master_output_event(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        self.pubsub.subscribe_master_events(PubSub.MasterTopics.OUTPUT, _on_event)

        events = []
        self.controller._handle_event({'type': 0, 'device_nr': 0, 'action': 0, 'data': bytearray([255, 0, 0, 0])})
        self.controller._handle_event({'type': 0, 'device_nr': 2, 'action': 1, 'data': bytearray([100, 2, 0xff, 0xfe])})
        self.pubsub._publish_all_events()
        self.assertEqual([MasterEvent(MasterEvent.Types.OUTPUT_STATUS, {'id': 0, 'status': False, 'dimmer': 255, 'ctimer': 0}),
                          MasterEvent(MasterEvent.Types.OUTPUT_STATUS, {'id': 2, 'status': True, 'dimmer': 100, 'ctimer': 65534})], events)

    def test_master_shutter_event(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        self.pubsub.subscribe_master_events(PubSub.MasterTopics.SHUTTER, _on_event)

        self.controller._output_states = {0: OutputStateDTO(id=0, status=False),
                                          10: OutputStateDTO(id=10, status=False),
                                          11: OutputStateDTO(id=11, status=False)}
        self.controller._output_shutter_map = {10: 1, 11: 1}
        self.controller._shutter_status = {1: (False, False)}
        self.pubsub._publish_all_events()

        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy):
            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 10, 'action': 0, 'data': [None, 0, 0, 0]})
            self.controller._handle_event({'type': 0, 'device_nr': 11, 'action': 0, 'data': [None, 0, 0, 0]})
            self.pubsub._publish_all_events()
            assert [] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 10, 'action': 1, 'data': [None, 0, 0, 0]})
            self.pubsub._publish_all_events()
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_up', 'location': {'room_id': 255}})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 11, 'action': 1, 'data': [None, 0, 0, 0]})
            self.pubsub._publish_all_events()
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'stopped', 'location': {'room_id': 255}})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 10, 'action': 0, 'data': [None, 0, 0, 0]})
            self.pubsub._publish_all_events()
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_down', 'location': {'room_id': 255}})] == events

            events = []
            self.controller._handle_event({'type': 0, 'device_nr': 11, 'action': 0, 'data': [None, 0, 0, 0]})
            self.pubsub._publish_all_events()
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'stopped', 'location': {'room_id': 255}})] == events

    def test_master_shutter_refresh(self):
        events = []

        def _on_event(master_event):
            events.append(master_event)

        self.pubsub.subscribe_master_events(PubSub.MasterTopics.SHUTTER, _on_event)

        output_status = [{'device_nr': 0, 'status': False, 'dimmer': 0},
                         {'device_nr': 1, 'status': False, 'dimmer': 0},
                         {'device_nr': 10, 'status': False, 'dimmer': 0},
                         {'device_nr': 11, 'status': False, 'dimmer': 0}]
        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy), \
             mock.patch.object(self.controller, 'load_output_status', return_value=output_status):
            events = []
            self.controller._refresh_shutter_states()
            self.pubsub._publish_all_events()
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'stopped', 'location': {'room_id': 255}})] == events

        output_status = [{'device_nr': 0, 'status': False, 'dimmer': 0},
                         {'device_nr': 1, 'status': True, 'dimmer': 0},
                         {'device_nr': 10, 'status': True, 'dimmer': 0},
                         {'device_nr': 11, 'status': False, 'dimmer': 0}]
        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy), \
             mock.patch.object(self.controller, 'load_output_status', return_value=output_status):
            events = []
            self.controller._refresh_shutter_states()
            self.pubsub._publish_all_events()
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_up', 'location': {'room_id': 255}})] == events

        output_status = [{'device_nr': 0, 'status': False, 'dimmer': 0},
                         {'device_nr': 1, 'status': True, 'dimmer': 0},
                         {'device_nr': 10, 'status': False, 'dimmer': 0},
                         {'device_nr': 11, 'status': True, 'dimmer': 0}]
        with mock.patch.object(gateway.hal.master_controller_core, 'ShutterConfiguration',
                               side_effect=get_core_shutter_dummy), \
             mock.patch.object(self.controller, 'load_output_status', return_value=output_status):
            events = []
            self.controller._refresh_shutter_states()
            self.pubsub._publish_all_events()
            assert [MasterEvent('SHUTTER_CHANGE', {'id': 1, 'status': 'going_down', 'location': {'room_id': 255}})] == events

    def test_input_module_type(self):
        with mock.patch.object(gateway.hal.master_controller_core, 'InputConfiguration',
                               return_value=get_core_input_dummy(1)):
            data = self.controller.get_input_module_type(1)
            self.assertEqual('I', data)

    def test_load_input(self):
        data = self.controller.load_input(1)
        self.assertEqual(data.id, 1)

    def test_load_inputs(self):
        input_modules = list(map(get_core_input_dummy, range(1, 17)))
        self.return_data['GC'] = {'input': 2}
        with mock.patch.object(gateway.hal.master_controller_core, 'InputConfiguration',
                               side_effect=input_modules):
            inputs = self.controller.load_inputs()
            self.assertEqual([x.id for x in inputs], list(range(1, 17)))

    def test_save_inputs(self):
        data = [(InputDTO(id=1, name='foo', module_type='I'), ['id', 'name', 'module_type']),
                (InputDTO(id=2, name='bar', module_type='I'), ['id', 'name', 'module_type'])]
        input_mock = mock.Mock(InputConfiguration)
        with mock.patch.object(InputConfiguration, 'deserialize', return_value=input_mock) as deserialize, \
                mock.patch.object(input_mock, 'save', return_value=None) as save:
            self.controller.save_inputs(data)
            self.assertIn(mock.call({'id': 1, 'name': 'foo'}), deserialize.call_args_list)
            self.assertIn(mock.call({'id': 2, 'name': 'bar'}), deserialize.call_args_list)
            save.assert_called_with(activate=False)

    def test_inputs_with_status(self):
        from gateway.hal.master_controller_core import MasterInputState
        with mock.patch.object(MasterInputState, 'get_inputs', return_value=[]) as get:
            self.controller.get_inputs_with_status()
            get.assert_called_with()

    def test_recent_inputs(self):
        from gateway.hal.master_controller_core import MasterInputState
        with mock.patch.object(MasterInputState, 'get_recent', return_value=[]) as get:
            self.controller.get_recent_inputs()
            get.assert_called_with()

    def test_event_consumer(self):
        with mock.patch.object(gateway.hal.master_controller_core, 'BackgroundConsumer',
                               return_value=None) as new_consumer:
            controller = MasterCoreController()
            expected_call = mock.call(CoreAPI.event_information(), 0, mock.ANY)
            self.assertIn(expected_call, new_consumer.call_args_list)

    def test_subscribe_input_events(self):
        consumer_list = []

        def new_consumer(*args):
            consumer = BackgroundConsumer(*args)
            consumer_list.append(consumer)
            return consumer

        subscriber = mock.Mock()
        with mock.patch.object(gateway.hal.master_controller_core, 'BackgroundConsumer',
                               side_effect=new_consumer) as new_consumer:
            controller = MasterCoreController()
        self.pubsub.subscribe_master_events(PubSub.MasterTopics.INPUT, subscriber.callback)

        new_consumer.assert_called()
        event_data = {'type': 1, 'action': 1, 'device_nr': 2,
                      'data': {}}
        with mock.patch.object(Queue, 'get', return_value=event_data):
            consumer_list[0].deliver()
        self.pubsub._publish_all_events()
        expected_event = MasterEvent.deserialize({'type': 'INPUT_CHANGE',
                                                  'data': {'id': 2,
                                                           'status': True,
                                                           'location': {'room_id': 255}}})
        subscriber.callback.assert_called_with(expected_event)

    def test_get_modules(self):
        from master.core.memory_models import (
            InputModuleConfiguration, OutputModuleConfiguration, SensorModuleConfiguration,
            GlobalConfiguration
        )
        global_configuration = GlobalConfiguration()
        global_configuration.number_of_output_modules = 5
        global_configuration.number_of_input_modules = 4
        global_configuration.number_of_sensor_modules = 2
        global_configuration.number_of_can_control_modules = 2
        global_configuration.save()
        for module_id, module_class, device_type, address in [(0, InputModuleConfiguration, 'I', '{0}.123.123.123'.format(ord('I'))),
                                                              (1, InputModuleConfiguration, 'i', '{0}.123.123.123'.format(ord('i'))),
                                                              (2, InputModuleConfiguration, 'i', '{0}.000.000.000'.format(ord('i'))),
                                                              (3, InputModuleConfiguration, 'b', '{0}.123.132.123'.format(ord('b'))),
                                                              (0, OutputModuleConfiguration, 'o', '{0}.000.000.000'.format(ord('o'))),
                                                              (1, OutputModuleConfiguration, 'o', '{0}.000.000.001'.format(ord('o'))),
                                                              (2, OutputModuleConfiguration, 'o', '{0}.000.000.002'.format(ord('o'))),
                                                              (3, OutputModuleConfiguration, 'o', '{0}.123.123.123'.format(ord('o'))),
                                                              (4, OutputModuleConfiguration, 'O', '{0}.123.123.123'.format(ord('O'))),
                                                              (0, SensorModuleConfiguration, 's', '{0}.123.123.123'.format(ord('s'))),
                                                              (1, SensorModuleConfiguration, 'T', '{0}.123.123.123'.format(ord('T')))]:
            instance = module_class(module_id)
            instance.device_type = device_type
            instance.address = address
            instance.save()

        self.assertEqual({'can_inputs': ['I', 'T', 'C', 'E'],
                          'inputs': ['I', 'i', 'J', 'T'],
                          'outputs': ['P', 'P', 'P', 'o', 'O'],
                          'shutters': []}, self.controller.get_modules())

    def test_master_eeprom_event(self):
        master_event = MasterEvent(MasterEvent.Types.EEPROM_CHANGE, {})
        self.controller._output_last_updated = 1603178386.0
        self.pubsub.publish_master_event(PubSub.MasterTopics.EEPROM, master_event)
        self.pubsub._publish_all_events()
        assert self.controller._output_last_updated == 0

    def test_individual_feedback_leds(self):
        output = OutputConfiguration.deserialize({'id': 0})
        # Setup basic LED feedback
        output_dto = OutputDTO(id=0,
                               can_led_1=FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                               can_led_3=FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.MB_B8_INVERTED))

        # Save led feedback config
        self.controller._save_output_led_feedback_configuration(output, output_dto, ['can_led_1', 'can_led_3'])
        MemoryActivator.activate()

        # Validate correct data in created GA
        self.assertEqual(0, output.output_groupaction_follow)
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual([BasicAction(action_type=19, action=80, device_nr=0),
                          BasicAction(action_type=20, action=50, device_nr=5, extra_parameter=65280),
                          BasicAction(action_type=20, action=51, device_nr=7, extra_parameter=32514)], group_action.actions)
        self.assertEqual('Output 0', group_action.name)

        # Alter GA
        extra_bas = [BasicAction(action_type=123, action=123),  # Some random BA
                     BasicAction(action_type=19, action=80, device_nr=1),  # Another batch of feedback statements for another Output
                     BasicAction(action_type=20, action=50, device_nr=15),
                     BasicAction(action_type=20, action=51, device_nr=17)]
        group_action.actions += extra_bas
        group_action.name = 'Foobar'
        GroupActionController.save_group_action(group_action, ['name', 'actions'])

        # Validate loading data
        output_dto = OutputDTO(id=0)
        self.controller._load_output_led_feedback_configuration(output, output_dto)
        self.assertEqual(FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL), output_dto.can_led_1)
        self.assertEqual(FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.MB_B8_INVERTED), output_dto.can_led_2)  # Moved to 2

        # Change led feedback config
        output_dto.can_led_2.function = FeedbackLedDTO.Functions.ON_B8_INVERTED
        self.controller._save_output_led_feedback_configuration(output, output_dto, ['can_led_1', 'can_led_2'])
        MemoryActivator.activate()

        # Validate stored led feedback data
        output_dto = OutputDTO(id=0)
        self.controller._load_output_led_feedback_configuration(output, output_dto)
        self.assertEqual(FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL), output_dto.can_led_1)
        self.assertEqual(FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.ON_B8_INVERTED), output_dto.can_led_2)

        # Validate GA changes
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(extra_bas + [BasicAction(action_type=19, action=80, device_nr=0),
                                      BasicAction(action_type=20, action=50, device_nr=5, extra_parameter=65280),
                                      BasicAction(action_type=20, action=51, device_nr=7, extra_parameter=32512)],
                         group_action.actions)
        self.assertEqual('Foobar', group_action.name)

    def test_global_feedback_leds(self):
        global_configuration = GlobalConfiguration()
        all_default_global_feedbacks = [GlobalFeedbackDTO(id=i) for i in range(32)]

        # Verify base
        self.assertEqual(65535, global_configuration.groupaction_any_output_changed)
        self.assertEqual([GlobalFeedbackDTO(id=i) for i in range(32)], self.controller.load_global_feedbacks())

        # Store feedback "0" (nr of lights == 0)
        global_feedback_0 = GlobalFeedbackDTO(id=0,
                                              can_led_1=FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                              can_led_3=FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.ON_B8_INVERTED),
                                              can_led_4=FeedbackLedDTO(id=9, function=FeedbackLedDTO.Functions.FB_B8_NORMAL))
        self.controller.save_global_feedbacks([(global_feedback_0, ['can_led_1', 'can_led_3', 'can_led_4'])])

        #                                                                                                 +- 256 = MSB is 1 = lights
        # Validate                                                                                        |   +- 0 = Solid on, 1 = Fast blinking
        expected_basic_actions_0 = [BasicAction(action_type=20, action=73, device_nr=5, extra_parameter=256 + 0),
                                    BasicAction(action_type=20, action=73, device_nr=7, extra_parameter=256 + 0),
                                    BasicAction(action_type=20, action=73, device_nr=9, extra_parameter=256 + 1)]
        expected_global_feedback_0 = GlobalFeedbackDTO(id=0,
                                                       can_led_1=FeedbackLedDTO(id=5, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                                       can_led_2=FeedbackLedDTO(id=7, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                                       can_led_3=FeedbackLedDTO(id=9, function=FeedbackLedDTO.Functions.FB_B16_NORMAL))
        expected_global_feedbacks = all_default_global_feedbacks[:]
        expected_global_feedbacks[0] = expected_global_feedback_0
        global_configuration = GlobalConfiguration()
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(0, global_configuration.groupaction_any_output_changed)
        self.assertEqual('Global feedback', group_action.name)
        self.assertEqual(expected_basic_actions_0, group_action.actions)
        self.assertEqual(expected_global_feedbacks, self.controller.load_global_feedbacks())
        self.assertEqual(expected_global_feedback_0, self.controller.load_global_feedback(0))

        # Prepare feedback "3" (nr of lights > 2)
        global_feedback_3 = GlobalFeedbackDTO(id=3,
                                              can_led_1=FeedbackLedDTO(id=11, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                              can_led_3=FeedbackLedDTO(id=13, function=FeedbackLedDTO.Functions.FB_B8_INVERTED),
                                              can_led_4=FeedbackLedDTO(id=15, function=FeedbackLedDTO.Functions.ON_B8_INVERTED))
        expected_global_feedback_3 = GlobalFeedbackDTO(id=3,
                                                       can_led_1=FeedbackLedDTO(id=11, function=FeedbackLedDTO.Functions.ON_B16_NORMAL),
                                                       can_led_2=FeedbackLedDTO(id=13, function=FeedbackLedDTO.Functions.FB_B16_NORMAL))
        expected_basic_actions_3 = [BasicAction(action_type=20, action=71, device_nr=11, extra_parameter=512 + 0),
                                    BasicAction(action_type=20, action=71, device_nr=13, extra_parameter=512 + 1)]
        #                                                                                                |   +- 0 = Solid on, 1 = Fast blinking
        #                                                                                                +- 512 = MSB is 2 = nr of lights

        # Store in various scenarios, all should yield the same response
        save_scenarios = [[(global_feedback_3, ['can_led_1', 'can_led_3'])],
                          [(global_feedback_0, ['can_led_1', 'can_led_3', 'can_led_4']), (global_feedback_3, ['can_led_1', 'can_led_3'])]]
        for save_scenario in save_scenarios:
            self.controller.save_global_feedbacks(save_scenario)

            expected_global_feedbacks = all_default_global_feedbacks[:]
            expected_global_feedbacks[0] = expected_global_feedback_0
            expected_global_feedbacks[3] = expected_global_feedback_3
            global_configuration = GlobalConfiguration()
            group_action = GroupActionController.load_group_action(0)
            self.assertEqual(0, global_configuration.groupaction_any_output_changed)
            self.assertEqual(expected_basic_actions_0 + expected_basic_actions_3, group_action.actions)
            self.assertEqual(expected_global_feedbacks, self.controller.load_global_feedbacks())
            self.assertEqual(expected_global_feedback_0, self.controller.load_global_feedback(0))
            self.assertEqual(expected_global_feedback_3, self.controller.load_global_feedback(3))

        # Add extra BA that should not be removed by altering global feedback
        extra_basic_actions = [BasicAction(action_type=123, action=123)]
        group_action.actions += extra_basic_actions
        group_action.name = 'Foobar'
        GroupActionController.save_group_action(group_action, ['name', 'actions'])

        # Save without scenario (will re-save data, but should not alter)
        self.controller.save_global_feedbacks([])
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual('Foobar', group_action.name)
        self.assertEqual(expected_basic_actions_0 + expected_basic_actions_3 + extra_basic_actions, group_action.actions)

        # Save full scenario (will remove feedback BAs and save them again at the end of the GA)
        self.controller.save_global_feedbacks(save_scenarios[1])
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual('Foobar', group_action.name)
        self.assertEqual(extra_basic_actions + expected_basic_actions_0 + expected_basic_actions_3, group_action.actions)

        # Prepare feedbacks "16" (nr of outputs == 0) and "20" (nr of outputs > 3)
        global_feedback_16 = GlobalFeedbackDTO(id=16, can_led_1=FeedbackLedDTO(id=15, function=FeedbackLedDTO.Functions.ON_B16_NORMAL))
        global_feedback_20 = GlobalFeedbackDTO(id=20, can_led_1=FeedbackLedDTO(id=17, function=FeedbackLedDTO.Functions.ON_B16_NORMAL))
        expected_global_feedback_16 = GlobalFeedbackDTO(id=16, can_led_1=FeedbackLedDTO(id=15, function=FeedbackLedDTO.Functions.ON_B16_NORMAL))
        expected_global_feedback_20 = GlobalFeedbackDTO(id=20, can_led_1=FeedbackLedDTO(id=17, function=FeedbackLedDTO.Functions.ON_B16_NORMAL))
        expected_basic_actions_16 = [BasicAction(action_type=20, action=73, device_nr=15, extra_parameter=0 + 0)]  # 0 = MSB is 0 = outputs
        expected_basic_actions_20 = [BasicAction(action_type=20, action=70, device_nr=17, extra_parameter=768 + 0)]  # 768 = MSB is 3 = nr of outputs

        # Store
        self.controller.save_global_feedbacks([(global_feedback_0, ['can_led_1', 'can_led_3', 'can_led_4']),
                                               (global_feedback_3, ['can_led_1', 'can_led_3']),
                                               (global_feedback_16, ['can_led_1']),
                                               (global_feedback_20, ['can_led_1'])])

        # Validate
        expected_global_feedbacks = all_default_global_feedbacks[:]
        expected_global_feedbacks[0] = expected_global_feedback_0
        expected_global_feedbacks[3] = expected_global_feedback_3
        expected_global_feedbacks[16] = expected_global_feedback_16
        expected_global_feedbacks[20] = expected_global_feedback_20
        global_configuration = GlobalConfiguration()
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(0, global_configuration.groupaction_any_output_changed)
        self.assertEqual(extra_basic_actions +
                         expected_basic_actions_0 +
                         expected_basic_actions_3 +
                         expected_basic_actions_16 +
                         expected_basic_actions_20, group_action.actions)
        self.assertEqual(expected_global_feedbacks, self.controller.load_global_feedbacks())
        self.assertEqual(expected_global_feedback_0, self.controller.load_global_feedback(0))
        self.assertEqual(expected_global_feedback_3, self.controller.load_global_feedback(3))
        self.assertEqual(expected_global_feedback_16, self.controller.load_global_feedback(16))
        self.assertEqual(expected_global_feedback_20, self.controller.load_global_feedback(20))

        # Remove 3
        empty_global_feedback_3 = GlobalFeedbackDTO(id=3)
        self.controller.save_global_feedbacks([(empty_global_feedback_3, ['can_led_1', 'can_led_2']),
                                               (global_feedback_20, ['can_led_1'])])

        # Validate
        expected_global_feedbacks = all_default_global_feedbacks[:]
        expected_global_feedbacks[0] = expected_global_feedback_0
        expected_global_feedbacks[16] = expected_global_feedback_16
        expected_global_feedbacks[20] = expected_global_feedback_20
        global_configuration = GlobalConfiguration()
        group_action = GroupActionController.load_group_action(0)
        self.assertEqual(0, global_configuration.groupaction_any_output_changed)
        self.assertEqual(extra_basic_actions +
                         expected_basic_actions_0 +
                         expected_basic_actions_16 +
                         expected_basic_actions_20, group_action.actions)
        self.assertEqual(expected_global_feedbacks, self.controller.load_global_feedbacks())
        self.assertEqual(expected_global_feedback_0, self.controller.load_global_feedback(0))
        self.assertEqual(expected_global_feedback_16, self.controller.load_global_feedback(16))
        self.assertEqual(expected_global_feedback_20, self.controller.load_global_feedback(20))


class MasterInputState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_handle_event(self):
        from gateway.hal.master_controller_core import MasterCoreEvent, MasterInputState
        state = MasterInputState()
        core_event = MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': 2, 'data': {}})
        with mock.patch.object(time, 'time', return_value=30):
            event = state.handle_event(core_event)
            expected_data = {'type': 'INPUT_CHANGE',
                             'data': {'id': 2,
                                      'status': True,
                                      'location': {'room_id': 255}}}
            self.assertEqual(expected_data, event.serialize())
            self.assertIn({'id': 2, 'status': 1}, state.get_inputs())

    def test_refresh(self):
        from gateway.hal.master_controller_core import MasterCoreEvent, MasterInputState
        state = MasterInputState(interval=10)
        core_events = [
            MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': 1, 'data': {}}),
            MasterCoreEvent({'type': 1, 'action': 0, 'device_nr': 2, 'data': {}}),
        ]
        with mock.patch.object(time, 'time', return_value=30):
            for core_event in core_events:
                state.handle_event(core_event)
            self.assertTrue(state.should_refresh())
            events = state.refresh([0b00000110])
            self.assertEqual(1, len(events))
            expected_event = MasterEvent(event_type=MasterEvent.Types.INPUT_CHANGE,
                                         data={'id': 2,
                                               'status': True,
                                               'location': {'room_id': 255}})
            self.assertIn(expected_event, events)
            self.assertFalse(state.should_refresh())

            events = state.refresh([0b00000110])
            self.assertEqual([], events)

        with mock.patch.object(time, 'time', return_value=60):
            self.assertTrue(state.should_refresh())

    def test_recent(self):
        from gateway.hal.master_controller_core import MasterCoreEvent, MasterInputState
        state = MasterInputState()
        with mock.patch.object(time, 'time', return_value=0):
            core_event = MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': 1, 'data': {}})
            state.handle_event(core_event)
            self.assertEqual([1], state.get_recent())

        with mock.patch.object(time, 'time', return_value=30):
            for i in range(2, 10):
                core_event = MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': i, 'data': {}})
                state.handle_event(core_event)
            devices = state.get_recent()
            self.assertEqual(5, len(devices))
            self.assertNotIn(1, devices)

        with mock.patch.object(time, 'time', return_value=60):
            self.assertEqual(0, len(state.get_recent()))

        with mock.patch.object(time, 'time', return_value=60):
            state.handle_event(MasterCoreEvent({'type': 1, 'action': 0, 'device_nr': 1, 'data': {}}))
            state.handle_event(MasterCoreEvent({'type': 1, 'action': 1, 'device_nr': 2, 'data': {}}))
            devices = state.get_recent()
            self.assertIn(1, devices)
            self.assertNotIn(2, devices)


def get_core_output_dummy(i):
    return OutputConfiguration.deserialize({
        'id': i,
        'name': 'foo',
        'module': {'id': 20 + i,
                   'device_type': 'O',
                   'address': '0.0.0.0',
                   'firmware_version': '0.0.1'}
    })


def get_core_input_dummy(i):
    return InputConfiguration.deserialize({
        'id': i,
        'name': 'foo',
        'module': {'id': 20 + i,
                   'device_type': 'I',
                   'address': '0.0.0.0',
                   'firmware_version': '0.0.1'}
    })


def get_core_shutter_dummy(i):
    return ShutterConfiguration.deserialize({
        'id': i,
        'name': 'foo',
        'groups': {},
        'outputs': {'output_0': 10 * i if i > 0 else 255,
                    'output_1': 10 * i + 1 if i > 0 else 255},
    })
