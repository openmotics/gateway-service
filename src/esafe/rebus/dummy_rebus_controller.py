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
import json
from collections import defaultdict

from esafe.rebus.abstract_rebus_controller import RebusControllerInterface
from gateway.apartment_controller import ApartmentController
from gateway.daemon_thread import DaemonThread
from gateway.delivery_controller import DeliveryController
from gateway.dto.box import ParcelBoxDTO, MailBoxDTO
from gateway.dto.doorbell import DoorbellDTO
from gateway.events import EsafeEvent
from gateway.pubsub import PubSub
from ioc import Inject, INJECTED, Injectable, Singleton

import logging
import os
logger = logging.getLogger(__name__)

if False:  # MYPY
    from typing import Dict, List, Optional


# define a custom rebus exception type
class RebusException(Exception):
    pass


class DummyRebusController(RebusControllerInterface):
    @Inject
    def __init__(self, pubsub=INJECTED, apartment_controller=INJECTED, delivery_controller=INJECTED):
        # type: (PubSub, ApartmentController, DeliveryController) -> None
        logger.info('Creating dummy rebus controller')
        self.pub_sub = pubsub
        self.apartment_controller = apartment_controller
        self.delivery_controller = delivery_controller
        self.mailboxes = {}  # type: Dict[int, MailBoxDTO]
        self.parcelboxes = {}  # type: Dict[int, ParcelBoxDTO]
        self.doorbells = {}  # type: Dict[int, DoorbellDTO]
        self._lock_status = {}  # type: Dict[int, int]  # int counter to check how many ticks it stays open
        self._lock_open_ticks = 2
        self.lock_tick_thread = DaemonThread(name='fake lock tick', target=self._lock_close_tick_check, interval=2, delay=2)

        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.dummy_rebus_json_file = os.path.join(self.current_path, "dummy_rebus_devices.json")
        logger.info("Loading rebus info from {}".format(self.dummy_rebus_json_file))

    ######################
    # Controller Functions
    ######################

    def start(self):
        logger.info('Starting eSafe controller')
        logger.info(' -> Fake Discover devices')
        self.discover_devices()

    def stop(self):
        pass
        # self.polling_thread.stop()

    def _send_lock_event(self, lock_id, status):
        event = EsafeEvent(EsafeEvent.Types.LOCK_CHANGE, {'lock_id': lock_id, 'status': 'open' if status else 'closed'})
        logger.debug("Sending event: {}".format(event))
        self.pub_sub.publish_esafe_event(PubSub.EsafeTopics.LOCK, event)

    def _lock_close_tick_check(self):
        for lock_id in list(self._lock_status.keys()):
            self._lock_status[lock_id] += 1
            if self._lock_status[lock_id] > self._lock_open_ticks:
                logger.info("Sending lock event, lock is closing")
                self._close_box(lock_id)
                del self._lock_status[lock_id]

    # Mailbox Functions

    def get_mailboxes(self, rebus_id=None):
        # type: (Optional[int]) -> List[MailBoxDTO]
        logger.debug('Getting mailboxes')
        if rebus_id is None:
            return list(self.mailboxes.values())
        return [self.mailboxes[rebus_id]]

    # ParcelBox Functions

    def get_parcelboxes(self, rebus_id=None, size=None, available=False):
        # type: (Optional[int], Optional[str], Optional[bool]) -> List[ParcelBoxDTO]
        logger.debug('Getting parcelboxes, size: {}, rebus_id: {}'.format(size, rebus_id))
        # if no rebus id is given, get all the parcelboxes
        parcelboxes = []
        if rebus_id is None:
            parcelboxes = list(self.parcelboxes.values())
        # else get the one parcelbox
        else:
            parcelboxes = list([self.parcelboxes[rebus_id]])

        # filter out the sizes
        if size is not None:
            size = size.lower()
            parcelboxes = [parcelbox for parcelbox in parcelboxes if parcelbox.size.name.lower() == size]

        # filter out the available packages
        if available is True:
            parcelboxes = [box for box in parcelboxes if box.available]

        return parcelboxes

    # Generic Functions (parcelbox and mailbox)

    def get_lock(self, rebus_id):
        if rebus_id not in self.mailboxes and rebus_id not in self.parcelboxes:
            raise ValueError('Trying to open rebus device that is not a parcelbox of mailbox')
        if rebus_id in self.mailboxes:
            return self.mailboxes[rebus_id]
        else:
            return self.parcelboxes[rebus_id]

    def open_box(self, rebus_id):
        device = self.get_lock(rebus_id)
        self._send_lock_event(rebus_id, True)
        device.is_open = True
        # initiate a lock countdown
        self._lock_status[rebus_id] = 0
        return device

    def _close_box(self, rebus_id):
        device = self.get_lock(rebus_id)
        self._send_lock_event(rebus_id, False)
        device.is_open = False
        return device

    # Doorbells

    def get_doorbells(self):
        return list(self.doorbells.values())

    def ring_doorbell(self, doorbell_id):
        # type: (int) -> None
        if doorbell_id not in self.doorbells:
            raise ValueError('Cannot ring doorbell device, device does not exists or is non doorbell device')

    ######################
    # FAKE DISCOVERY
    ######################

    def discover_devices(self):
        _ = self
        logger.info('Parsing the dummy_rebus_devices.json file')
        rebus_json = None
        try:
            with open(self.dummy_rebus_json_file) as rebus_json_file:
                rebus_json = json.load(rebus_json_file)
        except Exception as ex:
            error_msg = 'Could not read int the dummy_rebus_devices.json: {}'.format(ex)
            logger.error(error_msg)
            raise RebusException(error_msg)

        for json_device in rebus_json['devices']:
            logger.info("Found device: {}".format(json_device))
            dev_id = json_device['id']
            dev_type = json_device['type']
            if dev_type == 'mailbox':
                apartment_dto = self.apartment_controller.load_apartment_by_mailbox_id(dev_id)
                initial_state = json_device['initial_state'] == 'open'
                if initial_state:
                    self._send_lock_event(dev_id, True)
                self.mailboxes[dev_id] = MailBoxDTO(
                    id=dev_id,
                    label=str(dev_id),
                    apartment=apartment_dto,
                    is_open=initial_state
                )
            elif dev_type == 'parcelbox':
                apartment_dto = self.apartment_controller.load_apartment_by_mailbox_id(dev_id)
                available = self.delivery_controller.parcel_id_available(dev_id)
                initial_state = json_device['initial_state'] == 'open'
                if initial_state:
                    self._send_lock_event(dev_id, True)
                self.parcelboxes[dev_id] = ParcelBoxDTO(
                    id=dev_id,
                    label=str(dev_id),
                    available=available,
                    height=json_device['height'],
                    width=json_device['width'],
                    is_open=initial_state,
                    size=ParcelBoxDTO.Size(json_device['size'])
                )
            elif dev_type == 'doorbell':
                apartment = self.apartment_controller.load_apartment_by_doorbell_id(dev_id)
                self.doorbells[dev_id] = DoorbellDTO(
                    id=dev_id,
                    label=str(dev_id),
                    apartment=apartment
                )

        self.lock_tick_thread.start()

    ######################
    # REBUS COMMANDS
    ######################

    def get_lock_status(self, lock_id):
        device = self.get_lock(lock_id)
        return device.is_open

    def toggle_rebus_power(self, duration=0.5):
        pass

    ########################
    # VERIFICATION COMMANDS
    ########################

    def verify_device_exists(self, device_id):
        return device_id in self.mailboxes or \
            device_id in self.parcelboxes or \
            device_id in self.doorbells
