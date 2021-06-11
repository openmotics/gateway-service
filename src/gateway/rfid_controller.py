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
import datetime
from dateutil.tz import tzlocal
import logging

from gateway.models import RFID, User
from gateway.mappers import RfidMapper
from gateway.dto import RfidDTO
from ioc import INJECTED, Inject, Injectable, Singleton

if False:  # MyPy
    from typing import List, Optional

logger = logging.getLogger('openmotics')


@Injectable.named('rfid_controller')
@Singleton
class RfidController(object):
    def __init__(self):
        pass

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
