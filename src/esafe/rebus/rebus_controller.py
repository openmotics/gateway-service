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

from multiprocessing import Lock

from esafe.rebus.abstract_rebus_controller import RebusControllerInterface
from gateway.apartment_controller import ApartmentController
from gateway.daemon_thread import DaemonThread
from gateway.delivery_controller import DeliveryController
from gateway.dto.box import ParcelBoxDTO, MailBoxDTO
from gateway.dto.doorbell import DoorbellDTO
from gateway.events import EsafeEvent
from gateway.exceptions import ServiceUnavailableException
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
lock_status_logger = logging.getLogger(__name__ + ".lock-status")

if False:  # MYPY
    from typing import Dict, List, Optional


class RebusController(RebusControllerInterface):
    @Inject
    def __init__(self, rebus_device=INJECTED, pubsub=INJECTED, apartment_controller=INJECTED, delivery_controller=INJECTED):
        # type: (str, PubSub, ApartmentController, DeliveryController) -> None
        logger.debug('Creating esafe controller')
        self.rebus_dev_file = rebus_device
        self._rebus_device = None
        self.pub_sub = pubsub
        self.apartment_controller = apartment_controller
        self.delivery_controller = delivery_controller
        self.devices = {}  # type: Dict[int, RebusComponent]
        self.polling_thread = DaemonThread(name='eSafe status polling', target=self._get_esafe_status, interval=1, delay=5)
        self.lock_ids = []  # type: List[int]
        self.lock_status = defaultdict(lambda: False)  # type: Dict[int, bool]
        self.done_discovering = False
        self.rebus_lock = Lock()

    @property
    def rebus_device(self):
        # type: () -> Rebus
        if self._rebus_device is not None:
            return self._rebus_device
        raise ServiceUnavailableException('Rebus device does not exists, first start the rebus controller to create a device')

    ######################
    # Controller Functions
    ######################

    def start(self):
        logger.debug('Starting eSafe controller')
        logger.debug(' -> Creating eSafe device: {}'.format(self.rebus_dev_file))
        self._rebus_device = Rebus(self.rebus_dev_file, power_off_on_del=True)
        logger.debug(' -> Toggle power')
        self.toggle_rebus_power()
        logger.debug(' -> Discover devices')
        self.discover_devices()

    def stop(self):
        self.polling_thread.stop()

    def _get_esafe_status(self):
        for lock_id in self.lock_ids:
            try:
                is_lock_open = self.devices[lock_id].get_lock_status()
            except RebusException as rebus_ex:
                lock_status_logger.error("could not get lock status of lock: {}: Exception: {}".format(lock_id, rebus_ex))
                continue
            if is_lock_open != self.lock_status[lock_id]:
                event = EsafeEvent(EsafeEvent.Types.LOCK_CHANGE, {'lock_id': lock_id, 'status': 'open' if is_lock_open else 'closed'})
                lock_status_logger.debug("lock status changed, Sending event: {}".format(event))
                self.pub_sub.publish_esafe_event(PubSub.EsafeTopics.LOCK, event)
            self.lock_status[lock_id] = is_lock_open
            lock_status_logger.debug("Updated lock [{}] to status: {}".format(lock_id, 'open' if self.lock_status[lock_id] else 'closed'))

    # Mailbox Functions

    def get_mailboxes(self, rebus_id=None):
        # type: (Optional[int]) -> List[MailBoxDTO]
        logger.debug('Getting mailboxes, rebus_id: {}'.format(rebus_id))
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
        # type: (Optional[int], Optional[str], Optional[bool]) -> List[ParcelBoxDTO]
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

        # filter out the sizes
        if size is not None:
            size = size.lower()
            parcelboxes = [parcelbox for parcelbox in parcelboxes if parcelbox.size.name.lower() == size]

        parcelboxes_dto = [self._rebus_parcelbox_to_dto(parcelbox) for parcelbox in parcelboxes]

        # filter out the available packages
        if available is True:
            parcelboxes_dto = [box for box in parcelboxes_dto if box.available]

        return parcelboxes_dto

    # Generic Functions (parcelbox and mailbox)

    def open_box(self, rebus_id):
        logger.info("Opening lock with rebus_id: {}".format(rebus_id))
        device = self.devices.get(rebus_id)
        if device is None or not isinstance(device, RebusComponentEsafeLock):
            raise ValueError('Trying to open rebus device that is not a parcelbox of mailbox')
        with self.rebus_lock:
            success = device.open_lock(blocking=True)
        if success:
            self.lock_status[rebus_id] = True
            event = EsafeEvent(EsafeEvent.Types.LOCK_CHANGE, {'lock_id': rebus_id, 'status': 'open'})
            logger.debug("Sending event: {}".format(event))
            self.pub_sub.publish_esafe_event(PubSub.EsafeTopics.LOCK, event)
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

        with self.rebus_lock:
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
            is_open = self.get_lock_status(rebus_device.get_rebus_id())
        return ParcelBoxDTO(id=rebus_device.get_rebus_id(), label=rebus_device.get_rebus_id(), height=rebus_device.height, width=rebus_device.width, size=rebus_device.size, available=available, is_open=is_open)

    def _rebus_mailbox_to_dto(self, rebus_device, force_latest_status=False):
        # type: (RebusComponentEsafeLock, bool) -> MailBoxDTO
        apartment_dto = self.apartment_controller.load_apartment_by_mailbox_id(rebus_device.get_rebus_id())
        if not force_latest_status:
            is_open = self.lock_status[rebus_device.get_rebus_id()]
        else:
            is_open = self.get_lock_status(rebus_device.get_rebus_id())
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
        self.log_discovered_devices()
        self.polling_thread.start()

    def log_discovered_devices(self):
        logger.info("Rebus discovered devices:")
        for dev_id, device in self.devices.items():
            logger.info(" * {} @ {}".format(dev_id, device.__class__.__name__))

    ######################
    # REBUS COMMANDS
    ######################

    def get_lock_status(self, lock_id):
        if lock_id not in self.devices:
            raise ValueError("Cannot get lock status: Lock_id: '{}' is not detected".format(lock_id))
        device = self.devices[lock_id]
        if not isinstance(device, RebusComponentEsafeLock):
            raise ValueError("Cannot get lock status: device with id: '{}' is not a lock".format(lock_id))
        lock_status = False
        for _ in range(5):
            try:
                lock_status = device.get_lock_status()
                break
            except RebusException:
                time.sleep(0.1)
                continue
        return lock_status

    def toggle_rebus_power(self, duration=0.5):
        self.rebus_device.power_off()
        time.sleep(duration)
        self.rebus_device.power_on()
        time.sleep(duration)

    ########################
    # VERIFICATION COMMANDS
    ########################

    def verify_device_exists(self, device_id):
        if (device_id % 16) != 0:
            # if the device id is not a multiple of 16, then it could be a doorbell
            doorbells = self.get_doorbells()
            for doorbell in doorbells:
                if device_id == doorbell.id:
                    return True
            return False
        return device_id in self.devices
