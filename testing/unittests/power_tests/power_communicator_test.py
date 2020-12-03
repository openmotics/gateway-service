# Copyright (C) 2016 OpenMotics BV
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
Tests for PowerCommunicator module.
"""

from __future__ import absolute_import

import time
import unittest

import xmlrunner
from pytest import mark

import power.power_api as power_api
from gateway.pubsub import PubSub
from gateway.hal.master_event import MasterEvent
from ioc import SetTestMode, SetUpTestInjections
from power.power_communicator import InAddressModeException, PowerCommunicator
from power.power_store import PowerStore
from serial_test import SerialMock, sin, sout
from serial_utils import RS485, CommunicationTimedOutException


class PowerCommunicatorTest(unittest.TestCase):
    """ Tests for PowerCommunicator class """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.pubsub = PubSub()
        SetUpTestInjections(pubsub=self.pubsub)
        self.power_data = []  # type: list
        SetUpTestInjections(power_db=':memory:')
        self.serial = RS485(SerialMock(self.power_data))
        self.store = PowerStore()
        SetUpTestInjections(power_serial=self.serial,
                            power_store=self.store)
        self.communicator = PowerCommunicator()

    def tearDown(self):
        self.communicator.stop()
        self.serial.stop()

    def test_do_command(self):
        """ Test for standard behavior PowerCommunicator.do_command. """
        action = power_api.get_voltage(power_api.POWER_MODULE)

        self.power_data.extend([
            sin(action.create_input(1, 1)), sout(action.create_output(1, 1, 49.5))
        ])
        self.serial.start()
        self.communicator.start()

        output = self.communicator.do_command(1, action)
        self.assertEqual((49.5, ), output)

        self.assertEqual(14, self.communicator.get_communication_statistics()['bytes_written'])
        self.assertEqual(18, self.communicator.get_communication_statistics()['bytes_read'])

    def test_do_command_timeout_once(self):
        """ Test for timeout in PowerCommunicator.do_command. """
        action = power_api.get_voltage(power_api.POWER_MODULE)

        self.power_data.extend([
            sin(action.create_input(1, 1)),
            sout(bytearray()),
            sin(action.create_input(1, 2)),
            sout(action.create_output(1, 2, 49.5))
        ])
        self.serial.start()
        self.communicator.start()

        output = self.communicator.do_command(1, action)
        self.assertEqual((49.5, ), output)

    def test_do_command_timeout_twice(self):
        """ Test for timeout in PowerCommunicator.do_command. """
        action = power_api.get_voltage(power_api.POWER_MODULE)

        self.power_data.extend([
            sin(action.create_input(1, 1)),
            sout(bytearray()),
            sin(action.create_input(1, 2)),
            sout(bytearray())
        ])
        self.serial.start()
        self.communicator.start()

        with self.assertRaises(CommunicationTimedOutException):
            self.communicator.do_command(1, action)

    def test_do_command_split_data(self):
        """ Test PowerCommunicator.do_command when the data is split over multiple reads. """
        action = power_api.get_voltage(power_api.POWER_MODULE)
        out = action.create_output(1, 1, 49.5)

        self.power_data.extend([
            sin(action.create_input(1, 1)),
            sout(out[:5]), sout(out[5:])
        ])
        self.serial.start()
        self.communicator.start()

        output = self.communicator.do_command(1, action)
        self.assertEqual((49.5, ), output)

    def test_wrong_response(self):
        """ Test PowerCommunicator.do_command when the power module returns a wrong response. """
        action_1 = power_api.get_voltage(power_api.POWER_MODULE)
        action_2 = power_api.get_frequency(power_api.POWER_MODULE)

        self.power_data.extend([
            sin(action_1.create_input(1, 1)),
            sout(action_2.create_output(3, 2, 49.5))
        ])
        self.serial.start()
        self.communicator.start()

        with self.assertRaises(Exception):
            self.communicator.do_command(1, action_1)

    @mark.slow
    def test_address_mode(self):
        """ Test the address mode. """
        events = []

        def handle_events(master_event):
            events.append(master_event)

        self.pubsub.subscribe_master_events(PubSub.MasterTopics.POWER, handle_events)

        sad = power_api.set_addressmode(power_api.POWER_MODULE)
        sad_p1c = power_api.set_addressmode(power_api.P1_CONCENTRATOR)

        self.power_data.extend([
            sin(sad.create_input(power_api.BROADCAST_ADDRESS, 1, power_api.ADDRESS_MODE)),
            sin(sad_p1c.create_input(power_api.BROADCAST_ADDRESS, 2, power_api.ADDRESS_MODE)),
            sout(power_api.want_an_address(power_api.POWER_MODULE).create_output(0, 0)),
            sin(power_api.set_address(power_api.POWER_MODULE).create_input(0, 0, 1)),
            sout(power_api.want_an_address(power_api.ENERGY_MODULE).create_output(0, 0)),
            sin(power_api.set_address(power_api.ENERGY_MODULE).create_input(0, 0, 2)),
            sout(power_api.want_an_address(power_api.P1_CONCENTRATOR).create_output(0, 0)),
            sin(power_api.set_address(power_api.P1_CONCENTRATOR).create_input(0, 0, 3)),
            sout(bytearray()),  # Timeout read after 1 second
            sin(sad.create_input(power_api.BROADCAST_ADDRESS, 3, power_api.NORMAL_MODE)),
            sin(sad_p1c.create_input(power_api.BROADCAST_ADDRESS, 4, power_api.NORMAL_MODE))
        ])
        self.serial.start()
        self.communicator.start()

        self.assertEqual(self.store.get_free_address(), 1)

        self.communicator.start_address_mode()
        self.assertTrue(self.communicator.in_address_mode())
        self.pubsub._publisher_loop()
        time.sleep(0.5)
        assert [] == events

        self.communicator.stop_address_mode()
        self.pubsub._publisher_loop()
        assert MasterEvent(MasterEvent.Types.POWER_ADDRESS_EXIT, {}) in events
        assert len(events) == 1

        self.assertEqual(self.store.get_free_address(), 4)
        self.assertFalse(self.communicator.in_address_mode())


    @mark.slow
    def test_do_command_in_address_mode(self):
        """ Test the behavior of do_command in address mode."""
        action = power_api.get_voltage(power_api.POWER_MODULE)
        sad = power_api.set_addressmode(power_api.POWER_MODULE)
        sad_p1c = power_api.set_addressmode(power_api.P1_CONCENTRATOR)

        self.power_data.extend([
            sin(sad.create_input(power_api.BROADCAST_ADDRESS, 1, power_api.ADDRESS_MODE)),
            sin(sad_p1c.create_input(power_api.BROADCAST_ADDRESS, 2, power_api.ADDRESS_MODE)),
            sout(bytearray()),  # Timeout read after 1 second
            sin(sad.create_input(power_api.BROADCAST_ADDRESS, 3, power_api.NORMAL_MODE)),
            sin(sad_p1c.create_input(power_api.BROADCAST_ADDRESS, 4, power_api.NORMAL_MODE)),
            sin(action.create_input(1, 5)),
            sout(action.create_output(1, 5, 49.5))
        ])
        self.serial.start()
        self.communicator.start()

        self.communicator.start_address_mode()
        with self.assertRaises(InAddressModeException):
            self.communicator.do_command(1, action)

        self.communicator.stop_address_mode()
        self.assertEqual((49.5, ), self.communicator.do_command(1, action))

    @mark.slow
    def test_address_mode_timeout(self):
        """ Test address mode timeout. """
        action = power_api.get_voltage(power_api.POWER_MODULE)
        sad = power_api.set_addressmode(power_api.POWER_MODULE)
        sad_p1c = power_api.set_addressmode(power_api.P1_CONCENTRATOR)

        self.power_data.extend([
            sin(sad.create_input(power_api.BROADCAST_ADDRESS, 1, power_api.ADDRESS_MODE)),
            sin(sad_p1c.create_input(power_api.BROADCAST_ADDRESS, 2, power_api.ADDRESS_MODE)),
            sout(bytearray()),  # Timeout read after 1 second
            sin(sad.create_input(power_api.BROADCAST_ADDRESS, 3, power_api.NORMAL_MODE)),
            sin(sad_p1c.create_input(power_api.BROADCAST_ADDRESS, 4, power_api.NORMAL_MODE)),
            sin(action.create_input(1, 5)),
            sout(action.create_output(1, 5, 49.5))
        ])
        self.communicator = PowerCommunicator(address_mode_timeout=1)
        self.serial.start()
        self.communicator.start()

        self.communicator.start_address_mode()
        time.sleep(1.1)

        self.assertEqual((49.5, ), self.communicator.do_command(1, action))

    @mark.slow
    def test_timekeeper(self):
        """ Test the TimeKeeper. """
        self.store.register_power_module(1, power_api.POWER_MODULE)

        time_action = power_api.set_day_night(power_api.POWER_MODULE)
        times = [power_api.NIGHT for _ in range(8)]
        action = power_api.get_voltage(power_api.POWER_MODULE)

        self.power_data.extend([
            sin(time_action.create_input(1, 1, *times)),
            sout(time_action.create_output(1, 1)),
            sin(action.create_input(1, 2)),
            sout(action.create_output(1, 2, 243))
        ])
        self.communicator = PowerCommunicator(time_keeper_period=1)
        self.serial.start()
        self.communicator.start()

        time.sleep(1.5)
        self.assertEqual((243, ), self.communicator.do_command(1, action))


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
