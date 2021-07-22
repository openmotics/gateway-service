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

from rfid.idtronic_M890.para.para_packet import ParaPacketType, ParaPacket

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
        scanned_uuid = para_packet.data
        if scanned_uuid:
            self.new_scan_callback(scanned_uuid)