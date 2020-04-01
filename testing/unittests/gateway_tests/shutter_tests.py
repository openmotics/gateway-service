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
Tests for the shutters module.
"""
import copy
import fakesleep
import time
import unittest
import xmlrunner
from mock import Mock
from ioc import SetTestMode, SetUpTestInjections
from gateway.enums import ShutterEnums
from gateway.shutters import ShutterController
from gateway.dto import ShutterDTO
from gateway.hal.master_controller_classic import MasterClassicController


class ShutterControllerTest(unittest.TestCase):
    """ Tests for ShutterController. """

    SHUTTER_CONFIG = [ShutterDTO(id=0,
                                 steps=None,
                                 up_down_config=0,
                                 timer_up=100,
                                 timer_down=100),
                      ShutterDTO(id=1,
                                 steps=None,
                                 up_down_config=1,
                                 timer_up=100,
                                 timer_down=100),
                      ShutterDTO(id=2,
                                 steps=100,
                                 up_down_config=0),
                      ShutterDTO(id=3,
                                 steps=0,
                                 up_down_config=0)]

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        fakesleep.monkey_patch()

    @classmethod
    def tearDownClass(cls):
        fakesleep.monkey_restore()

    def test_update_config(self):
        master_controller = Mock()
        master_controller.load_shutters = lambda: []
        SetUpTestInjections(master_controller=master_controller)
        controller = ShutterController()

        # Basic configuration
        controller.update_config(ShutterControllerTest.SHUTTER_CONFIG)
        self.assertEqual(len(controller._shutters), 4)
        for shutter_id in xrange(3):
            self.assertIn(shutter_id, controller._shutters)
            self.assertEqual(controller._shutters[shutter_id], ShutterControllerTest.SHUTTER_CONFIG[shutter_id])
            self.assertIn(shutter_id, controller._actual_positions)
            self.assertIn(shutter_id, controller._desired_positions)
            self.assertIn(shutter_id, controller._directions)
            self.assertIn(shutter_id, controller._states)

        # Config removal
        config = copy.deepcopy(ShutterControllerTest.SHUTTER_CONFIG)
        config.pop(0)
        controller.update_config(config)
        self.assertNotIn(0, controller._shutters)
        self.assertNotIn(0, controller._actual_positions)
        self.assertNotIn(0, controller._desired_positions)
        self.assertNotIn(0, controller._directions)
        self.assertNotIn(0, controller._states)

        self.assertEqual(controller._get_shutter(1), ShutterControllerTest.SHUTTER_CONFIG[1])
        with self.assertRaises(RuntimeError) as ex:
            controller._get_shutter(0)
        self.assertEqual(str(ex.exception), 'Shutter 0 is not available')

        # Config update
        controller._actual_positions[1] = 'foo'
        controller._desired_positions[1] = 'foo'
        controller._directions[1] = 'foo'
        controller._states[1] = 'foo'
        config[0].up_down_config = 0
        controller.update_config(config)
        self.assertIsNone(controller._actual_positions.get(1, 'incorrect'))
        self.assertIsNone(controller._desired_positions.get(1, 'incorrect'))
        self.assertEquals(controller._directions.get(1), ShutterEnums.Direction.STOP)
        self.assertEquals(controller._states.get(1), [0, ShutterEnums.State.STOPPED])

    def test_basic_actions_non_positional(self):
        calls = {}

        def shutter_direction(direction, _shutter_id):
            calls.setdefault(_shutter_id, []).append(direction)

        master_controller = Mock()
        master_controller.shutter_up = lambda id: shutter_direction('up', id)
        master_controller.shutter_down = lambda id: shutter_direction('down', id)
        master_controller.shutter_stop = lambda id: shutter_direction('stop', id)
        SetUpTestInjections(master_controller=master_controller)

        controller = ShutterController()
        controller.update_config(ShutterControllerTest.SHUTTER_CONFIG)

        #                        +- shutter id
        # Valid calls            |  +- desired position
        calls = {}             # v  v
        for shutter_id, data in {0: None,
                                 1: None,
                                 2: 99}.iteritems():
            controller.shutter_down(shutter_id)
            self.assertEqual(controller._desired_positions[shutter_id], data)
            self.assertEqual(controller._directions[shutter_id], ShutterEnums.Direction.DOWN)
            self.assertEqual(calls.get(shutter_id)[-1], 'down')

        #                        +- shutter id
        #                        |  +- desired position
        calls = {}             # v  v
        for shutter_id, data in {0: None,
                                 1: None,
                                 2: 0}.iteritems():
            controller.shutter_up(shutter_id)
            self.assertEqual(controller._desired_positions[shutter_id], data)
            self.assertEqual(controller._directions[shutter_id], ShutterEnums.Direction.UP)
            self.assertEqual(calls.get(shutter_id)[-1], 'up')

        calls = {}
        for shutter_id in xrange(3):
            controller.shutter_stop(shutter_id)
            self.assertIsNone(controller._desired_positions[shutter_id])
            self.assertEqual(controller._directions[shutter_id], ShutterEnums.Direction.STOP)
            self.assertEqual(calls.get(shutter_id)[-1], 'stop')

    def test_basic_actions_positional(self):
        calls = {}

        def shutter_direction(direction, _shutter_id):
            calls.setdefault(_shutter_id, []).append(direction)

        master_controller = Mock()
        master_controller.shutter_up = lambda id: shutter_direction('up', id)
        master_controller.shutter_down = lambda id: shutter_direction('down', id)
        master_controller.shutter_stop = lambda id: shutter_direction('stop', id)
        SetUpTestInjections(master_controller=master_controller)

        controller = ShutterController()
        controller.update_config(ShutterControllerTest.SHUTTER_CONFIG)

        # Positionned calls on non-positional shutters should fail
        calls = {}
        for shutter_id in [0, 1]:
            message = 'Shutter {0} does not support positioning'.format(shutter_id)
            with self.assertRaises(RuntimeError) as ex:
                controller.shutter_up(shutter_id, 5)
            self.assertEqual(str(ex.exception), message)
            with self.assertRaises(RuntimeError) as ex:
                controller.shutter_down(shutter_id, 5)
            self.assertEqual(str(ex.exception), message)
        self.assertEqual(len(calls), 0)

        # Out of range positions should fail
        calls = {}
        for shutter_id in [2]:
            message = 'Shutter {0} has a position limit of 0 <= position <= {1}'.format(shutter_id, ShutterControllerTest.SHUTTER_CONFIG[shutter_id].steps - 1)
            with self.assertRaises(RuntimeError) as ex:
                controller.shutter_up(shutter_id, 105)
            self.assertEqual(str(ex.exception), message)
            with self.assertRaises(RuntimeError) as ex:
                controller.shutter_down(shutter_id, 105)
            self.assertEqual(str(ex.exception), message)
        self.assertEqual(len(calls), 0)

        # Valid calls
        calls = {}
        for shutter_id in [2]:
            controller.shutter_up(shutter_id, 50)
            controller.shutter_down(shutter_id, 50)
            self.assertEqual(calls[shutter_id], ['up', 'down'])
        self.assertEqual(len(calls), 1)

    def test_goto_position(self):
        calls = {}

        def shutter_direction(direction, _shutter_id):
            calls.setdefault(_shutter_id, []).append(direction)

        master_controller = Mock()
        master_controller.shutter_up = lambda id: shutter_direction('up', id)
        master_controller.shutter_down = lambda id: shutter_direction('down', id)
        master_controller.shutter_stop = lambda id: shutter_direction('stop', id)
        SetUpTestInjections(master_controller=master_controller)

        controller = ShutterController()
        controller.update_config(ShutterControllerTest.SHUTTER_CONFIG)

        # Positionned calls on non-positional shutters should fail
        calls = {}
        for shutter_id in [0, 1]:
            message = 'Shutter {0} does not support positioning'.format(shutter_id)
            with self.assertRaises(RuntimeError) as ex:
                controller.shutter_goto(shutter_id, 5)
            self.assertEqual(str(ex.exception), message)
        self.assertEqual(len(calls), 0)

        #                             +- starting actual position
        #                             |   +- position to go to
        #                             |   |   +- expected direction after the call
        #                             |   |   |                            +- expected BA to be executed
        calls = {}                  # v   v   v                            v
        for shutter_id, data in {2: [[10, 50, ShutterEnums.Direction.UP,   'up'],  # down = 0, up = 100
                                     [10, 5,  ShutterEnums.Direction.DOWN, 'down']]}.iteritems():
            # Out of range calls need to fail
            message = 'Shutter {0} has a position limit of 0 <= position <= {1}'.format(shutter_id, ShutterControllerTest.SHUTTER_CONFIG[shutter_id].steps - 1)
            with self.assertRaises(RuntimeError) as ex:
                controller.shutter_goto(shutter_id, 105)
            self.assertEqual(str(ex.exception), message)
            # A shutter with unknown position can't be instructed
            controller._actual_positions[shutter_id] = None
            with self.assertRaises(RuntimeError) as ex:
                controller.shutter_goto(shutter_id, 50)
            self.assertEqual(str(ex.exception), 'Shutter {0} has unknown actual position'.format(shutter_id))
            # Validate correct calls
            for entry in data:
                controller._actual_positions[shutter_id] = entry[0]
                controller.shutter_goto(shutter_id, entry[0])
                self.assertEqual(calls[shutter_id].pop(), 'stop')
                controller.shutter_goto(shutter_id, entry[1])
                self.assertEqual(controller._directions[shutter_id], entry[2])
                self.assertEqual(calls[shutter_id].pop(), entry[3])

    def test_position_reached(self):
        for expected_result, data in [[False, {'direction': ShutterEnums.Direction.UP,
                                               'desired_position': 50,
                                               'actual_position': 60}],
                                      [True, {'direction': ShutterEnums.Direction.UP,
                                              'desired_position': 50,
                                              'actual_position': 50}],
                                      [True, {'direction': ShutterEnums.Direction.UP,
                                              'desired_position': 50,
                                              'actual_position': 40}],
                                      [False, {'direction': ShutterEnums.Direction.DOWN,
                                               'desired_position': 50,
                                               'actual_position': 40}],
                                      [True, {'direction': ShutterEnums.Direction.DOWN,
                                              'desired_position': 50,
                                              'actual_position': 50}],
                                      [True, {'direction': ShutterEnums.Direction.DOWN,
                                              'desired_position': 50,
                                              'actual_position': 60}]]:
            self.assertEqual(expected_result, ShutterController._is_position_reached(**data))

    def test_position_reporting(self):
        calls = {}

        def shutter_direction(direction, _shutter_id):
            calls.setdefault(_shutter_id, []).append(direction)

        master_controller = Mock()
        master_controller.shutter_up = lambda id: shutter_direction('up', id)
        master_controller.shutter_down = lambda id: shutter_direction('down', id)
        master_controller.shutter_stop = lambda id: shutter_direction('stop', id)
        SetUpTestInjections(master_controller=master_controller)

        controller = ShutterController()
        controller.update_config(ShutterControllerTest.SHUTTER_CONFIG)

        # Positionned calls on non-positional shutters should fail
        calls = {}
        for shutter_id in [0, 1]:
            message = 'Shutter {0} does not support positioning'.format(shutter_id)
            with self.assertRaises(RuntimeError) as ex:
                controller.report_shutter_position(shutter_id, 5)
            self.assertEqual(str(ex.exception), message)
        self.assertEqual(len(calls), 0)

        #                             +- desired position
        #                             |   +- reported position
        #                             |   |   +- internal direction of the shutter
        # Validate correct calls      |   |   |                            +- reported position
        calls = {}                  # v   v   v                            v
        for shutter_id, data in {2: [[50, 60, ShutterEnums.Direction.UP,   None],  # down = 0, up = 100
                                     [50, 60, ShutterEnums.Direction.UP,   ShutterEnums.Direction.UP],
                                     [50, 60, ShutterEnums.Direction.UP,   ShutterEnums.Direction.DOWN],
                                     [50, 40, ShutterEnums.Direction.DOWN, None],
                                     [50, 40, ShutterEnums.Direction.DOWN, ShutterEnums.Direction.DOWN],
                                     [50, 40, ShutterEnums.Direction.DOWN, ShutterEnums.Direction.UP],
                                     [50, 50, ShutterEnums.Direction.UP,   None],
                                     [50, 50, ShutterEnums.Direction.UP,   ShutterEnums.Direction.STOP],
                                     [50, 50, ShutterEnums.Direction.UP,   ShutterEnums.Direction.UP],
                                     [50, 50, ShutterEnums.Direction.UP,   ShutterEnums.Direction.DOWN]]}.iteritems():
            for entry in data:
                controller._desired_positions[shutter_id] = entry[0]
                controller._directions[shutter_id] = entry[2]
                controller.report_shutter_position(shutter_id, entry[1], entry[3])
                if entry[0] == entry[1] or (entry[3] is not None and entry[2] != entry[3]):  # If desired and reported are equal, or if the direction changed
                    self.assertEqual(calls[shutter_id].pop(), 'stop')
                    self.assertEqual(controller._directions[shutter_id], ShutterEnums.Direction.STOP)
                elif entry[3] is None:
                    self.assertEqual(controller._directions[shutter_id], entry[2])
                else:
                    self.assertEqual(controller._directions[shutter_id], entry[3])

    def test_master_events_and_state(self):
        fakesleep.reset(0)
        calls = {}

        SetUpTestInjections(master_communicator=Mock(),
                            configuration_controller=Mock(),
                            eeprom_controller=Mock())

        master_controller = MasterClassicController()
        master_controller._shutter_config = {shutter.id: shutter for shutter in ShutterControllerTest.SHUTTER_CONFIG}
        SetUpTestInjections(master_controller=master_controller)

        controller = ShutterController()
        controller.update_config(ShutterControllerTest.SHUTTER_CONFIG)

        def shutter_callback(_shutter_id, _shutter_data, _state):
            calls.setdefault(_shutter_id, []).append([_shutter_data, _state])
        controller.subscribe_shutter_change(shutter_callback)

        def validate(_shutter_id, _entry):
            self.assertEquals(controller._actual_positions.get(_shutter_id), _entry[0])
            self.assertEquals(controller._desired_positions.get(_shutter_id), _entry[1])
            self.assertEquals(controller._directions.get(_shutter_id), _entry[2])
            self.assertEquals(controller._states.get(_shutter_id), _entry[3])
            if len(_entry) == 4 or _entry[4]:
                self.assertEqual(calls[_shutter_id].pop()[1], _entry[3][1].upper())

        master_controller._update_from_master_state({'module_nr': 0, 'status': 0b00000000})
        for shutter_id in xrange(3):
            #                     +- actual position
            #                     |     +- desired position
            #                     |     |     +- direction                      +- state                              +- optional skip call check
            #                     v     v     v                                 v                                     v
            validate(shutter_id, [None, None, ShutterEnums.Direction.STOP, [0, ShutterEnums.State.STOPPED], False])

        for shutter_id in xrange(3):
            controller.shutter_down(shutter_id, None)

        time.sleep(20)

        master_controller._update_from_master_state({'module_nr': 0, 'status': 0b00010101})
        #                             +- actual position
        #                             |     +- desired position
        #                             |     |     +- direction                      +- state
        #                             v     v     v                                 v
        for shutter_id, entry in {0: [None, None, ShutterEnums.Direction.DOWN, [20, ShutterEnums.State.GOING_DOWN]],
                                  1: [None, None, ShutterEnums.Direction.UP,   [20, ShutterEnums.State.GOING_UP]],
                                  2: [None, 99,   ShutterEnums.Direction.DOWN, [20, ShutterEnums.State.GOING_DOWN]]}.iteritems():
            validate(shutter_id, entry)

        time.sleep(50)  # Standard shutters will be down now

        controller._actual_positions[2] = 20  # Simulate position reporting
        master_controller._update_from_master_state({'module_nr': 0, 'status': 0b00010100})  # First shutter motor stop
        #                             +- actual position
        #                             |     +- desired position
        #                             |     |     +- direction                      +- state                                  +- optional skip call check
        #                             v     v     v                                 v                                         v
        for shutter_id, entry in {0: [None, None, ShutterEnums.Direction.STOP, [70, ShutterEnums.State.STOPPED]],
                                  1: [None, None, ShutterEnums.Direction.UP,   [20, ShutterEnums.State.GOING_UP],   False],
                                  2: [20,   99,   ShutterEnums.Direction.DOWN, [20, ShutterEnums.State.GOING_DOWN], False]}.iteritems():
            validate(shutter_id, entry)

        time.sleep(50)  # Standard shutters will be down now

        controller._actual_positions[2] = 50  # Simulate position reporting
        master_controller._update_from_master_state({'module_nr': 0, 'status': 0b00010000})  # Second shutter motor stop
        #                             +- actual position
        #                             |     +- desired position
        #                             |     |     +- direction                      +- state                                  +- optional skip call check
        #                             v     v     v                                 v                                         v
        for shutter_id, entry in {0: [None, None, ShutterEnums.Direction.STOP, [70, ShutterEnums.State.STOPPED],    False],
                                  1: [None, None, ShutterEnums.Direction.STOP, [120, ShutterEnums.State.UP]],
                                  2: [50,   99,   ShutterEnums.Direction.DOWN, [20, ShutterEnums.State.GOING_DOWN], False]}.iteritems():
            validate(shutter_id, entry)

        time.sleep(10)

        controller._actual_positions[2] = 50  # Simulate position reporting
        master_controller._update_from_master_state({'module_nr': 0, 'status': 0b00000000})  # Third motor stopped
        #                             +- actual position
        #                             |     +- desired position
        #                             |     |     +- direction                      +- state                               +- optional skip call check
        #                             v     v     v                                 v                                      v
        for shutter_id, entry in {0: [None, None, ShutterEnums.Direction.STOP, [70, ShutterEnums.State.STOPPED], False],
                                  1: [None, None, ShutterEnums.Direction.STOP, [120, ShutterEnums.State.UP],     False],
                                  2: [50,   99,   ShutterEnums.Direction.STOP, [130, ShutterEnums.State.STOPPED]]}.iteritems():
            validate(shutter_id, entry)

        controller._actual_positions[2] = 60  # Simulate position reporting
        master_controller._update_from_master_state({'module_nr': 0, 'status': 0b00010000})  # Third motor started again
        #                             +- actual position
        #                             |     +- desired position
        #                             |     |     +- direction                      +- state                               +- optional skip call check
        #                             v     v     v                                 v                                      v
        for shutter_id, entry in {0: [None, None, ShutterEnums.Direction.STOP, [70, ShutterEnums.State.STOPPED], False],
                                  1: [None, None, ShutterEnums.Direction.STOP, [120, ShutterEnums.State.UP],     False],
                                  2: [60,   99,   ShutterEnums.Direction.DOWN, [130, ShutterEnums.State.GOING_DOWN]]}.iteritems():
            validate(shutter_id, entry)

        controller._actual_positions[2] = 99  # Simulate position reporting
        master_controller._update_from_master_state({'module_nr': 0, 'status': 0b00000000})  # Third motor stopped again
        #                             +- actual position
        #                             |     +- desired position
        #                             |     |     +- direction                      +- state                               +- optional skip call check
        #                             v     v     v                                 v                                      v
        for shutter_id, entry in {0: [None, None, ShutterEnums.Direction.STOP, [70, ShutterEnums.State.STOPPED], False],
                                  1: [None, None, ShutterEnums.Direction.STOP, [120, ShutterEnums.State.UP],     False],
                                  2: [99,   99,   ShutterEnums.Direction.STOP, [130, ShutterEnums.State.DOWN]]}.iteritems():
            validate(shutter_id, entry)

        states = controller.get_states()
        states['status'].pop(3)  # Remove the "unused" shutter
        states['detail'].pop(3)
        self.assertEqual(states, {'detail': {0: {'actual_position': None,
                                                 'desired_position': None,
                                                 'state': 'stopped'},
                                             1: {'actual_position': None,
                                                 'desired_position': None,
                                                 'state': 'up'},
                                             2: {'actual_position': 99,
                                                 'desired_position': 99,
                                                 'state': 'down'}},
                                  'status': ['stopped', 'up', 'down']})

    def test_master_event_failsafe(self):
        _ = self

        SetUpTestInjections(master_communicator=Mock(),
                            configuration_controller=Mock(),
                            eeprom_controller=Mock())

        master_controller = MasterClassicController()
        master_controller._shutter_config = {shutter.id: shutter for shutter in ShutterControllerTest.SHUTTER_CONFIG}
        master_controller._shutter_config.pop(0)

        # Got data for an unconfigured shutter. This should not raise.
        master_controller._update_from_master_state({'module_nr': 0, 'status': 0b00000000})


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
