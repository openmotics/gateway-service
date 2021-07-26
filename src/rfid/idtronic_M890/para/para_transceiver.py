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
Para packets transceiver
"""
import logging
import os
import select
import serial
from threading import Thread
from rfid.idtronic_M890.para.para_packet import ParaPacket

logger = logging.getLogger(__name__)


class ParaSender(object):
    def __init__(self, serial_endpoint, callback=None):
        self.serial_endpoint = serial_endpoint
        self.callback = callback
        self.reader_thread = Thread(target=self.reader_runner, name='reader-thread', daemon=False)
        self.is_running = False
        # Set the correct serial device parameters according to the specifications in the datasheet
        self.serial_device = serial.Serial(port=self.serial_endpoint,
                                           baudrate=115200,
                                           bytesize=serial.EIGHTBITS,
                                           parity=serial.PARITY_NONE,
                                           stopbits=serial.STOPBITS_ONE,
                                           timeout=1,
                                           write_timeout=1)
        logger.debug('ParaSender is created: {}'.format({'endpoint': self.serial_endpoint, 'is_running': self.is_running}))

    def __del__(self):
        self.stop()

    def set_callback(self, callback):
        self.callback = callback

    def start(self):
        logger.debug('Starting ParaSender')
        if self.callback is not None and not self.is_running:
            self.is_running = True
            self.reader_thread.start()
        else:
            logger.warning('ParaSender was already started, skipping this start instruction.')

    def stop(self):
        logger.debug('Stopping ParaSender')
        self.is_running = False
        self.reader_thread.join()
        self.serial_device.close()

    def reader_runner(self):
        packet = ParaPacket()
        while self.is_running:
            try:
                byte = self.serial_device.read(1)
                # Ignore empty send bytes: This means that the serial device can't read any bytes
                if byte == b'':
                    continue
                if not packet.is_complete():
                    packet.append_byte(byte)
                else:
                    raise Exception("received a new byte for an already full package: 0x{}".format(byte.hex()))
                if packet.is_complete():
                    if packet.crc_check():
                        logger.debug('received a para-packet: {}'.format(packet.get_oneliner()))
                        self.callback(packet)
                        packet = ParaPacket()
                    else:
                        raise Exception("Received package with non matching XOR: {}".format(packet.get_oneliner()))
            except KeyboardInterrupt:
                return
            except Exception as ex:
                import traceback
                traceback.print_exc()
                logger.error("Unexpected error: {}".format(ex))
                packet = ParaPacket()

    def send(self, para_packet):
        try:
            if not para_packet.is_complete():
                raise Exception("package is not complete!!")

            logger.debug("para_transceiver: sending:  {}".format(para_packet.get_oneliner()))
            self.serial_device.write(para_packet.serialize())
        except Exception as ex:
            logger.error("Could not send the para-packet: {}".format(ex))


if __name__ == '__main__':
    import time

    def cb(pp):
        print(">> {}".format(pp.get_oneliner()))


    ps = ParaSender('/dev/rfid')
    ps.set_callback(cb)
    print('Starting...')
    ps.start()
    print('Started')

    time.sleep(2)
    # Send set buzzer command
    # pp = ParaPacket(bytes([0x50, 0x00, 0x02, 0x02, 0x03, 0x04, 0x57]))
    # send led command
    pp = ParaPacket(bytes([0x50, 0x00, 0x02, 0x03, 0x03, 0x04, 0x56]))
    print("<< {}".format(pp.get_oneliner()))
    ps.send(pp)

