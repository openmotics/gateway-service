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
import abc
import datetime

import six
from dateutil.tz import tzlocal
import enum
import logging
from six.moves.configparser import ConfigParser, NoOptionError, NoSectionError
import os

import constants
from gateway.models import RFID, User
from gateway.mappers import RfidMapper
from gateway.dto import RfidDTO, UserDTO
from gateway.pubsub import PubSub
from rfid.idtronic_M890.idtronic_M890 import IdTronicM890
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MyPy
    from typing import List, Optional, Type

logger = logging.getLogger(__name__)


@Injectable.named('rfid_controller')
@Singleton
class RfidController(object):
    def __init__(self):
        config = ConfigParser()
        config.read(constants.get_config_file())
        try:
            rfid_device_file = config.get('OpenMotics', 'rfid_device')
        except NoOptionError:
            rfid_device_file = None
        self.rfid_context = RfidContext(self)
        if rfid_device_file is not None and not os.path.exists(rfid_device_file):
            self.rfid_device = IdTronicM890(rfid_device_file)
            self.rfid_device.set_new_scan_callback(self.rfid_context.handle_rfid_scan)
        else:
            self.rfid_device = None

    @staticmethod
    def load_rfid(rfid_id):
        # type: (int) -> Optional[RfidDTO]
        rfid_orm = RFID.get_or_none(RFID.id == rfid_id)
        if rfid_orm is None:
            return None
        rfid_dto = RfidMapper.orm_to_dto(rfid_orm)
        return rfid_dto

    @staticmethod
    def load_rfids():
        # type: () -> List[RfidDTO]
        rfids = []
        for rfid_orm in RFID.select():
            rfid_dto = RfidMapper.orm_to_dto(rfid_orm)
            rfids.append(rfid_dto)
        return rfids

    @staticmethod
    def get_rfid_count():
        # type: () -> int
        return RFID.select().count()

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
        return RfidMapper.orm_to_dto(rfid_orm)

    @staticmethod
    def delete_rfid(rfid_id):
        RFID.delete().where(RFID.id == rfid_id).execute()

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
        self.rfid_context.set_add_badge_state(user, label)

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
        logger.info('Got a new rfid scanned')
        # ToDo add the events here


class RfidAddBadgeState(RfidState):
    @staticmethod
    def handle_rfid_scan(context):
        rfid_dto = RfidDTO(tag_string=context.last_scanned_uuid,
                           label=context.label,
                           user=context.user)
        context.rfid_controller.save_rfid(rfid_dto)


class RfidContext(object):
    def __init__(self, rfid_controller):
        self.rfid_controller = rfid_controller
        self.last_scanned_uuid = None
        self.rfid_state = RfidStandByState  # type: Type[RfidState]

        self.label = None
        self.user = None

    def handle_rfid_scan(self, rfid_uuid):
        self.last_scanned_uuid = rfid_uuid
        self.rfid_state.handle_rfid_scan(self.last_scanned_uuid)

    def set_add_badge_state(self, label, user):
        self.label = label
        self.user = user
        self.rfid_state = RfidAddBadgeState

    def stop_add_badge_state(self):
        self.label = None
        self.user = None
        self.rfid_state = RfidStandByState

