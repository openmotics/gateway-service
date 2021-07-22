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
from threading import Thread
from rfid.idtronic_M890.para.para_packet import ParaPacket

logger = logging.getLogger(__name__)


class ParaSender(object):
    def __init__(self, serial_endpoint, callback=None):
        self.serial_endpoint = serial_endpoint
        self.callback = callback
        self.reader_thread = Thread(target=self.reader_runner, name='reader-thread', daemon=False)
        self.is_running = False
        self.device_fd = os.open(self.serial_endpoint, os.O_RDWR)
        os.set_blocking(self.device_fd, False)
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
        os.close(self.device_fd)

    def reader_runner(self):
        packet = ParaPacket()
        # use an epoll instance to get notified when there is data and keep an timeout
        # to be able to exit hte while loop
        ep = select.epoll(1)
        ep.register(self.device_fd, select.EPOLLIN)
        while self.is_running:
            try:
                # poll the file descriptor with a timeout of 0.25s
                for _, _ in ep.poll(0.25):
                    byte = os.read(self.device_fd, 1)
                    if byte == b'':
                        break
                    if not packet.is_complete():
                        packet.append_byte(byte)
                    else:
                        raise Exception("received a new byte for an already full package: 0x{}".format(byte.hex()))
                    if packet.is_complete():
                        if packet.crc_check():
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

            print("sending:  {}".format(para_packet.get_oneliner()))
            res = os.write(self.device_fd, para_packet.serialize())
            if res != len(para_packet):
                raise Exception('Could not write package to reader, send length does not match length of package: {}'.format(para_packet))
        except Exception as ex:
            print("Could not send the para-packet: {}".format(ex))


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

