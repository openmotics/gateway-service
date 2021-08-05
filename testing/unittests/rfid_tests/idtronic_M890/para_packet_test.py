# Copyright (C) 2021 OpenMotics BV
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
ParaPacket tests
"""
from __future__ import absolute_import

import unittest

from rfid.idtronic_M890.para.para_packet import ParaPacket, ParaPacketType


class ParaPacketTest(unittest.TestCase):

    def setUp(self):
        self.packet_1 = ParaPacket.create(ParaPacketType.AutoListCard, [0x01, 0x02])
        self.packet_2 = ParaPacket.create(ParaPacketType.AutoListCard, [0x01, 0x02])
        self.packet_3 = ParaPacket.create(ParaPacketType.AutoListCard, [0x01, 0x02, 0x03])

    def test_create_packet(self):
        packet = ParaPacket.create(ParaPacketType.AutoListCard, [0x01, 0x02])
        self.assertTrue(packet.is_complete())
        self.assertTrue(packet.crc_check())
        self.assertEqual(packet, ParaPacket([0x50, 0x00, 0x02, 0x23, 0x01, 0x02, 0x72]))

    def test_create_packet_per_byte(self):
        # Correct packet
        packet = ParaPacket()
        for byte in [0x50, 0x00, 0x02, 0x23, 0x01, 0x02]:
            packet.append_byte(byte)
            self.assertFalse(packet.is_complete())
        packet.append_byte(0x72)
        self.assertTrue(packet.is_complete())
        self.assertTrue(packet.crc_check())

        # Wrong CRC
        packet = ParaPacket()
        for byte in [0x50, 0x00, 0x02, 0x23, 0x01, 0x02]:
            packet.append_byte(byte)
            self.assertFalse(packet.is_complete())
        packet.append_byte(0x71)
        self.assertTrue(packet.is_complete())
        self.assertFalse(packet.crc_check())

        # append to full packet
        packet = ParaPacket()
        for byte in [0x50, 0x00, 0x02, 0x23, 0x01, 0x02, 0x03]:
            packet.append_byte(byte)
        self.assertTrue(packet.is_complete())
        with self.assertRaises(ValueError):
            packet.append_byte(0x00)

        # append bytes
        packet = ParaPacket()
        for byte in [b'\x50', b'\x00', b'\x02', b'\x23', b'\x01', b'\x02', b'\x03']:
            packet.append_byte(byte)
        self.assertTrue(packet.is_complete())
        with self.assertRaises(ValueError):
            packet.append_byte(0x00)

    def test_create_packet_long(self):
        with self.assertRaises(ValueError):
            packet = ParaPacket.create(ParaPacketType.AutoListCard, [0x01] * 65536)

    def test_equal_packet(self):
        self.assertEqual(self.packet_1, self.packet_2)
        self.assertNotEqual(self.packet_1, self.packet_3)

