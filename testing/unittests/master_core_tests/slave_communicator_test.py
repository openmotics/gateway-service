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
"""
Tests for Slave communicator module.
"""

from __future__ import absolute_import
import unittest
import xmlrunner
import logging
import time
import fakesleep
from mock import Mock
from master.core.core_communicator import CoreCommunicator
from master.core.slave_communicator import SlaveCommunicator, CommunicationTimedOutException
from master.core.slave_command import SlaveCommandSpec, Instruction
from master.core.core_api import CoreAPI
from master.core.fields import ByteField
from logs import Logs


class SlaveCommunicatorTest(unittest.TestCase):
    """ Tests for SlaveCommunicator """

    @classmethod
    def setUpClass(cls):
        Logs.setup_logger(log_level=logging.DEBUG)

    def setUp(self):
        fakesleep.monkey_patch()

    def tearDown(self):
        fakesleep.monkey_restore()

    def test_transparent_mode(self):
        received_commands = []

        def do_command(command, fields, timeout=None):
            received_commands.append(fields)
            return {'mode': fields['mode']}

        core_communicator = CoreCommunicator(controller_serial=Mock())
        core_communicator.do_command = do_command
        slave_communicator = SlaveCommunicator(master_communicator=core_communicator, verbose=True)
        address = '000.000.000.000'

        command_spec = SlaveCommandSpec(instruction=Instruction(instruction='AB'),
                                        request_fields=[ByteField('foo')],
                                        response_fields=[ByteField('bar')])

        with self.assertRaises(RuntimeError):
            # Transparent mode inactive
            slave_communicator.do_command(address, command_spec, {'foo': 0}, timeout=None)

        self.assertFalse(slave_communicator._transparent_mode)
        with slave_communicator:
            # SlaveCommunicator as ContextManager activates transparent mode
            self.assertEqual(1, len(received_commands))
            self.assertEqual({'mode': CoreAPI.SlaveBusMode.TRANSPARENT}, received_commands[0])
            self.assertTrue(slave_communicator._transparent_mode)
        self.assertEqual(2, len(received_commands))
        self.assertEqual({'mode': CoreAPI.SlaveBusMode.LIVE}, received_commands[1])
        self.assertFalse(slave_communicator._transparent_mode)

    def test_rxtx(self):
        received_commands = []

        def do_command(command, fields, timeout=None):
            received_commands.append(fields)

        core_communicator = CoreCommunicator(controller_serial=Mock())
        core_communicator.do_command = do_command
        slave_communicator = SlaveCommunicator(master_communicator=core_communicator, verbose=True)
        slave_communicator._transparent_mode = True
        address = '000.000.000.000'

        command_spec = SlaveCommandSpec(instruction=Instruction(instruction='AB'),
                                        request_fields=[ByteField('foo')],
                                        response_fields=[ByteField('bar')])

        slave_communicator.do_command(address, command_spec, {'foo': 0}, timeout=None)
        self.assertEqual(1, len(received_commands))
        self.assertTrue('payload' in received_commands[0])
        payload = received_commands[0]['payload']
        self.assertEqual(SlaveCommunicatorTest._build_request_message(b'\x00\x00\x00\x00AB\x00'), payload)
        consumer = slave_communicator._consumers[0]
        response_payload = SlaveCommunicatorTest._build_response_message(b'\x00\x00\x00\x00AC\x04')
        slave_communicator._process_transport_message({'payload': bytearray(b'FOO') + response_payload[:5]})
        slave_communicator._process_transport_message({'payload': response_payload[5:]})
        slave_communicator._process_transport_message({'payload': SlaveCommunicatorTest._build_response_message(b'\x00\x00\x00\x01AB\x03')})
        slave_communicator._process_transport_message({'payload': SlaveCommunicatorTest._build_response_message(b'\x00\x00\x00\x00AB\x02', bad_crc=True)})
        with self.assertRaises(CommunicationTimedOutException):
            self.assertEqual({'bar': 1}, consumer.get(1))  # Invalid CRC
        slave_communicator.do_command(address, command_spec, {'foo': 0}, timeout=None)
        consumer = slave_communicator._consumers[0]
        slave_communicator._process_transport_message({'payload': SlaveCommunicatorTest._build_response_message(b'\x00\x00\x00\x00AB\x01')})
        self.assertEqual({'bar': 1}, consumer.get(1))

        command_spec = SlaveCommandSpec(instruction=Instruction(instruction='AB'),
                                        request_fields=[ByteField('foo')])
        slave_communicator.do_command(address, command_spec, {'foo': 0}, timeout=None)
        consumer = slave_communicator._consumers[0]
        with self.assertRaises(CommunicationTimedOutException):
            consumer.get(0)

    def test_unresponsiveness(self):
        core_communicator = CoreCommunicator(controller_serial=Mock())
        core_communicator.do_command = Mock()
        slave_communicator = SlaveCommunicator(master_communicator=core_communicator, verbose=True)
        slave_communicator._transparent_mode = True
        address = '000.000.000.000'

        command_spec = SlaveCommandSpec(instruction=Instruction(instruction='AB'),
                                        request_fields=[ByteField('foo')],
                                        response_fields=[ByteField('bar')])

        with self.assertRaises(CommunicationTimedOutException):
            core_communicator.do_command.side_effect = lambda command, fields, timeout=None: time.sleep(2)
            slave_communicator.do_command(address, command_spec, {'foo': 0}, timeout=1)  # No slave response
        with self.assertRaises(CommunicationTimedOutException):
            core_communicator.do_command.side_effect = CommunicationTimedOutException('Master unresponsive')
            slave_communicator.do_command(address, command_spec, {'foo': 0}, timeout=1)

    @staticmethod
    def _build_request_message(payload):
        crc = SlaveCommandSpec.calculate_crc(bytearray(payload))
        return bytearray(b'ST' + payload + b'C' + crc + b'\r\n\r\n')

    @staticmethod
    def _build_response_message(payload, bad_crc=False):
        if bad_crc:
            crc = bytearray(b'\x00\x00')
        else:
            crc = SlaveCommandSpec.calculate_crc(bytearray(payload))
        return bytearray(b'RC' + payload + b'C' + crc + b'\r\n')


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
