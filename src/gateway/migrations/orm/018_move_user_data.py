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
    TextField, SQL
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
        id = AutoField(constraints=[SQL('AUTOINCREMENT')], unique=True)
        name = CharField(null=False)
        mailbox_rebus_id = IntegerField(unique=True)
        doorbell_rebus_id = IntegerField(unique=True)

    # User old table
    # -----------------------
    class UserOld(BaseModel):
        class Meta:
            table_name = '_user_old'
        id = AutoField()
        username = CharField(unique=True)
        password = CharField()
        accepted_terms = IntegerField(default=0)

    # User definitive model
    # ------------------------
    class User(BaseModel):
        class UserRoles(object):
            SUPER = 'SUPER'
            USER = 'USER'
            ADMIN = 'ADMIN'
            TECHNICIAN = 'TECHNICIAN'
            COURIER = 'COURIER'

        class UserLanguages(object):
            EN = 'English'
            DE = 'Deutsch'
            NL = 'Nederlands'
            FR = 'Francais'

        # id = AutoField()
        id = AutoField(constraints=[SQL('AUTOINCREMENT')], unique=True)
        username = CharField(null=False, unique=True)
        first_name = CharField(null=True)
        last_name = CharField(null=True)
        role = CharField(default=UserRoles.USER, null=False, )  # options USER, ADMIN, TECHINICAN, COURIER
        pin_code = CharField(null=True, unique=True)
        language = CharField(null=False, default='English')  # options: See Userlanguages
        password = CharField()
        apartment_id = ForeignKeyField(Apartment, null=True, default=None, backref='users', on_delete='SET NULL')
        is_active = BooleanField(default=True)
        accepted_terms = IntegerField(default=0)

    # copy over the data from the old table to the new one
    for old_user in UserOld.select():
        print('Migrating user: {}, {}'.format(old_user.id, old_user.username))
        User.create(
            id=old_user.id,
            username=old_user.username,
            password=old_user.password,
            role=User.UserRoles.SUPER,
            language=User.UserLanguages.EN,
            accepted_terms=old_user.accepted_terms
        )

    # remove the old user table since it is not needed anymore
    migrator.drop_table(UserOld)


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
