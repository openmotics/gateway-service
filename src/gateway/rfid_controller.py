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
RFID BLL
"""

import constants
from gateway.events import EsafeEvent, EventError
from gateway.models import RFID
from gateway.mappers import RfidMapper
from gateway.dto import RfidDTO, UserDTO
from gateway.pubsub import PubSub
from gateway.system_config_controller import SystemConfigController
from esafe.rfid import IdTronicM890
from esafe.rfid import RfidException
from ioc import INJECTED, Inject, Injectable, Singleton

import abc
import datetime
from dateutil.tz import tzlocal
import logging
import os
import six
from six.moves.configparser import ConfigParser, NoOptionError, NoSectionError

if False:  # MyPy
    from typing import List, Optional, Type, Dict, Any

logger = logging.getLogger(__name__)


@Injectable.named('rfid_controller')
@Singleton
class RfidController(object):
    @Inject
    def __init__(self, system_config_controller=INJECTED):
        # type: (SystemConfigController) -> None
        logger.debug('Creating rfid_controller')
        self.system_config_controller = system_config_controller
        logger.debug(' -> Reading out the config file')
        config = ConfigParser()
        config.read(constants.get_config_file())
        rfid_device_file = None
        try:
            rfid_device_file = config.get('OpenMotics', 'rfid_device')
        except NoOptionError:
            pass
        except NoSectionError:  # This needs to be here for testing on Jenkins, there will be no config file
            pass
        logger.debug(' -> Result: {}'.format(rfid_device_file))
        logger.debug(' -> Creating rfid context')
        self.rfid_context = RfidContext(self)
        self.rfid_device = None
        if rfid_device_file is not None and os.path.exists(rfid_device_file):
            logger.debug(' -> Creating rfid device')
            self.rfid_device = IdTronicM890(rfid_device_file)
            logger.debug(' -> Setting the callback')
            self.rfid_device.set_new_scan_callback(self.rfid_context.handle_rfid_scan)

    def start(self):
        logger.debug('Starting the rfid reader')
        if self.rfid_device is not None:
            logger.debug(' -> Starting the rfid reader')
            self.rfid_device.start()

    def stop(self):
        logger.debug('Stopping the rfid reader')
        if self.rfid_device is not None:
            logger.debug(' -> Stopping the rfid reader')
            self.rfid_device.stop()

    @staticmethod
    @Inject
    def send_config_change_event(error=EventError.ErrorTypes.NO_ERROR, pubsub=INJECTED):
        # type: (Dict[str, Any], PubSub) -> None
        event = EsafeEvent(EsafeEvent.Types.CONFIG_CHANGE, {'type': 'RFID'}, error=error)
        pubsub.publish_esafe_event(PubSub.EsafeTopics.CONFIG, event)

    @staticmethod
    def load_rfid(rfid_id):
        # type: (int) -> Optional[RfidDTO]
        rfid_orm = RFID.get_or_none(RFID.id == rfid_id)
        if rfid_orm is None:
            return None
        rfid_dto = RfidMapper.orm_to_dto(rfid_orm)
        return rfid_dto

    @staticmethod
    def load_rfids(user_id=None):
        # type: (Optional[int]) -> List[RfidDTO]
        rfids = []
        query = RFID.select()
        if user_id is not None and isinstance(user_id, int):
            query = query.where(RFID.user_id == user_id)
        for rfid_orm in query:
            rfid_dto = RfidMapper.orm_to_dto(rfid_orm)
            rfids.append(rfid_dto)
        return rfids

    @staticmethod
    def check_if_rfid_exists(rfid_tag):
        query = RFID.select().where(RFID.tag_string == rfid_tag)
        rfid_orm = query.first()
        return rfid_orm is not None

    @staticmethod
    def get_rfid_count(user_id=None):
        # type: (Optional[int]) -> int
        query = RFID.select()
        if user_id is not None and isinstance(user_id, int):
            query = query.where(RFID.user_id == user_id)
        return query.count()

    @staticmethod
    def check_rfid_tag_for_login(rfid_tag_string):
        # type: (str) -> Optional[RfidDTO]
        rfid_orm = RFID.select().where(RFID.tag_string == rfid_tag_string).first()
        if rfid_orm is None:
            return None
        rfid_orm.timestamp_last_used = RfidController.current_timestamp_to_string_format()
        rfid_orm.save()
        rfid_dto = RfidMapper.orm_to_dto(rfid_orm)
        return rfid_dto

    @staticmethod
    def save_rfid(rfid_dto):
        # type: (RfidDTO) -> Optional[RfidDTO]
        rfid_orm = RfidMapper.dto_to_orm(rfid_dto)
        if rfid_orm.user is None:
            raise ValueError("User is needed to identify an RFID tag")
        rfid_orm.user.save()
        if rfid_orm.timestamp_created is None:
            rfid_orm.timestamp_created = RfidController.current_timestamp_to_string_format()
        if rfid_orm.enter_count is None:
            rfid_orm.enter_count = 0
        rfid_orm.save()
        RfidController.send_config_change_event()
        return RfidMapper.orm_to_dto(rfid_orm)

    @staticmethod
    def delete_rfid(rfid_id):
        RFID.delete().where(RFID.id == rfid_id).execute()
        RfidController.send_config_change_event()

    @staticmethod
    def datetime_to_string_format(timestamp):
        # type: (datetime.datetime) -> str
        # replace the microseconds to not show them in the string
        return timestamp.replace(microsecond=0).isoformat('T')

    @staticmethod
    def current_timestamp_to_string_format():
        # type: () -> str
        timestamp = datetime.datetime.now(tzlocal())
        return RfidController.datetime_to_string_format(timestamp)

    def start_add_rfid_session(self, user, label):
        # type: (UserDTO, str) -> None
        # check that it is allowed for this user to add an extra badge
        rfid_config = self.system_config_controller.get_rfid_config()
        max_rfid = rfid_config.max_tags
        if max_rfid is None:
            raise RfidException('Cannot request the max_rfid config value')
        num_tags = self.get_rfid_count(user_id=user.id)
        if num_tags >= max_rfid:
            raise RfidException('Cannot start the add rfid session: Max number of tags ({}) is reached for user: "{}"'.format(max_rfid, user.username))
        logger.debug('Starting add rfid badge session: {} {}'.format(user, label))
        self.rfid_context.set_add_badge_state(label=label, user=user)

    def stop_add_rfid_session(self):
        self.rfid_context.stop_add_badge_state()

    def get_current_add_rfid_session_info(self):
        """
        Returns info about the add rfid session info.
         - When no session is running, Returns None
         - When a session is running, Returns the user_id Type: int
        """
        if self.rfid_context.rfid_state == RfidAddBadgeState:
            return self.rfid_context.user.id
        return None


# RFID state machine
# This will house the actions to take with the rfid device
# The states are:
# stand-by
# add-badge

@six.add_metaclass(abc.ABCMeta)
class RfidState(object):
    @staticmethod
    @abc.abstractmethod
    def handle_rfid_scan(context):
        # type: (RfidContext) -> None
        pass


class RfidStandByState(RfidState):

    @staticmethod
    @Inject
    def handle_rfid_scan(context, pubsub=INJECTED):
        # type: (RfidContext, PubSub) -> None
        logger.debug('Got a new rfid scanned: {}'.format(context.last_scanned_uuid))
        event_data = {
            'uuid': context.last_scanned_uuid,
            'action': 'SCAN'
        }
        error = EventError.ErrorTypes.NO_ERROR
        if not context.check_if_badge_uuid_exits():
            error = EventError.ErrorTypes.DOES_NOT_EXIST
        event = EsafeEvent(EsafeEvent.Types.RFID_CHANGE, event_data, error)
        logger.info("Sending eSafe event for rfid scan: {}".format(event))
        pubsub.publish_esafe_event(PubSub.EsafeTopics.RFID, event)


class RfidAddBadgeState(RfidState):
    @staticmethod
    @Inject
    def handle_rfid_scan(context, pubsub=INJECTED):
        logger.info('Saving the new scanned badge for user: {}: {}'.format(context.user.username, context.last_scanned_uuid))
        rfid_dto = RfidDTO(tag_string=context.last_scanned_uuid,
                           label=context.label,
                           user=context.user,
                           enter_count=-1,
                           uid_manufacturer=context.last_scanned_uuid)
        context.rfid_controller.save_rfid(rfid_dto)
        event_data = {
            'uuid': context.last_scanned_uuid,
            'action': 'REGISTER'
        }
        error = EventError.ErrorTypes.NO_ERROR
        event = EsafeEvent(EsafeEvent.Types.RFID_CHANGE, event_data, error)
        logger.info("Sending eSafe event for rfid registration: {}".format(event))
        pubsub.publish_esafe_event(PubSub.EsafeTopics.RFID, event)
        context.rfid_state = RfidStandByState


class RfidContext(object):
    def __init__(self, rfid_controller):
        # type: (RfidController) -> None
        self.rfid_controller = rfid_controller
        self.last_scanned_uuid = None  # type: Optional[str]
        self.rfid_state = RfidStandByState  # type: Type[RfidState]

        self.label = None  # type: Optional[str]
        self.user = None  # type: Optional[UserDTO]

    def handle_rfid_scan(self, rfid_uuid):
        logger.info("Handling RFID scan: {}".format(rfid_uuid))
        self.last_scanned_uuid = rfid_uuid
        self.rfid_state.handle_rfid_scan(self)

    def set_add_badge_state(self, label, user):
        # type: (str, UserDTO) -> None
        self.label = label
        self.user = user
        self.rfid_state = RfidAddBadgeState

    def stop_add_badge_state(self):
        self.label = None
        self.user = None
        self.rfid_state = RfidStandByState

    def check_if_badge_uuid_exits(self):
        return self.rfid_controller.check_if_rfid_exists(self.last_scanned_uuid)

