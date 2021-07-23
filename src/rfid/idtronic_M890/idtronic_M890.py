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
IdTronic M890 wrapper
"""

from rfid.idtronic_M890.para.para_handler import ParaPacketHandler
from rfid.idtronic_M890.para.para_transceiver import ParaSender
from rfid.rfid_device import RfidDevice

import logging

logger = logging.getLogger(__name__)


class IdTronicM890(RfidDevice):

    def __init__(self, device_location='/dev/rfid', callback=None):
        self.device_location = device_location
        self.para_sender = ParaSender(self.device_location, self.packet_callback)
        self.packet_handler = ParaPacketHandler(new_scan_callback=self.new_scan_callback)
        super(IdTronicM890, self).__init__(callback)
        logger.debug('Created an idtronic M890 RFID reader.')

    def start(self):
        self.para_sender.start()

    def stop(self):
        self.para_sender.stop()

    def packet_callback(self, para_packet):
        # When a packet is received, handle the packet by the packet handler
        self.packet_handler.handle_packet(para_packet)

    def new_scan_callback(self, rfid_uuid):
        self.callback(rfid_uuid)


if __name__ == '__main__':
    import time
    rfid_reader = IdTronicM890('/dev/rfid')
    rfid_reader.start()
    time.sleep(10)
    rfid_reader.stop()

