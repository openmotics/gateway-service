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
eSafe controller will communicate over rebus with the esafe hardware
"""

from gateway.daemon_thread import DaemonThread
from gateway.pubsub import PubSub
from ioc import Inject, INJECTED

try:
    from rebus import Rebus
    from rebus import Utils
    from rebus import RebusComponent, RebusComponentEsafeLock, RebusComponentEsafeEightChannelOutput
    from rebus import EsafeBoxType
except ImportError:
    pass

import logging
import time
logger = logging.getLogger(__name__)

if False:  # MYPY
    from typing import Dict, List


class EsafeController(object):
    @Inject
    def __init__(self, rebus_port=INJECTED, pub_sub=INJECTED):
        # type: (str, PubSub) -> None
        self.rebus_device = Rebus(rebus_port, power_off_on_del=False)
        self.pub_sub = pub_sub
        self.devices = {}  # type: Dict[int, RebusComponent]
        self.polling_thread = DaemonThread(name='eSafe status polling', target=self._get_esafe_status, interval=5, delay=5)
        self.open_locks = []  # type: List[int]

    ######################
    # Controller Functions
    ######################

    def start(self):
        self.polling_thread.start()

    def stop(self):
        self.polling_thread.stop()

    def _get_esafe_status(self):
        for lock_id in self.open_locks:
            is_lock_open = self.get_lock_status(lock_id)
            if not is_lock_open:
                # TODO: Raise event that lock has just closed
                pass
        time.sleep(0.5)

    def get_mailboxes(self):
        mailboxes = []
        for id, device in self.devices.items():
            if isinstance(device, RebusComponentEsafeLock):
                if device.type is EsafeBoxType.MAILBOX:
                    mailboxes.append(device)
        return mailboxes

    def get_parcelboxes(self):
        parcelboxes = []
        for id, device in self.devices.items():
            if isinstance(device, RebusComponentEsafeLock):
                if device.type is EsafeBoxType.PARCELBOX:
                    parcelboxes.append(device)
        return parcelboxes


    ######################
    # DISCOVERY
    ######################

    def discover_devices(self):
        self.rebus_device.discover(callback=self.discover_callback)

    def discover_callback(self):
        self.devices = {device: device for device in self.rebus_device.get_discovered_devices()}

    ######################
    # REBUS COMMANDS
    ######################

    def get_lock_status(self, lock_id):
        rebus_component = self.rebus_device.get_basic_component(Utils.convert_rebus_id_to_route(lock_id))
        rebus_lock = RebusComponentEsafeLock.from_component(rebus_component)
        status = rebus_lock.get_lock_status()
        return status

    def open_lock(self, lock_id):
        rebus_component = self.rebus_device.get_basic_component(Utils.convert_rebus_id_to_route(lock_id))
        rebus_lock = RebusComponentEsafeLock.from_component(rebus_component)
        rebus_lock.open_lock(blocking=False)

    def ring_doorbell(self, doorbell_id):
        doorbell_output_id = doorbell_id % 16
        rebus_device_id = doorbell_id - doorbell_output_id
        rebus_component = self.rebus_device.get_basic_component(Utils.convert_rebus_id_to_route(rebus_device_id))
        doorbell_component = RebusComponentEsafeEightChannelOutput.from_component(rebus_component)
        doorbell_component.set_output()

    def toggle_rebus_power(self, duration=0.5):
        self.rebus_device.power_off()
        time.sleep(duration)
        self.rebus_device.power_on()

    ########################
    # VERIFICATION COMMANDS
    ########################

    def verify_device_exists(self, device_id):
        return device_id in self.devices
