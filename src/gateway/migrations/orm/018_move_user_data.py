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
            USER = 'USER'
            ADMIN = 'ADMIN'
            TECHNICIAN = 'TECHNICIAN'
            COURIER = 'COURIER'

        class UserLanguages(object):
            EN = 'English'
            DE = 'Deutsh'
            NL = 'Nederlands'
            FR = 'Francais'

        id = AutoField()
        first_name = CharField(null=False)
        last_name = CharField(null=False, default='')
        role = CharField(default=UserRoles.USER, null=False, )  # options USER, ADMIN, TECHINICAN, COURIER
        pin_code = CharField(null=True, unique=True)
        language = CharField(null=False, default='English')  # options: See Userlanguages
        password = CharField()
        apartment_id = ForeignKeyField(Apartment, null=True, default=None, backref='users', on_delete='SET NULL')
        is_active = BooleanField(default=True)
        accepted_terms = IntegerField(default=0)

        # Keep these here to use as reference functions to populate the first_name and last_name fields
        # consistent with the implementation used in models.py at the moment of creating the migration
        @property
        def username(self):
            # type: () -> str
            separator = ''
            if self.first_name != '' and self.last_name != '':
                separator = ' '
            return "{}{}{}".format(self.first_name, separator, self.last_name)

        @username.setter
        def username(self, username):
            # type: (str) -> None
            splits = username.split(' ')
            if len(splits) > 1:
                self.first_name = splits[0]
                self.last_name = ' '.join(splits[1:])
            else:
                self.first_name = username
                self.last_name = ''

    # copy over the data from the old table to the new one
    for user in UserOld.select():
        print('Migrating user: {}'.format(user))
        user_orm = User()
        user_orm.username = user.username
        user_orm.role = User.UserRoles.ADMIN
        user_orm.pin_code = None
        user_orm.id = user.id
        user_orm.is_active = True
        user_orm.apartment_id = None
        user_orm.language = User.UserLanguages.EN
        user_orm.save()

    # remove the old user table since it is not needed anymore
    migrator.drop_table(UserOld)


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
