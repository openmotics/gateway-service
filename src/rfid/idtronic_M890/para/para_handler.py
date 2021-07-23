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
Para packet handler
"""

from rfid.idtronic_M890.para.para_packet import ParaPacketType, ParaPacket, CardType
from rfid.idtronic_M890.para.para_exception import ParaException

import logging
logger = logging.getLogger(__name__)

if False:  # MyPy
    from typing import Any, Dict, Callable


# @Injectable.named('para_packet_handler')
class ParaPacketHandler(object):
    """ Packet handler for the ParaPackets, this can be extended in the future for multiple requests, and for keeping state of the reader"""
    # At this point only one kind of packet is implemented, but can be extended in the future


    def __init__(self, new_scan_callback):
        self.handlers = {
            ParaPacketType.AutoListCard.value: self.handle_auto_list
        }  # type: Dict[ParaPacketType.value, Callable[[ParaPacket], Any]]
        self.new_scan_callback = new_scan_callback

    def handle_packet(self, para_packet):
        # type: (ParaPacket) -> Any
        packet_type = para_packet.header.command_type
        if packet_type in self.handlers:
            handler = self.handlers[packet_type]
            return handler(para_packet)
        return None

    def handle_auto_list(self, para_packet):
        # type: (ParaPacket) -> Any
        _ = self
        # Ignore the empty list packets
        if not para_packet.data:
            return
        # General scan parameters
        card_type = para_packet.data[0]
        # scan_period = para_packet.data[1]
        # scanned_antenna = para_packet.data[2]
        # notice_type = para_packet.data[3]
        # reserved_future_use = para_packet.data[4]

        if card_type in [CardType.ISO14443A.value, CardType.ISO14443B.value]:
            # auto reporting format for ISO14443 cards
            # ATQL = para_packet.data[5]
            # ATQH = para_packet.data[6]
            # SAK = para_packet.data[7]
            uuid_length = para_packet.data[8]
            logger.debug('Detected new ISO14443 card scan: Card type: {}, uuid_length: {}'.format(card_type, uuid_length))
            scanned_uuid = para_packet.data[-uuid_length:]
        elif card_type == CardType.ISO15693.value:
            scanned_uuid = para_packet.data[5:]
        else:
            raise ParaException('Cannot handle auto list packet: Cannot detect card type')
        scanned_uuid_str = ''.join('{:02X}'.format(x) for x in scanned_uuid)
        self.new_scan_callback(scanned_uuid_str)
