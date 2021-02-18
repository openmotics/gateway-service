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
Tests for uCAN communicator module.
"""

from __future__ import absolute_import
import unittest
import xmlrunner
import logging
from mock import Mock
from master.core.core_communicator import CoreCommunicator
from master.core.exceptions import BootloadingException
from master.core.ucan_communicator import UCANCommunicator, SID
from master.core.ucan_command import UCANCommandSpec, UCANPalletCommandSpec, PalletType, Instruction
from master.core.fields import AddressField, ByteArrayField, ByteField, UInt32Field, StringField, LiteralBytesField
from logs import Logs


class UCANCommunicatorTest(unittest.TestCase):
    """ Tests for UCANCommunicator """

    @classmethod
    def setUpClass(cls):
        Logs.setup_logger(log_level=logging.DEBUG)

    def setUp(self):
        self._uint32_helper = UInt32Field('')

    def test_pallet_reconstructing(self):
        received_commands = []

        def send_command(_cid, _command, _fields):
            received_commands.append(_fields)

        core_communicator = CoreCommunicator(controller_serial=Mock())
        core_communicator._send_command = send_command
        ucan_communicator = UCANCommunicator(master_communicator=core_communicator)
        cc_address = '000.000.000.000'
        ucan_address = '000.000.000'
        pallet_type = PalletType.MCU_ID_REQUEST  # Not important for this test

        for length in [1, 3]:
            # Build command
            command = UCANPalletCommandSpec(identifier=AddressField('ucan_address', 3),
                                            pallet_type=pallet_type,
                                            request_fields=[ByteField('foo'), ByteField('bar')],
                                            response_fields=[ByteArrayField('other', length)])

            # Send command to mocked Core communicator
            received_commands = []
            ucan_communicator.do_command(cc_address, command, ucan_address, {'foo': 1, 'bar': 2}, timeout=None)

            # Validate whether the correct data was send to the Core
            self.assertEqual(len(received_commands), 2)
            self.assertDictEqual(received_commands[0], {'cc_address': cc_address,
                                                        'nr_can_bytes': 8,
                                                        'payload': bytearray([129, 0, 0, 0, 0, 0, 0, pallet_type]),
                                                        #                          +--------------+ = source and destination uCAN address
                                                        'sid': SID.BOOTLOADER_PALLET})
            self.assertDictEqual(received_commands[1], {'cc_address': cc_address,
                                                        'nr_can_bytes': 7,
                                                        'payload': bytearray([0, 1, 2, 219, 155, 250, 178, 0]),
                                                        #                        |  |  +----------------+ = checksum
                                                        #                        |  + = bar
                                                        #                        + = foo
                                                        'sid': SID.BOOTLOADER_PALLET})

            # Build fake reply from Core
            consumer = ucan_communicator._consumers[cc_address][0]
            fixed_payload = bytearray([0, 0, 0, 0, 0, 0, pallet_type])
            variable_payload = bytearray(list(range(7, 7 + length)))  # [7] or [7, 8, 9]
            crc_payload = self._uint32_helper.encode(UCANPalletCommandSpec.calculate_crc(fixed_payload + variable_payload))
            ucan_communicator._process_transport_message({'cc_address': cc_address,
                                                          'nr_can_bytes': 8,
                                                          'sid': 1,
                                                          'payload': bytearray([129]) + fixed_payload})
            ucan_communicator._process_transport_message({'cc_address': cc_address,
                                                          'nr_can_bytes': length + 5,
                                                          'sid': 1,
                                                          'payload': bytearray([0]) + variable_payload + crc_payload})
            self.assertDictEqual(consumer.get(1), {'other': list(variable_payload)})

    def test_string_parsing(self):
        core_communicator = Mock()
        ucan_communicator = UCANCommunicator(master_communicator=core_communicator)
        cc_address = '000.000.000.000'
        ucan_address = '000.000.000'
        pallet_type = PalletType.MCU_ID_REQUEST  # Not important for this test
        foo = 'XY'  # 2 chars max, otherwise more segments are needed and the test might get too complex

        # Build response-only command
        command = UCANPalletCommandSpec(identifier=AddressField('ucan_address', 3),
                                        pallet_type=pallet_type,
                                        response_fields=[StringField('foo')])
        ucan_communicator.do_command(cc_address, command, ucan_address, {}, timeout=None)
        consumer = ucan_communicator._consumers[cc_address][0]

        # Build and validate fake reply from Core
        payload_segment_1 = bytearray([0, 0, 0, 0, 0, 0, PalletType.MCU_ID_REPLY])
        payload_segment_2 = bytearray([ord(x) for x in '{0}\x00'.format(foo)])
        crc_payload = self._uint32_helper.encode(UCANPalletCommandSpec.calculate_crc(payload_segment_1 + payload_segment_2))
        payload_segment_2 += crc_payload
        ucan_communicator._process_transport_message({'cc_address': cc_address,
                                                      'nr_can_bytes': 8,
                                                      'sid': 1,
                                                      'payload': bytearray([129]) + payload_segment_1})
        ucan_communicator._process_transport_message({'cc_address': cc_address,
                                                      'nr_can_bytes': 8,
                                                      'sid': 1,
                                                      'payload': bytearray([0]) + payload_segment_2})
        self.assertDictEqual(consumer.get(1), {'foo': foo})

    def test_bootload_lock(self):
        core_communicator = Mock()
        ucan_communicator = UCANCommunicator(master_communicator=core_communicator)
        cc_address = '000.000.000.000'
        ucan_address = '000.000.000'

        command = UCANCommandSpec(sid=SID.NORMAL_COMMAND,
                                  instructions=[Instruction(instruction=[0, 0])],
                                  identifier=AddressField('ucan_address', 3))
        ucan_communicator.do_command(cc_address, command, ucan_address, {}, timeout=None)

        command = UCANPalletCommandSpec(identifier=AddressField('ucan_address', 3),
                                        pallet_type=PalletType.MCU_ID_REPLY)
        ucan_communicator.do_command(cc_address, command, ucan_address, {}, timeout=None)
        pallet_consumer = ucan_communicator._consumers[cc_address][-1]  # Load last consumer

        command = UCANCommandSpec(sid=SID.NORMAL_COMMAND,
                                  instructions=[Instruction(instruction=[0, 0])],
                                  identifier=AddressField('ucan_address', 3))
        with self.assertRaises(BootloadingException):
            ucan_communicator.do_command(cc_address, command, ucan_address, {}, timeout=None)

        command = UCANPalletCommandSpec(identifier=AddressField('ucan_address', 3),
                                        pallet_type=PalletType.MCU_ID_REPLY)
        with self.assertRaises(BootloadingException):
            ucan_communicator.do_command(cc_address, command, ucan_address, {}, timeout=None)

        try:
            pallet_consumer.get(0.1)
        except Exception:
            pass  #

        command = UCANCommandSpec(sid=SID.NORMAL_COMMAND,
                                  instructions=[Instruction(instruction=[0, 0])],
                                  identifier=AddressField('ucan_address', 3))
        ucan_communicator.do_command(cc_address, command, ucan_address, {}, timeout=None)

    def test_crc(self):
        payload = bytearray([10, 50, 250])
        total_payload = payload + self._uint32_helper.encode(UCANPalletCommandSpec.calculate_crc(payload))
        self.assertEqual(0, UCANPalletCommandSpec.calculate_crc(total_payload))
        crc = 0
        for part in payload:
            crc = UCANPalletCommandSpec.calculate_crc(bytearray([part]), crc)
        total_payload = payload + self._uint32_helper.encode(crc)
        self.assertEqual(0, UCANPalletCommandSpec.calculate_crc(total_payload))

    def test_multi_messages(self):
        core_communicator = Mock()
        ucan_communicator = UCANCommunicator(master_communicator=core_communicator)
        cc_address = '000.000.000.000'
        ucan_address = '000.000.000'

        command = UCANCommandSpec(sid=SID.NORMAL_COMMAND,
                                  identifier=AddressField('ucan_address', 3),
                                  instructions=[Instruction(instruction=[0, 10]), Instruction(instruction=[0, 10])],
                                  request_fields=[[LiteralBytesField(1)], [LiteralBytesField(2)]],
                                  response_instructions=[Instruction(instruction=[1, 10], checksum_byte=7),
                                                         Instruction(instruction=[2, 10], checksum_byte=7)],
                                  response_fields=[ByteArrayField('foo', 4)])
        ucan_communicator.do_command(cc_address, command, ucan_address, {}, timeout=None)
        consumer = ucan_communicator._consumers[cc_address][0]

        # Build and validate fake reply from Core
        payload_reply_1 = bytearray([1, 10, 0, 0, 0, 20, 21])
        payload_reply_2 = bytearray([2, 10, 0, 0, 0, 22, 23])
        ucan_communicator._process_transport_message({'cc_address': cc_address,
                                                      'nr_can_bytes': 8,
                                                      'sid': 5,
                                                      'payload': payload_reply_1 + bytearray([UCANCommandSpec.calculate_crc(payload_reply_1)])})
        ucan_communicator._process_transport_message({'cc_address': cc_address,
                                                      'nr_can_bytes': 8,
                                                      'sid': 5,
                                                      'payload': payload_reply_2 + bytearray([UCANCommandSpec.calculate_crc(payload_reply_2)])})
        self.assertDictEqual(consumer.get(1), {'foo': [20, 21, 22, 23]})


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
