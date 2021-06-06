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
import os
import tempfile

import power.power_api as power_api
from peewee import SqliteDatabase
from gateway.pubsub import PubSub
from gateway.hal.master_event import MasterEvent
from gateway.models import Module, EnergyModule, EnergyCT
from gateway.dto import ModuleDTO
from ioc import SetTestMode, SetUpTestInjections
from power.power_communicator import InAddressModeException, PowerCommunicator
from serial_test import SerialMock, sin, sout
from serial_utils import RS485, CommunicationTimedOutException

MODELS = [Module, EnergyModule, EnergyCT]


class PowerCommunicatorTest(unittest.TestCase):
    """ Tests for PowerCommunicator class """

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.db_filename = tempfile.mktemp()
        cls.test_db = SqliteDatabase(cls.db_filename)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db_filename):
            os.remove(cls.db_filename)

    def setUp(self):
        self.pubsub = PubSub()
        SetUpTestInjections(pubsub=self.pubsub)
        self.power_data = []  # type: list
        self.serial = RS485(SerialMock(self.power_data))
        SetUpTestInjections(power_serial=self.serial)
        self.communicator = PowerCommunicator()
        self.test_db.bind(MODELS, bind_refs=True, bind_backrefs=True)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

    def tearDown(self):
        self.serial.stop()
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_do_command(self):
        """ Test for standard behavior PowerCommunicator.do_command. """
        action = power_api.get_voltage(power_api.POWER_MODULE)

        self.power_data.extend([
            sin(action.create_input(1, 1)), sout(action.create_output(1, 1, 49.5))
        ])
        self.serial.start()

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
            sin(power_api.set_address(power_api.POWER_MODULE).create_input(0, 0, 2)),
            sout(power_api.want_an_address(power_api.ENERGY_MODULE).create_output(0, 0)),
            sin(power_api.set_address(power_api.ENERGY_MODULE).create_input(0, 0, 3)),
            sout(power_api.want_an_address(power_api.P1_CONCENTRATOR).create_output(0, 0)),
            sin(power_api.set_address(power_api.P1_CONCENTRATOR).create_input(0, 0, 4)),
            sout(bytearray()),  # Timeout read after 1 second
            sin(sad.create_input(power_api.BROADCAST_ADDRESS, 3, power_api.NORMAL_MODE)),
            sin(sad_p1c.create_input(power_api.BROADCAST_ADDRESS, 4, power_api.NORMAL_MODE))
        ])
        self.serial.start()

        self.assertEqual(0, len(Module.select().where(Module.source == ModuleDTO.Source.GATEWAY,
                                                      Module.hardware_type == ModuleDTO.HardwareType.PHYSICAL)))

        self.communicator.start_address_mode()
        self.assertTrue(self.communicator.in_address_mode())
        self.pubsub._publish_all_events()
        time.sleep(0.5)
        assert [] == events

        self.communicator.stop_address_mode()
        self.pubsub._publish_all_events()
        assert MasterEvent(MasterEvent.Types.POWER_ADDRESS_EXIT, {}) in events
        assert len(events) == 1

        modules = Module.select().where(Module.source == ModuleDTO.Source.GATEWAY,
                                        Module.hardware_type == ModuleDTO.HardwareType.PHYSICAL)
        self.assertEqual(['2', '3', '4'], [module.address for module in modules])

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

        self.communicator.start_address_mode()
        time.sleep(1.1)

        self.assertEqual((49.5, ), self.communicator.do_command(1, action))


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
