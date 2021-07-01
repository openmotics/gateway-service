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

from gateway.apartment_controller import ApartmentController
from gateway.daemon_thread import DaemonThread
from gateway.delivery_controller import DeliveryController
from gateway.dto.box import ParcelBoxDTO, MailBoxDTO
from gateway.pubsub import PubSub
from ioc import Inject, INJECTED, Injectable, Singleton

from rebus import Rebus
from rebus import Utils
from rebus import RebusComponent, RebusComponentEsafeLock, RebusComponentEsafeEightChannelOutput
from rebus import EsafeBoxType

import logging
import time
logger = logging.getLogger(__name__)

if False:  # MYPY
    from typing import Dict, List, Optional


class EsafeController(object):
    @Inject
    def __init__(self, rebus_device=INJECTED, pubsub=INJECTED, apartment_controller=INJECTED):
        # type: (str, PubSub, ApartmentController) -> None
        logger.info('Creating esafe controller')
        self.rebus_device = Rebus(rebus_device, power_off_on_del=False)
        self.rebus_device.power_on()
        time.sleep(0.2)
        logger.info('Created rebus device')
        self.pub_sub = pubsub
        self.apartment_controller = apartment_controller
        self.devices = {}  # type: Dict[int, RebusComponent]
        self.polling_thread = DaemonThread(name='eSafe status polling', target=self._get_esafe_status, interval=5, delay=5)
        self.open_locks = []  # type: List[int]
        self.done_discovering = False
        logger.info('Starting up discovery')
        self.discover_devices()

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

    def get_mailboxes(self, rebus_id=None):
        # type: (Optional[int]) -> list[MailBoxDTO]
        logger.info('Getting mailboxes')
        if not self.done_discovering:
            return []
        mailboxes = []

        if rebus_id is None:
            for rebus_id, device in self.devices.items():
                if isinstance(device, RebusComponentEsafeLock):
                    if device.type is EsafeBoxType.MAILBOX:
                        mailboxes.append(device)
        else:
            mailbox = self.devices.get(rebus_id)
            mailboxes = [mailbox] if mailbox is not None and mailbox.type is EsafeBoxType.MAILBOX else []
        return [self._rebus_mailbox_to_dto(mailbox) for mailbox in mailboxes]

    def get_parcelboxes(self, size=None, rebus_id=None):
        # type: (Optional[str], Optional[int]) -> List[ParcelBoxDTO]
        logger.info('Getting parcelboxes, size: {}, rebus_id: {}'.format(size, rebus_id))
        if not self.done_discovering:
            return []
        parcelboxes = []  # type: List[RebusComponentEsafeLock]

        # if no rebus id is given, get all the parcelboxes
        if rebus_id is None:
            for _, device in self.devices.items():
                if isinstance(device, RebusComponentEsafeLock):
                    if device.type is EsafeBoxType.PARCELBOX:
                        parcelboxes.append(device)
        # else get the one parcelbox
        else:
            parcelbox = self.devices.get(rebus_id)
            logger.info('Requesting specific parcelbox: {}'.format(parcelbox))
            parcelboxes = [parcelbox] if parcelbox is not None and parcelbox.type is EsafeBoxType.PARCELBOX else []

        # filter out the sizes
        if size is not None:
            size = size.lower()
            parcelboxes = [parcelbox for parcelbox in parcelboxes if parcelbox.size.value.lower() == size]

        return [self._rebus_parcelbox_to_dto(mailbox) for mailbox in parcelboxes]

    ######################
    # HELPERS
    ######################

    def _rebus_parcelbox_to_dto(self, rebus_device):
        # type: (RebusComponentEsafeLock) -> ParcelBoxDTO
        _ = self  # suppress 'may be static' warning
        return ParcelBoxDTO(id=rebus_device.get_rebus_id(), label=rebus_device.get_rebus_id(), height=rebus_device.height, width=rebus_device.width, size=rebus_device.size)

    def _rebus_mailbox_to_dto(self, rebus_device):
        # type: (RebusComponentEsafeLock) -> MailBoxDTO
        apartment_dto = self.apartment_controller.load_apartment_by_mailbox_id(rebus_device.get_rebus_id())
        return MailBoxDTO(id=rebus_device.get_rebus_id(), label=rebus_device.get_rebus_id(), apartment=apartment_dto)

    ######################
    # DISCOVERY
    ######################

    def discover_devices(self):
        logger.info('Discovering rebus devices')
        self.rebus_device.discover(callback=self.discover_callback)

    def discover_callback(self):
        logger.info('Discovering Callback called')
        self.devices = {device.get_rebus_id(): device for device in self.rebus_device.get_discovered_devices()}
        for dev_id, dev in self.devices.items():
            logger.info('Discovered device: {}: {}'.format(dev_id, dev))
        logger.info(self.devices.get(64))
        self.done_discovering = True

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
