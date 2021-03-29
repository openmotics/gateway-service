# Copyright (C) 2020 OpenMotics BV
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

import os
import logging
import constants
from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import User, Apartment

from peewee import (
    Model, Database, SqliteDatabase,
    AutoField, CharField, IntegerField,
    ForeignKeyField, BooleanField, FloatField,
    TextField
)

logger = logging.getLogger('openmotics')


class Users2Migrator(BaseMigrator):

    MIGRATION_KEY = 'users_2'

    @classmethod
    def _migrate(cls):
        # type: () -> None

        # first copy over all the users form the old table to the new table
        class BaseModel(Model):
            class Meta:
                database = SqliteDatabase(constants.get_gateway_database_file(),
                                          pragmas={'foreign_keys': 1})
        # CURRENT/OLD USER MODEL
        # -------------------
        class UserOld(BaseModel):
            class Meta:
                table_name = '_user_old'

            class UserRoles(object):
                USER = 'USER'
                ADMIN = 'ADMIN'
                TECHNICIAN = 'TECHNICIAN'
                COURIER = 'COURIER'
            id = AutoField()
            username = CharField(unique=True)
            password = CharField()
            accepted_terms = IntegerField(default=0)

        for user in UserOld.select():
            user_orm = User()
            user_orm.username = user.username  # this will populate first_name and last_name as well.
            user_orm.pin_code = user.username
            user_orm.role = User.UserRoles.ADMIN
            user_orm.password = user.password
            user_orm.accepted_terms = user.accepted_terms
            user_orm.save()

        UserOld.drop_table()
