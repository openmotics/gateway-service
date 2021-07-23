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

from collections import defaultdict

from gateway.apartment_controller import ApartmentController
from gateway.daemon_thread import DaemonThread
from gateway.delivery_controller import DeliveryController
from gateway.dto.box import ParcelBoxDTO, MailBoxDTO
from gateway.dto.doorbell import DoorbellDTO
from gateway.events import EsafeEvent
from gateway.pubsub import PubSub
from ioc import Inject, INJECTED, Injectable, Singleton

try:
    from rebus import Rebus
    from rebus import Utils
    from rebus import RebusComponent, RebusComponentEsafeLock, RebusComponentEsafeEightChannelOutput
    from rebus import EsafeBoxType
    from rebus import RebusException
except ImportError:
    pass

import logging
import time
logger = logging.getLogger(__name__)

if False:  # MYPY
    from typing import Dict, List, Optional


class EsafeController(object):
    @Inject
    def __init__(self, rebus_device=INJECTED, pubsub=INJECTED, apartment_controller=INJECTED, delivery_controller=INJECTED):
        # type: (str, PubSub, ApartmentController, DeliveryController) -> None
        logger.debug('Creating esafe controller')
        self.rebus_dev_file = rebus_device
        self.pub_sub = pubsub
        self.apartment_controller = apartment_controller
        self.delivery_controller = delivery_controller
        self.devices = {}  # type: Dict[int, RebusComponent]
        self.polling_thread = DaemonThread(name='eSafe status polling', target=self._get_esafe_status, interval=5, delay=5)
        self.lock_ids = []  # type: List[int]
        self.lock_status = defaultdict(lambda: False)  # type: Dict[int, bool]
        self.done_discovering = False

    ######################
    # Controller Functions
    ######################

    def start(self):
        self.rebus_device = Rebus(self.rebus_dev_file, power_off_on_del=False)
        self.toggle_rebus_power()
        self.discover_devices()

    def stop(self):
        self.polling_thread.stop()

    def _get_esafe_status(self):
        for lock_id in self.lock_ids:
            logger.debug("Getting lock status for rebus id: {}".format(lock_id))
            try:
                is_lock_open = self.devices[lock_id].get_lock_status()
            except RebusException:
                pass
            logger.debug("Status: {}".format(is_lock_open))
            if is_lock_open != self.lock_status[lock_id]:
                event = EsafeEvent(PubSub.EsafeTopics.LOCK, {'lock_id': lock_id, 'status': 'open' if is_lock_open else 'closed'})
                logger.debug("Sending event: {}".format(event))
                self.pub_sub.publish_esafe_event(PubSub.EsafeTopics.LOCK, event)
            self.lock_status[lock_id] = is_lock_open
            logger.debug("Updated lock status: {}".format(self.lock_status[lock_id]))
        time.sleep(1)

    # Mailbox Functions

    def get_mailboxes(self, rebus_id=None):
        # type: (Optional[int]) -> List[MailBoxDTO]
        logger.debug('Getting mailboxes')
        if not self.done_discovering:
            return []
        mailboxes = []

        if rebus_id is None:
            for device in self.devices.values():
                if isinstance(device, RebusComponentEsafeLock):
                    if device.type is EsafeBoxType.MAILBOX:
                        mailboxes.append(device)
        else:
            mailbox = self.devices.get(rebus_id)
            mailboxes = [mailbox] if mailbox is not None and mailbox.type is EsafeBoxType.MAILBOX else []
        return [self._rebus_mailbox_to_dto(mailbox) for mailbox in mailboxes]

    # ParcelBox Functions

    def get_parcelboxes(self, rebus_id=None, size=None, available=False):
        # type: (Optional[int], Optional[str], bool) -> List[ParcelBoxDTO]
        logger.debug('Getting parcelboxes, size: {}, rebus_id: {}'.format(size, rebus_id))
        if not self.done_discovering:
            return []
        parcelboxes = []  # type: List[RebusComponentEsafeLock]

        # if no rebus id is given, get all the parcelboxes
        if rebus_id is None:
            for device in self.devices.values():
                if isinstance(device, RebusComponentEsafeLock):
                    if device.type is EsafeBoxType.PARCELBOX:
                        parcelboxes.append(device)
        # else get the one parcelbox
        else:
            parcelbox = self.devices.get(rebus_id)
            logger.debug('Requesting specific parcelbox: {}'.format(parcelbox))
            parcelboxes = [parcelbox] if parcelbox is not None and parcelbox.type is EsafeBoxType.PARCELBOX else []

        # filter out the available packages
        if available is True:
            parcelboxes = [box for box in parcelboxes if self.delivery_controller.parcel_id_available(box.get_rebus_id())]

        # filter out the sizes
        if size is not None:
            size = size.lower()
            parcelboxes = [parcelbox for parcelbox in parcelboxes if parcelbox.size.name.lower() == size]

        return [self._rebus_parcelbox_to_dto(parcelbox) for parcelbox in parcelboxes]

    # Generic Functions (parcelbox and mailbox)

    def open_box(self, rebus_id):
        device = self.devices.get(rebus_id)
        if device is None or not isinstance(device, RebusComponentEsafeLock):
            raise ValueError('Trying to open rebus device that is not a parcelbox of mailbox')
        success = device.open_lock(blocking=True)
        if success:
            if device.type == EsafeBoxType.PARCELBOX:
                return self._rebus_parcelbox_to_dto(device, force_latest_status=True)
            elif device.type == EsafeBoxType.MAILBOX:
                return self._rebus_mailbox_to_dto(device, force_latest_status=True)
        return None

    # Doorbells

    def get_doorbells(self):
        doorbell_devices = [device for device in self.devices.values() if isinstance(device, RebusComponentEsafeEightChannelOutput)]
        doorbells = []
        for doorbell_device in doorbell_devices:
            rebus_id = doorbell_device.get_rebus_id()
            for i in range(8):
                doorbell_id = rebus_id + i + 1
                apartment = self.apartment_controller.load_apartment_by_doorbell_id(doorbell_id)
                doorbells.append(DoorbellDTO(id=doorbell_id, label=str(doorbell_id), apartment=apartment))
        return doorbells

    def ring_doorbell(self, doorbell_id):
        # type: (int) -> None
        doorbell_index = doorbell_id % 16
        rebus_id = doorbell_id - doorbell_index
        doorbell = self.devices.get(rebus_id)  # type: Optional[RebusComponentEsafeEightChannelOutput]
        if doorbell is None or not isinstance(doorbell, RebusComponentEsafeEightChannelOutput):
            raise ValueError('Cannot ring doorbell device, device does not exists or is non doorbell device')

        doorbell.set_output(doorbell_index, True)
        time.sleep(0.5)
        doorbell.set_output(doorbell_index, False)
        return

    ######################
    # HELPERS
    ######################

    def _rebus_parcelbox_to_dto(self, rebus_device, force_latest_status=False):
        # type: (RebusComponentEsafeLock, bool) -> ParcelBoxDTO
        _ = self  # suppress 'may be static' warning
        available = self.delivery_controller.parcel_id_available(rebus_device.get_rebus_id())
        if not force_latest_status:
            is_open = self.lock_status[rebus_device.get_rebus_id()]
        else:
            is_open = rebus_device.get_lock_status()
        return ParcelBoxDTO(id=rebus_device.get_rebus_id(), label=rebus_device.get_rebus_id(), height=rebus_device.height, width=rebus_device.width, size=rebus_device.size, available=available, is_open=is_open)

    def _rebus_mailbox_to_dto(self, rebus_device, force_latest_status=False):
        # type: (RebusComponentEsafeLock, bool) -> MailBoxDTO
        apartment_dto = self.apartment_controller.load_apartment_by_mailbox_id(rebus_device.get_rebus_id())
        if not force_latest_status:
            is_open = self.lock_status[rebus_device.get_rebus_id()]
        else:
            is_open = rebus_device.get_lock_status()
        return MailBoxDTO(id=rebus_device.get_rebus_id(), label=rebus_device.get_rebus_id(), apartment=apartment_dto, is_open=is_open)

    ######################
    # DISCOVERY
    ######################

    def discover_devices(self):
        logger.debug('Discovering rebus devices')
        self.rebus_device.discover(callback=self.discover_callback)

    def discover_callback(self):
        logger.debug('Discovering Callback called')
        self.devices = {device.get_rebus_id(): device for device in self.rebus_device.get_discovered_devices()}
        for dev_id, dev in self.devices.items():
            logger.debug('Discovered device: {}: {}'.format(dev_id, dev))
        self.done_discovering = True
        self.lock_ids = [lock_id for lock_id, lock in self.devices.items() if isinstance(lock, RebusComponentEsafeLock)]
        self.polling_thread.start()

    ######################
    # REBUS COMMANDS
    ######################

    def get_lock_status(self, lock_id):
        rebus_component = self.rebus_device.get_basic_component(Utils.convert_rebus_id_to_route(lock_id))
        rebus_lock = RebusComponentEsafeLock.from_component(rebus_component)
        status = rebus_lock.get_lock_status()
        return status

    def toggle_rebus_power(self, duration=0.5):
        self.rebus_device.power_off()
        time.sleep(duration)
        self.rebus_device.power_on()
        time.sleep(duration)

    ########################
    # VERIFICATION COMMANDS
    ########################

    def verify_device_exists(self, device_id):
        return device_id in self.devices
