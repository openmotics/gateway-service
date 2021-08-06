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
This migration will add an email address field to the existing users
"""

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
            ALL = [
                EN,
                DE,
                NL,
                FR,
            ]

        id = AutoField(constraints=[SQL('AUTOINCREMENT')], unique=True)
        username = CharField(null=False, unique=True)
        first_name = CharField(null=True)
        last_name = CharField(null=True)
        role = CharField(default=UserRoles.USER, null=False, )  # options USER, ADMIN, TECHINICAN, COURIER, SUPER
        pin_code = CharField(null=True, unique=True)
        language = CharField(null=False, default='English')  # options: See Userlanguages
        password = CharField()
        apartment = ForeignKeyField(Apartment, null=True, default=None, backref='users', on_delete='SET NULL')
        is_active = BooleanField(default=True)
        accepted_terms = IntegerField(default=0)

    # translate the existing languages to the iso format
    language_translation = {
        'English': 'en',
        'Deutsch': 'de',
        'Nederlands': 'nl',
        'Francais': 'fr'
    }
    for user in User.select():
        try:
            old_lang = user.language
            user.language = language_translation[old_lang]
            user.save()
        except KeyError:
            pass


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
