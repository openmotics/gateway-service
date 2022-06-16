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
Tests for EnergyCommunicator module.
"""

from __future__ import absolute_import

import logging
import time
import unittest
import mock

from pytest import mark
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from enums import HardwareType
from gateway.dto import ModuleDTO
from gateway.energy.energy_api import ADDRESS_MODE, BROADCAST_ADDRESS, \
    NORMAL_MODE, EnergyAPI
from gateway.energy.energy_communicator import EnergyCommunicator, \
    InAddressModeException
from gateway.enums import EnergyEnums
from gateway.models import Base, Database, EnergyCT, EnergyModule, Module
from gateway.pubsub import PubSub
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs
from serial_test import SerialMock, sin, sout
from serial_utils import RS485, CommunicationTimedOutException

MODELS = [Module, EnergyModule, EnergyCT]


class EnergyCommunicatorTest(unittest.TestCase):
    """ Tests for EnergyCommunicator class """
    @classmethod
    def setUpClass(cls):
        super(EnergyCommunicatorTest, cls).setUpClass()
        SetTestMode()
        Logs.set_loglevel(logging.DEBUG, namespace='gateway.energy.energy_communicator')
        Logs.set_loglevel(logging.DEBUG, namespace='sqlalchemy.engine')

    @classmethod
    def tearDownClass(cls):
        super(EnergyCommunicatorTest, cls).tearDownClass()

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=True, bind=engine)

        self.session = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()


        self.addCleanup(session_mock.stop)

        self.pubsub = PubSub()
        SetUpTestInjections(pubsub=self.pubsub)
        self.energy_data = []  # type: list
        self.serial = RS485(SerialMock(self.energy_data))
        SetUpTestInjections(energy_serial=self.serial)
        self.communicator = EnergyCommunicator()

    def test_do_command(self):
        """ Test for standard behavior EnergyCommunicator.do_command. """
        action = EnergyAPI.get_voltage(EnergyEnums.Version.POWER_MODULE)

        self.energy_data.extend([
            sin(action.create_input(1, 1)), sout(action.create_output(1, 1, 49.5))
        ])
        self.serial.start()

        output = self.communicator.do_command(1, action)
        self.assertEqual((49.5, ), output)

        self.assertEqual(14, self.communicator.get_communication_statistics()['bytes_written'])
        self.assertEqual(18, self.communicator.get_communication_statistics()['bytes_read'])

    def test_do_command_timeout_once(self):
        """ Test for timeout in EnergyCommunicator.do_command. """
        action = EnergyAPI.get_voltage(EnergyEnums.Version.POWER_MODULE)

        self.energy_data.extend([
            sin(action.create_input(1, 1)),
            sout(bytearray()),
            sin(action.create_input(1, 2)),
            sout(action.create_output(1, 2, 49.5))
        ])
        self.serial.start()

        output = self.communicator.do_command(1, action)
        self.assertEqual((49.5, ), output)

    def test_do_command_timeout_twice(self):
        """ Test for timeout in EnergyCommunicator.do_command. """
        action = EnergyAPI.get_voltage(EnergyEnums.Version.POWER_MODULE)

        self.energy_data.extend([
            sin(action.create_input(1, 1)),
            sout(bytearray()),
            sin(action.create_input(1, 2)),
            sout(bytearray())
        ])
        self.serial.start()

        with self.assertRaises(CommunicationTimedOutException):
            self.communicator.do_command(1, action)

    def test_do_command_split_data(self):
        """ Test EnergyCommunicator.do_command when the data is split over multiple reads. """
        action = EnergyAPI.get_voltage(EnergyEnums.Version.POWER_MODULE)
        out = action.create_output(1, 1, 49.5)

        self.energy_data.extend([
            sin(action.create_input(1, 1)),
            sout(out[:5]), sout(out[5:])
        ])
        self.serial.start()

        output = self.communicator.do_command(1, action)
        self.assertEqual((49.5, ), output)

    def test_wrong_response(self):
        """ Test EnergyCommunicator.do_command when the power module returns a wrong response. """
        action_1 = EnergyAPI.get_voltage(EnergyEnums.Version.POWER_MODULE)
        action_2 = EnergyAPI.get_frequency(EnergyEnums.Version.POWER_MODULE)

        self.energy_data.extend([
            sin(action_1.create_input(1, 1)),
            sout(action_2.create_output(3, 2, 49.5))
        ])
        self.serial.start()

        with self.assertRaises(Exception):
            self.communicator.do_command(1, action_1)

    @mark.slow
    def test_address_mode(self):
        """ Test the address mode. """
        sad = EnergyAPI.set_addressmode(EnergyEnums.Version.POWER_MODULE)
        sad_p1c = EnergyAPI.set_addressmode(EnergyEnums.Version.P1_CONCENTRATOR)

        self.energy_data.extend([
            sin(sad.create_input(BROADCAST_ADDRESS, 1, ADDRESS_MODE)),
            sin(sad_p1c.create_input(BROADCAST_ADDRESS, 2, ADDRESS_MODE)),
            sout(EnergyAPI.want_an_address(EnergyEnums.Version.POWER_MODULE).create_output(0, 0)),
            sin(EnergyAPI.set_address(EnergyEnums.Version.POWER_MODULE).create_input(0, 0, 2)),
            sout(EnergyAPI.want_an_address(EnergyEnums.Version.ENERGY_MODULE).create_output(0, 0)),
            sin(EnergyAPI.set_address(EnergyEnums.Version.ENERGY_MODULE).create_input(0, 0, 3)),
            sout(EnergyAPI.want_an_address(EnergyEnums.Version.P1_CONCENTRATOR).create_output(0, 0)),
            sin(EnergyAPI.set_address(EnergyEnums.Version.P1_CONCENTRATOR).create_input(0, 0, 4)),
            sout(bytearray()),  # Timeout read after 1 second
            sin(sad.create_input(BROADCAST_ADDRESS, 3, NORMAL_MODE)),
            sin(sad_p1c.create_input(BROADCAST_ADDRESS, 4, NORMAL_MODE))
        ])
        self.serial.start()

        with self.session as db:
            self.assertEqual(0, db.query(Module).where(Module.source == ModuleDTO.Source.GATEWAY,
                                                       Module.hardware_type == HardwareType.PHYSICAL).count())
        self.communicator.start_address_mode()
        time.sleep(0.5)
        self.assertTrue(self.communicator.in_address_mode())
        self.communicator.stop_address_mode()
        time.sleep(0.5)
        with self.session as db:
            modules = db.query(Module).where(Module.source == ModuleDTO.Source.GATEWAY,
                                             Module.hardware_type == HardwareType.PHYSICAL).all()
            self.assertEqual(['2', '3', '4'], [module.address for module in modules])

        self.assertFalse(self.communicator.in_address_mode())

    @mark.slow
    def test_do_command_in_address_mode(self):
        """ Test the behavior of do_command in address mode."""
        action = EnergyAPI.get_voltage(EnergyEnums.Version.POWER_MODULE)
        sad = EnergyAPI.set_addressmode(EnergyEnums.Version.POWER_MODULE)
        sad_p1c = EnergyAPI.set_addressmode(EnergyEnums.Version.P1_CONCENTRATOR)

        self.energy_data.extend([
            sin(sad.create_input(BROADCAST_ADDRESS, 1, ADDRESS_MODE)),
            sin(sad_p1c.create_input(BROADCAST_ADDRESS, 2, ADDRESS_MODE)),
            sout(bytearray()),  # Timeout read after 1 second
            sin(sad.create_input(BROADCAST_ADDRESS, 3, NORMAL_MODE)),
            sin(sad_p1c.create_input(BROADCAST_ADDRESS, 4, NORMAL_MODE)),
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
        action = EnergyAPI.get_voltage(EnergyEnums.Version.POWER_MODULE)
        sad = EnergyAPI.set_addressmode(EnergyEnums.Version.POWER_MODULE)
        sad_p1c = EnergyAPI.set_addressmode(EnergyEnums.Version.P1_CONCENTRATOR)

        self.energy_data.extend([
            sin(sad.create_input(BROADCAST_ADDRESS, 1, ADDRESS_MODE)),
            sin(sad_p1c.create_input(BROADCAST_ADDRESS, 2, ADDRESS_MODE)),
            sout(bytearray()),  # Timeout read after 1 second
            sin(sad.create_input(BROADCAST_ADDRESS, 3, NORMAL_MODE)),
            sin(sad_p1c.create_input(BROADCAST_ADDRESS, 4, NORMAL_MODE)),
            sin(action.create_input(1, 5)),
            sout(action.create_output(1, 5, 49.5))
        ])
        self.communicator = EnergyCommunicator(address_mode_timeout=1)
        self.serial.start()

        self.communicator.start_address_mode()
        time.sleep(1.1)

        self.assertEqual((49.5, ), self.communicator.do_command(1, action))
