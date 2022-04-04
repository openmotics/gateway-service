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
Module to work update a Core
"""

from __future__ import absolute_import
import logging
import os
import re
import time
from six.moves.queue import Queue, Empty

from intelhex import IntelHex
from ioc import Inject, INJECTED, Singleton, Injectable
from threading import Thread, Event as ThreadingEvent
from master.core.events import Event as MasterCoreEvent
from master.core.core_communicator import CoreCommunicator, BackgroundConsumer, CommunicationBlocker
from master.core.core_api import CoreAPI
from master.maintenance_communicator import MaintenanceCommunicator
from logs import Logs
from platform_utils import Hardware

if False:  # MYPY
    from typing import Optional, List
    from serial.serialposix import Serial

# Different name to reduce confusion between multiple used loggers
global_logger = logging.getLogger(__name__)


class BootloadException(RuntimeError):
    def __init__(self, message, fatal):
        self.fatal = fatal
        super(BootloadException, self).__init__(message)


@Injectable.named('core_updater')
@Singleton
class CoreUpdater(object):
    """
    This is a class holding tools to execute Core updates
    """

    BOOTLOADER_SERIAL_READ_TIMEOUT = 5.0
    POST_BOOTLOAD_DELAY = 2.0
    APPLICATION_STARTUP_TIMEOUT = 30.0
    POWER_CYCLE_DELAY = 2.0
    SLOW_WRITES = 50
    SLOW_WRITE_DELAY = 0.05
    BLOCK_WRITE_FAILURE_DELAY = 0.5
    BOOTLOADER_MARKER = 'DS30HexLoader'

    ENTER_BOOTLOADER_TRIES = 3
    BLOCK_WRITE_TRIES = 5

    @Inject
    def __init__(self, master_communicator=INJECTED, maintenance_communicator=INJECTED, cli_serial=INJECTED):
        # type: (CoreCommunicator, MaintenanceCommunicator, Serial) -> None
        self._master_communicator = master_communicator
        self._maintenance_communicator = maintenance_communicator
        self._cli_serial = cli_serial

        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
        )
        self._master_started = ThreadingEvent()
        self._master_started.set()
        self._read_queue = Queue()  # type: Queue[str]
        self._stop_reading = False
        self._communications_trace = []  # type: List[str]

    def _handle_event(self, data):
        core_event = MasterCoreEvent(data)
        if core_event.type == MasterCoreEvent.Types.SYSTEM:
            if core_event.data.get('type') == MasterCoreEvent.SystemEventTypes.STARTUP_COMPLETED:
                self._master_started.set()

    def update(self, hex_filename, version, ):
        # type: (str, str) -> None
        """ Flashes the content from an Intel HEX file to the Core """
        component_logger = Logs.get_update_logger('master_coreplus')
        component_logger.info('Updating Core')
        start_time = time.time()

        self._communications_trace = []
        if self._master_communicator is not None and not self._master_communicator.is_running():
            self._master_communicator.start()

        current_version = None  # type: Optional[str]
        try:
            current_version = self._master_communicator.do_command(command=CoreAPI.get_firmware_version(),
                                                                   fields={},
                                                                   bypass_blockers=[CommunicationBlocker.UPDATE])['version']
            component_logger.info('Current firmware version: {0}'.format(current_version))
        except Exception as ex:
            component_logger.warning('Could not load current firmware version: {0}'.format(ex))

        component_logger.info('Updating firmware from {0} to {1}'.format(current_version if current_version is not None else 'unknown',
                                                                         version if version is not None else 'unknown'))

        if self._master_communicator is not None and self._maintenance_communicator is not None:
            self._maintenance_communicator.stop()
            self._master_communicator.stop()

        if not os.path.exists(hex_filename):
            raise RuntimeError('The given path does not point to an existing file')
        _ = IntelHex(hex_filename)  # Using the IntelHex library to validate content validity
        with open(hex_filename, 'r') as hex_file:
            hex_lines = hex_file.readlines()
        amount_lines = len(hex_lines)

        self._stop_reading = False
        self._clear_read_queue()
        read_thread = Thread(name='cupdateread', target=self._read)
        read_thread.start()

        failure = False
        try:
            # Activate bootloader by a microcontrolle restart
            # This is tried `ENTER_BOOTLOADER_TRIES` times
            component_logger.info('Activating bootloader')
            enter_bootloader_tries = CoreUpdater.ENTER_BOOTLOADER_TRIES
            while True:
                try:
                    sub_delay = CoreUpdater.POWER_CYCLE_DELAY / 2
                    Hardware.cycle_gpio(
                        Hardware.CoreGPIO.MASTER_POWER,
                        [False, sub_delay, lambda: self._clear_read_queue(flush=True), sub_delay, True]
                    )
                    response = self._read_line()
                    if response is None or CoreUpdater.BOOTLOADER_MARKER not in response:
                        raise RuntimeError('Did not receive bootloader marker in time: {0}'.format(response))
                    try:
                        match = re.match(r'.*?V([0-9]+\.[0-9]+) .*?Library V([0-9]+\.[0-9]+\.[0-9]+).*', response)
                        if match is None:
                            raise RuntimeError()
                        bootloader_version, library_version = match.groups()
                        bootloader_version = '.'.join(str(int(i)) for i in bootloader_version.split('.'))  # Remove padding zeros
                        component_logger.info('Entered bootloader v{0} (library v{1})'.format(bootloader_version, library_version))
                    except Exception:
                        component_logger.warning('Could not parse bootloader version')
                    break  # The marker was received
                except Exception as ex:
                    enter_bootloader_tries -= 1
                    if enter_bootloader_tries == 0:
                        raise
                    component_logger.warning(str(ex))
                    component_logger.warning('Could not enter bootloader, trying again')

            self._verify_bootloader()
            component_logger.info('Bootloader active')

            # Start flashing the new firmware. This happens line by line and every line is tried
            # up to `BLOCK_WRITE_TRIES` times. As soon as there is a failure, the writes will be slowed
            # down for `SLOW_WRITES` times
            slow_counter = 0
            component_logger.info('Flashing contents of {0}'.format(os.path.basename(hex_filename)))
            component_logger.info('Flashing...')
            for index, line in enumerate(hex_lines):
                block_write_tries = CoreUpdater.BLOCK_WRITE_TRIES
                line_failed = False
                while True:
                    try:
                        self._clear_read_queue()
                        self._write_line(line=line)
                        response = self._read_line()
                        if response is None:
                            raise BootloadException('Did not receive an answer in time', fatal=False)
                        if CoreUpdater.BOOTLOADER_MARKER in response:
                            raise BootloadException('Bootloader restarted', fatal=True)
                        if response.startswith('nok'):
                            raise BootloadException('Received NOK: {0}'.format(response), fatal=False)
                        if response != 'ok':
                            raise BootloadException('Unexpected response: {0}'.format(response), fatal=False)
                        if line_failed:
                            component_logger.info('Flashing... Line {0}/{1} succeeded'.format(index + 1, amount_lines))
                        if slow_counter:
                            slow_counter -= 1
                        break
                    except RuntimeError as ex:
                        component_logger.warning('Flashing... Line {0}/{1} failed: {2}'.format(index + 1, amount_lines, ex))
                        slow_counter = CoreUpdater.SLOW_WRITES
                        if isinstance(ex, BootloadException):
                            if ex.fatal:
                                raise
                            time.sleep(CoreUpdater.BLOCK_WRITE_FAILURE_DELAY)
                        line_failed = True
                        block_write_tries -= 1
                        if block_write_tries == 0:
                            raise
                if slow_counter:
                    time.sleep(CoreUpdater.SLOW_WRITE_DELAY)
                if index % (amount_lines // 10) == 0 and index != 0:
                    component_logger.info('Flashing... {0}%'.format(index * 10 // (amount_lines // 10)))
            component_logger.info('Flashing... Done')
        except Exception:
            failure = True
            raise
        finally:
            self._stop_reading = True
            read_thread.join()
            if failure:
                # If there is a failure, write down the communications trace
                # after the read thread is stopped.
                with open('/tmp/bootloader.trace', 'w') as f:
                    f.write('\n'.join(self._communications_trace))

        component_logger.info('Post-flash power cycle')
        time.sleep(CoreUpdater.POST_BOOTLOAD_DELAY)

        def _prepare():
            if self._master_communicator is not None and self._maintenance_communicator is not None:
                self._maintenance_communicator.start()
                self._master_communicator.start()
            self._master_started.clear()

        sub_delay = CoreUpdater.POWER_CYCLE_DELAY / 2
        try:
            Hardware.cycle_gpio(
                Hardware.CoreGPIO.MASTER_POWER,
                [False, sub_delay, _prepare, sub_delay, True]
            )
        except Exception:
            component_logger.warning('Error on post-flash power cycle, powering on')
            Hardware.set_gpio(Hardware.CoreGPIO.MASTER_POWER, True)
            raise
        component_logger.info('Waiting for startup')
        if not self._master_started.wait(CoreUpdater.APPLICATION_STARTUP_TIMEOUT):
            raise RuntimeError('Core was not started after {0}s'.format(CoreUpdater.APPLICATION_STARTUP_TIMEOUT))
        component_logger.info('Startup complete')

        current_version = None
        try:
            current_version = self._master_communicator.do_command(command=CoreAPI.get_firmware_version(),
                                                                   fields={},
                                                                   bypass_blockers=[CommunicationBlocker.UPDATE])['version']
            component_logger.info('Post-update firmware version: {0}'.format(current_version))
        except Exception as ex:
            component_logger.warning('Could not load post-update firmware version: {0}'.format(ex))
        if version is not None and current_version != version:
            raise RuntimeError('Post-update firmware version {0} does not match expected {1}'.format(
                current_version if current_version is not None else 'unknown',
                version
            ))

        component_logger.info('Update completed. Took {0:.1f}s'.format(time.time() - start_time))

    def _verify_bootloader(self):  # type: () -> None
        while True:
            self._write_line('hi\n')
            response = self._read_line()
            if response is None:
                raise RuntimeError('Timeout while verifying bootloader')
            if CoreUpdater.BOOTLOADER_MARKER in response:
                continue
            if not response.startswith('hi;'):
                raise RuntimeError('Unexpected response while verifying bootloader: {0}'.format(response))
            return

    def _write_line(self, line):  # type: (str) -> None
        self._communications_trace.append('{0:.3f} > {1}'.format(time.time(), line.strip()))
        self._cli_serial.write(bytearray(ord(i) for i in line))

    def _read_line(self):
        try:
            return self._read_queue.get(timeout=CoreUpdater.BOOTLOADER_SERIAL_READ_TIMEOUT)
        except Empty:
            return None

    def _read(self):
        line_buffer = ''
        while not self._stop_reading:
            bytes_waiting = self._cli_serial.inWaiting()
            if bytes_waiting:
                try:
                    line_buffer += bytearray(self._cli_serial.read(bytes_waiting)).decode()
                except UnicodeDecodeError:
                    pass  # Is expected when (re)booting
            while '\n' in line_buffer:
                message, line_buffer = line_buffer.split('\n', 1)
                self._communications_trace.append('{0:.3f} < {1}'.format(time.time(), message))
                if message[0] != '#':
                    self._read_queue.put(message)
            if not bytes_waiting:
                time.sleep(0.01)

    def _clear_read_queue(self, flush=False):
        try:
            if flush:
                self._cli_serial.reset_input_buffer()
                self._cli_serial.reset_output_buffer()
            while True:
                self._read_queue.get(False)
        except Empty:
            pass
