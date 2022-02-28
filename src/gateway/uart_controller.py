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
UART (and other serial stuff) BLL
"""
from __future__ import absolute_import
import fcntl  # TODO: Seems python >= 3.9 doesn't have fcntl anymore
import logging
import struct
import time
from functools import wraps
from threading import Lock
from minimalmodbus import Instrument
from platform_utils import Hardware

if False:  # MYPY
    from typing import Dict, Union

logger = logging.getLogger(__name__)


def require_mode(mode):
    def wrapper(func):
        @wraps(func)
        def wrapped(self_, *args, **kwargs):
            if self_.mode != mode:
                raise RuntimeError('The function {0} is not available in mode {1}'.format(func.__name__, self_.mode))
            return func(self_,  *args, **kwargs)
        return wrapped
    return wrapper


class UARTController(object):

    # TODO:
    #  * Introduce some `create_client` call
    #    * Allows to create a reference between a serial port and a consumer and thus sharing the port
    #    * Allows a client (the first one?) to changing various serial port settings (e.g. baudrate)

    class RS485Settings(object):
        TIOCSRS485 = 0x542F  # This ioctl is used to enable/disable RS485 mode from user-space
        TIOCGRS485 = 0x542E  # This ioctl is used to get RS485 mode from kernel-space (i.e., driver) to user-space.
        SER_RS485_ENABLED = 0b00000001
        SER_RS485_RTS_ON_SEND = 0b00000010
        SER_RS485_RTS_AFTER_SEND = 0b00000100
        SER_RS485_RX_DURING_TX = 0b00010000

        def __init__(self,
                     loopback=False,
                     rts_level_for_tx=False,
                     rts_level_for_rx=False,
                     delay_before_tx=None,
                     delay_before_rx=None):
            self.loopback = loopback
            self.rts_level_for_tx = rts_level_for_tx
            self.rts_level_for_rx = rts_level_for_rx
            self.delay_before_tx = delay_before_tx
            self.delay_before_rx = delay_before_rx

    class Mode(object):
        NONE = 'NONE'
        P1 = 'P1'
        MODBUS = 'MODBUS'

    MODES = [Mode.NONE, Mode.P1, Mode.MODBUS]
    SUPPORTED_MODES = [Mode.NONE, Mode.MODBUS]

    def __init__(self, uart_port):
        self._mode = UARTController.Mode.NONE
        self._running = False
        self._uart_port = uart_port
        self._last_activity = 0.0
        # Modbus fields
        self._modbus_clients = {}  # type: Dict[int, Instrument]
        self._modbus_lock = Lock()

    @property
    def mode(self):
        return self._mode

    @property
    def activity(self):
        return self._last_activity >= time.time() - 5.0

    def start(self):
        if self._running:
            return
        # TODO: Start, as soon as there's a mode to start
        self._running = True

    def stop(self):
        if not self._running:
            return
        # TODO: Stop, as soon as there's a mode to stop
        self._running = False

    def set_mode(self, mode):
        if mode not in UARTController.SUPPORTED_MODES:
            raise RuntimeError('Mode {0} not (yet) supported'.format(mode))
        was_running = self._running
        self.stop()
        if self._mode == UARTController.Mode.MODBUS:
            Hardware.enable_extension_rs485_port()
        self._mode = mode
        if was_running:
            self.start()

    @staticmethod
    def _set_rs485_mode(serial_device, rs485_settings):
        # Slightly modified code from inside serialposix
        buffer = [0] * 8  # Flags, delay TX, delay RX, padding
        try:
            fcntl.ioctl(serial_device.fileno(),
                        UARTController.RS485Settings.TIOCGRS485,
                        struct.pack('hhhhhhhh', *buffer))
            buffer[0] |= UARTController.RS485Settings.SER_RS485_ENABLED
            if rs485_settings is not None:
                if rs485_settings.loopback:
                    buffer[0] |= UARTController.RS485Settings.SER_RS485_RX_DURING_TX
                else:
                    buffer[0] &= ~UARTController.RS485Settings.SER_RS485_RX_DURING_TX
                if rs485_settings.rts_level_for_tx:
                    buffer[0] |= UARTController.RS485Settings.SER_RS485_RTS_ON_SEND
                else:
                    buffer[0] &= ~UARTController.RS485Settings.SER_RS485_RTS_ON_SEND
                if rs485_settings.rts_level_for_rx:
                    buffer[0] |= UARTController.RS485Settings.SER_RS485_RTS_AFTER_SEND
                else:
                    buffer[0] &= ~UARTController.RS485Settings.SER_RS485_RTS_AFTER_SEND
                if rs485_settings.delay_before_tx is not None:
                    buffer[1] = int(rs485_settings.delay_before_tx * 1000)
                if rs485_settings.delay_before_rx is not None:
                    buffer[2] = int(rs485_settings.delay_before_rx * 1000)
            else:
                buffer[0] = 0  # clear UARTController.SER_RS485_ENABLED
            fcntl.ioctl(serial_device.fileno(),
                        UARTController.RS485Settings.TIOCSRS485,
                        struct.pack('hhhhhhhh', *buffer))
        except IOError as ex:
            raise ValueError('Failed to set RS485 mode: {0}'.format(ex))

    # Modbus

    def _create_modbus_client(self, slaveaddress):  # type: (int) -> Instrument
        client = Instrument(port=self._uart_port,
                            slaveaddress=slaveaddress)
        serial_device = client.serial
        serial_device.baudrate = 9600
        UARTController._set_rs485_mode(serial_device=serial_device,
                                       rs485_settings=UARTController.RS485Settings(rts_level_for_tx=True))
        return client

    def _get_modbus_client(self, slaveaddress):  # type: (int) -> Instrument
        if slaveaddress not in self._modbus_clients:
            self._modbus_clients[slaveaddress] = self._create_modbus_client(slaveaddress)
        return self._modbus_clients[slaveaddress]

    @require_mode(Mode.MODBUS)
    def write_register(self, slaveaddress, registeraddress, value, number_of_decimals=0, functioncode=16, signed=False):
        # type: (int, int, Union[float, int], int, int, bool) -> None
        with self._modbus_lock:
            client = self._get_modbus_client(slaveaddress)
            try:
                if isinstance(value, float):
                    client.write_register(registeraddress=registeraddress,
                                          value=value,
                                          number_of_decimals=number_of_decimals,
                                          functioncode=functioncode,
                                          signed=signed)
            except Exception as ex:
                logger.warning('Modbus write error: {0}'.format(ex))
                time.sleep(0.1)
                if isinstance(value, float):
                    client.write_register(registeraddress=registeraddress,
                                          value=value,
                                          number_of_decimals=number_of_decimals,
                                          functioncode=functioncode,
                                          signed=signed)
            self._last_activity = time.time()

    @require_mode(Mode.MODBUS)
    def read_register(self, slaveaddress, registeraddress, number_of_decimals=0, functioncode=3, signed=False):
        # type: (int, int, int, int, bool) -> Union[float, int, list]
        with self._modbus_lock:
            client = self._get_modbus_client(slaveaddress)
            try:
                return client.read_register(registeraddress=registeraddress,
                                            number_of_decimals=number_of_decimals,
                                            functioncode=functioncode,
                                            signed=signed)
            except Exception as ex:
                logger.warning('Modbus read error: {0}'.format(ex))
                time.sleep(0.1)
                return client.read_register(registeraddress=registeraddress,
                                            number_of_decimals=number_of_decimals,
                                            functioncode=functioncode,
                                            signed=signed)
            self._last_activity = time.time()
