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
apartment controller manages the apartment objects that are known in the system
"""
import logging

from gateway.events import EsafeEvent, EventError
from gateway.exceptions import ItemDoesNotExistException, StateException
from gateway.models import Apartment
from gateway.mappers import ApartmentMapper
from gateway.dto import ApartmentDTO
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MyPy
    from typing import List, Optional, Dict, Any
    from esafe.rebus import RebusController

logger = logging.getLogger(__name__)


@Injectable.named('apartment_controller')
@Singleton
class ApartmentController(object):
    def __init__(self):
        self.rebus_controller = None

    def set_rebus_controller(self, rebus_controller):
        self.rebus_controller = rebus_controller  # type: RebusController

    @staticmethod
    @Inject
    def send_config_change_event(msg, error=EventError.ErrorTypes.NO_ERROR, pubsub=INJECTED):
        # type: (str, Dict[str, Any], PubSub) -> None
        event = EsafeEvent(EsafeEvent.Types.CONFIG_CHANGE, {'type': 'Apartment', 'msg': msg}, error=error)
        pubsub.publish_esafe_event(PubSub.EsafeTopics.CONFIG, event)

    @staticmethod
    def load_apartment(apartment_id):
        # type: (int) -> Optional[ApartmentDTO]
        apartment_orm = Apartment.select().where(Apartment.id == apartment_id).first()
        if apartment_orm is None:
            return None
        apartment_dto = ApartmentMapper.orm_to_dto(apartment_orm)
        return apartment_dto

    @staticmethod
    def load_apartment_by_mailbox_id(mailbox_id):
        # type: (int) -> Optional[ApartmentDTO]
        apartment_orm = Apartment.select().where(Apartment.mailbox_rebus_id == mailbox_id).first()
        if apartment_orm is None:
            return None
        apartment_dto = ApartmentMapper.orm_to_dto(apartment_orm)
        return apartment_dto

    @staticmethod
    def load_apartment_by_doorbell_id(doorbell_id):
        # type: (int) -> Optional[ApartmentDTO]
        apartment_orm = Apartment.select().where(Apartment.doorbell_rebus_id == doorbell_id).first()
        if apartment_orm is None:
            return None
        apartment_dto = ApartmentMapper.orm_to_dto(apartment_orm)
        return apartment_dto

    @staticmethod
    def load_apartments():
        # type: () -> List[ApartmentDTO]
        apartments = []
        for apartment_orm in Apartment.select():
            apartment_dto = ApartmentMapper.orm_to_dto(apartment_orm)
            apartments.append(apartment_dto)
        return apartments

    @staticmethod
    def get_apartment_count():
        # type: () -> int
        return Apartment.select().count()

    @staticmethod
    def apartment_id_exists(apartment_id):
        # type: (int) -> bool
        apartments = ApartmentController.load_apartments()
        ids = (x.id for x in apartments)
        return apartment_id in ids

    def _check_rebus_ids(self, apartment_dto):
        if self.rebus_controller is None:
            raise StateException("Cannot save apartment: Rebus Controller is None")
        if 'doorbell_rebus_id' in apartment_dto.loaded_fields and \
                not self.rebus_controller.verify_device_exists(apartment_dto.doorbell_rebus_id):
            raise ItemDoesNotExistException("Cannot save apartment: doorbell ({}) does not exists".format(apartment_dto.doorbell_rebus_id))
        if 'mailbox_rebus_id' in apartment_dto.loaded_fields and \
                not self.rebus_controller.verify_device_exists(apartment_dto.mailbox_rebus_id):
            raise ItemDoesNotExistException("Cannot save apartment: mailbox ({}) does not exists".format(apartment_dto.mailbox_rebus_id))

    def save_apartment(self, apartment_dto):
        # type: (ApartmentDTO) -> Optional[ApartmentDTO]
        self._check_rebus_ids(apartment_dto)
        apartment_orm = ApartmentMapper.dto_to_orm(apartment_dto)
        apartment_orm.save()
        ApartmentController.send_config_change_event('save')
        return ApartmentController.load_apartment(apartment_orm.id)

    def update_apartment(self, apartment_dto):
        # type: (ApartmentDTO) -> Optional[ApartmentDTO]
        self._check_rebus_ids(apartment_dto)
        if 'id' not in apartment_dto.loaded_fields or apartment_dto.id is None:
            raise RuntimeError('cannot update an apartment without the id being set')
        try:
            apartment_orm = Apartment.select().where(Apartment.id == apartment_dto.id).first()
            for field in apartment_dto.loaded_fields:
                if field == 'id':
                    continue
                if hasattr(apartment_orm, field):
                    setattr(apartment_orm, field, getattr(apartment_dto, field))
            apartment_orm.save()
            ApartmentController.send_config_change_event('update')
        except Exception as e:
            raise RuntimeError('Could not update the user: {}'.format(e))
        return ApartmentController.load_apartment(apartment_dto.id)

    @staticmethod
    def delete_apartment(apartment_dto):
        # type: (ApartmentDTO) -> None
        if "id" in apartment_dto.loaded_fields and apartment_dto.id is not None:
            Apartment.delete_by_id(apartment_dto.id)
        elif "name" in apartment_dto.loaded_fields:
            # First check if there is only one:
            if Apartment.select().where(Apartment.name == apartment_dto.name).count() <= 1:
                Apartment.delete().where(Apartment.name == apartment_dto.name).execute()
                ApartmentController.send_config_change_event('delete')
            else:
                raise RuntimeError('More than one apartment with the given name: {}'.format(apartment_dto.name))
        else:
            raise RuntimeError('Could not find an apartment with the name {} to delete'.format(apartment_dto.name))
