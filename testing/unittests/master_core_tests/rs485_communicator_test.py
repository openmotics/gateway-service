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
Tests for RS485 communicator module.
"""

from __future__ import absolute_import
import unittest
import xmlrunner
import logging
import time
import fakesleep
from mock import Mock
from master.core.core_communicator import CoreCommunicator
from master.core.rs485_communicator import RS485Communicator, CommunicationTimedOutException
from master.core.rs485_command import RS485CommandSpec, Instruction
from master.core.core_api import CoreAPI
from master.core.fields import ByteField


class RS485CommunicatorTest(unittest.TestCase):
    """ Tests for RS485Communicator """

    @classmethod
    def setUpClass(cls):
        logger = logging.getLogger('openmotics')
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

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
        rs485_communicator = RS485Communicator(master_communicator=core_communicator, verbose=True)

        command_spec = RS485CommandSpec(instruction=Instruction(instruction='AB'),
                                        request_fields=[ByteField('foo')],
                                        response_fields=[ByteField('bar')])

        with self.assertRaises(RuntimeError):
            # Transparent mode inactive
            rs485_communicator.do_command(command_spec, '000.000.000.000', {'foo': 0}, timeout=None)

        self.assertFalse(rs485_communicator._transparent_mode)
        with rs485_communicator:
            # RS485Communicator as ContextManager activates transparent mode
            self.assertEqual(1, len(received_commands))
            self.assertEqual({'mode': CoreAPI.RS485Mode.TRANSPARENT}, received_commands[0])
            self.assertTrue(rs485_communicator._transparent_mode)
        self.assertEqual(2, len(received_commands))
        self.assertEqual({'mode': CoreAPI.RS485Mode.LIVE}, received_commands[1])
        self.assertFalse(rs485_communicator._transparent_mode)

    def test_rxtx(self):
        received_commands = []

        def do_command(command, fields, timeout=None):
            received_commands.append(fields)

        core_communicator = CoreCommunicator(controller_serial=Mock())
        core_communicator.do_command = do_command
        rs485_communicator = RS485Communicator(master_communicator=core_communicator, verbose=True)
        rs485_communicator._transparent_mode = True

        command_spec = RS485CommandSpec(instruction=Instruction(instruction='AB'),
                                        request_fields=[ByteField('foo')],
                                        response_fields=[ByteField('bar')])

        rs485_communicator.do_command(command_spec, '000.000.000.000', {'foo': 0}, timeout=None)
        self.assertEqual(1, len(received_commands))
        self.assertTrue('payload' in received_commands[0])
        payload = received_commands[0]['payload']
        self.assertEqual(list(RS485CommunicatorTest._build_request_message(b'\x00\x00\x00\x00AB\x00')), payload)
        consumer = rs485_communicator._consumers[0]
        response_payload = RS485CommunicatorTest._build_response_message(b'\x00\x00\x00\x00AC\x04')
        rs485_communicator._process_transport_message({'payload': bytearray(b'FOO') + response_payload[:5]})
        rs485_communicator._process_transport_message({'payload': response_payload[5:]})
        rs485_communicator._process_transport_message({'payload': RS485CommunicatorTest._build_response_message(b'\x00\x00\x00\x01AB\x03')})
        rs485_communicator._process_transport_message({'payload': RS485CommunicatorTest._build_response_message(b'\x00\x00\x00\x00AB\x02', bad_crc=True)})
        with self.assertRaises(CommunicationTimedOutException):
            self.assertEqual({'bar': 1}, consumer.get(1))  # Invalid CRC
        rs485_communicator.do_command(command_spec, '000.000.000.000', {'foo': 0}, timeout=None)
        consumer = rs485_communicator._consumers[0]
        rs485_communicator._process_transport_message({'payload': RS485CommunicatorTest._build_response_message(b'\x00\x00\x00\x00AB\x01')})
        self.assertEqual({'bar': 1}, consumer.get(1))

        command_spec = RS485CommandSpec(instruction=Instruction(instruction='AB'),
                                        request_fields=[ByteField('foo')])
        rs485_communicator.do_command(command_spec, '000.000.000.000', {'foo': 0}, timeout=None)
        consumer = rs485_communicator._consumers[0]
        with self.assertRaises(CommunicationTimedOutException):
            consumer.get(0)

    def test_unresponsiveness(self):
        core_communicator = CoreCommunicator(controller_serial=Mock())
        core_communicator.do_command = Mock()
        rs485_communicator = RS485Communicator(master_communicator=core_communicator, verbose=True)
        rs485_communicator._transparent_mode = True

        command_spec = RS485CommandSpec(instruction=Instruction(instruction='AB'),
                                        request_fields=[ByteField('foo')],
                                        response_fields=[ByteField('bar')])

        with self.assertRaises(CommunicationTimedOutException):
            core_communicator.do_command.side_effect = lambda command, fields, timeout=None: time.sleep(2)
            rs485_communicator.do_command(command_spec, '000.000.000.000', {'foo': 0}, timeout=1)  # No RS485 response
        with self.assertRaises(CommunicationTimedOutException):
            core_communicator.do_command.side_effect = CommunicationTimedOutException('Master unresponsive')
            rs485_communicator.do_command(command_spec, '000.000.000.000', {'foo': 0}, timeout=1)

    @staticmethod
    def _build_request_message(payload):
        crc = RS485CommandSpec.calculate_crc(bytearray(payload))
        return bytearray(b'ST' + payload + b'C' + crc + b'\r\n\r\n')

    @staticmethod
    def _build_response_message(payload, bad_crc=False):
        if bad_crc:
            crc = bytearray(b'\x00\x00')
        else:
            crc = RS485CommandSpec.calculate_crc(bytearray(payload))
        return bytearray(b'RC' + payload + b'C' + crc + b'\r\n')


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
