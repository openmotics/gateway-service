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
Module for the frontpanel
"""
from __future__ import absolute_import
import logging
import time
from ioc import INJECTED, Inject
from bus.om_bus_client import OMBusEvents
from platform_utils import Hardware
from gateway.daemon_thread import DaemonThread
from gateway.uart_controller import UARTController
from gateway.enums import SerialPorts

if False:  # MYPY
    from typing import Optional
    from gateway.hal.master_controller import MasterController
    from gateway.energy_module_controller import EnergyModuleController

logger = logging.getLogger(__name__)


class FrontpanelController(object):

    INDICATE_TIMEOUT = 30
    AUTH_MODE_PRESS_DURATION = 5
    AUTH_MODE_TIMEOUT = 60
    BOARD_TYPE = Hardware.get_board_type()
    MAIN_INTERFACE = Hardware.get_main_interface()

    @Inject
    def __init__(self, master_controller=INJECTED, energy_module_controller=INJECTED, uart_controller=INJECTED):
        # type: (MasterController, EnergyModuleController, UARTController) -> None
        self._master_controller = master_controller
        self._energy_module_controller = energy_module_controller
        self._uart_controller = uart_controller
        self._network_carrier = None
        self._network_activity = None
        self._network_activity_scan_counter = 0
        self._network_bytes = 0
        self._check_network_activity_thread = None
        self._authorized_mode = False
        self._authorized_mode_timeout = 0
        self._indicate = False
        self._indicate_timeout = 0
        self._master_stats = 0, 0
        self._energy_stats = 0, 0

    @property
    def authorized_mode(self):
        # return Platform.get_platform() == Platform.Type.CORE_PLUS or self._authorized_mode  # Needed to validate Brain+ with no front panel attached
        return self._authorized_mode

    def event_receiver(self, event, payload):
        if event == OMBusEvents.CLOUD_REACHABLE:
            self._report_cloud_reachable(payload)
        elif event == OMBusEvents.VPN_OPEN:
            self._report_vpn_open(payload)
        elif event == OMBusEvents.CONNECTIVITY:
            self._report_connectivity(payload)

    def start(self):
        self._check_network_activity_thread = DaemonThread(name='frontpanel',
                                                           target=self._do_frontpanel_tasks,
                                                           interval=0.5)
        self._check_network_activity_thread.start()

    def stop(self):
        if self._check_network_activity_thread is not None:
            self._check_network_activity_thread.stop()

    def _report_carrier(self, carrier):
        # type: (bool) -> None
        raise NotImplementedError()

    def _report_connectivity(self, connectivity):
        # type: (bool) -> None
        raise NotImplementedError()

    def _report_network_activity(self, activity):
        # type: (bool) -> None
        raise NotImplementedError()

    def _report_serial_activity(self, serial_port, activity):
        # type: (str, Optional[bool]) -> None
        raise NotImplementedError()

    def _report_cloud_reachable(self, reachable):
        # type: (bool) -> None
        raise NotImplementedError()

    def _report_vpn_open(self, vpn_open):
        # type: (bool) -> None
        raise NotImplementedError()

    def indicate(self):
        self._indicate = True
        self._indicate_timeout = time.time() + FrontpanelController.INDICATE_TIMEOUT

    def _do_frontpanel_tasks(self):
        # Check network activity
        try:
            with open('/sys/class/net/{0}/carrier'.format(FrontpanelController.MAIN_INTERFACE), 'r') as fh_up:
                line = fh_up.read()
            carrier = int(line) == 1
            carrier_changed = self._network_carrier != carrier
            if carrier_changed:
                self._network_carrier = carrier
                self._report_carrier(carrier)

            # Check network activity every second, or if the carrier changed
            if self._network_activity_scan_counter >= 9 or carrier_changed:
                self._network_activity_scan_counter = 0
                network_activity = False
                if self._network_carrier:  # There's no activity when there's no carrier
                    with open('/proc/net/dev', 'r') as fh_stat:
                        for line in fh_stat.readlines():
                            if FrontpanelController.MAIN_INTERFACE not in line:
                                continue
                            received, transmitted = 0, 0
                            parts = line.split()
                            if len(parts) == 17:
                                received = parts[1]
                                transmitted = parts[9]
                            elif len(parts) == 16:
                                (_, received) = tuple(parts[0].split(':'))
                                transmitted = parts[8]
                            new_bytes = received + transmitted
                            if self._network_bytes != new_bytes:
                                self._network_bytes = new_bytes
                                network_activity = True
                            else:
                                network_activity = False
                if self._network_activity != network_activity:
                    self._report_network_activity(network_activity)
                self._network_activity = network_activity
            self._network_activity_scan_counter += 1
        except Exception as exception:
            logger.error('Error while checking network activity: {0}'.format(exception))

        # Monitor serial activity
        try:
            stats = self._master_controller.get_communication_statistics()
            new_master_stats = (stats['bytes_read'], stats['bytes_written'])
            activity = self._master_stats[0] != new_master_stats[0] or self._master_stats[1] != new_master_stats[1]
            self._report_serial_activity(SerialPorts.MASTER_API, activity)
            self._master_stats = new_master_stats

            stats = self._energy_module_controller.get_communication_statistics()
            new_energy_stats = (stats['bytes_read'], stats['bytes_written'])
            activity = self._energy_stats[0] != new_energy_stats[0] or self._energy_stats[1] != new_energy_stats[1]
            self._report_serial_activity(SerialPorts.ENERGY, activity)
            self._energy_stats = new_energy_stats

            p1_activity = None  # type: Optional[bool]
            exp_activity = None  # type: Optional[bool]
            if self._uart_controller is not None:
                if self._uart_controller.mode in [UARTController.Mode.MODBUS]:
                    exp_activity = self._uart_controller.activity
                elif self._uart_controller.mode in [UARTController.Mode.P1]:
                    p1_activity = self._uart_controller.activity
            self._report_serial_activity(SerialPorts.P1, p1_activity)
            self._report_serial_activity(SerialPorts.EXPANSION, exp_activity)
        except Exception as exception:
            logger.error('Error while checking serial activity: {0}'.format(exception))

        # Clear indicate timeout
        if time.time() > self._indicate_timeout:
            self._indicate = False
