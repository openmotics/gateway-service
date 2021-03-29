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

from peewee import (
    Model, Database, SqliteDatabase,
    AutoField, CharField, IntegerField,
    ForeignKeyField, BooleanField, FloatField,
    TextField
)
from peewee_migrate import Migrator
import constants

if False:  # MYPY
    from typing import Dict, Any


def migrate(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None

    class BaseModel(Model):
        class Meta:
            database = SqliteDatabase(constants.get_gateway_database_file(),
                                      pragmas={'foreign_keys': 1})

    class Apartment(BaseModel):
        id = AutoField()
        name = CharField(null=False)
        mailbox_rebus_id = IntegerField(unique=True)
        doorbell_rebus_id = IntegerField(unique=True)

    # USER Intermediate MODEL:
    # ---------------------
    class User(BaseModel):
        class Meta:
            table_name = 'user'

        class UserRoles(object):
            USER = 'USER'
            ADMIN = 'ADMIN'
            TECHNICIAN = 'TECHNICIAN'
            COURIER = 'COURIER'

        class UserLanguages(object):
            EN = 'English'
            DE = 'Deutsh'
            NL = 'Nederlands'
            FR = 'Français'

        id = AutoField()
        username_old = CharField(unique=True)
        first_name = CharField(null=True)  # Allow null values for this migration, set it back afterwards
        last_name = CharField(null=False, default='')
        role = CharField(default=UserRoles.USER, null=False)
        pin_code = CharField(null=False, default='', unique=False)  # Allow null values for this migration, set it back afterwards
        language = CharField(null=False, default='English')
        password = CharField()
        apartment_id = ForeignKeyField(Apartment, null=True, default=None, backref='users', on_delete='SET NULL')
        is_active = BooleanField(default=True)
        accepted_terms = IntegerField(default=0)

    for user in User.select():
        user.first_name = user.username_old
        user.pin_code = user.username_old
        user.role = User.UserRoles.ADMIN  # Set all existing users as admin users
        user.save()

    # Change the first name back to non null values
    migrator.change_fields(User, first_name=CharField(null=False))
    # Change the pin code field after the fact since it will not allow to be set unique when adding the column
    # The pin_code is by definition unique since it is a copy of username for the existing users,
    # (making the pin code unusable for the most part) which is also unique.
    migrator.change_fields(User, pin_code=CharField(null=False, unique=True))


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
