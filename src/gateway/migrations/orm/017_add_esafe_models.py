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

    # CURRENT USER MODEL
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

    # USER TARGET MODEL:
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
        first_name = CharField(null=False)
        last_name = CharField(null=False, default='')
        role = CharField(default=UserRoles.USER, null=False, )  # options USER, ADMIN, TECHINICAN, COURIER
        pin_code = CharField(null=False, unique=True)
        language = CharField(null=False, default='English')  # options: See Userlanguages
        password = CharField()
        apartment_id = ForeignKeyField(Apartment, null=True, default=None, backref='users', on_delete='SET NULL')
        is_active = BooleanField(default=True)
        accepted_terms = IntegerField(default=0)


    class RFID(BaseModel):
        id = AutoField()
        tag_string = CharField(null=False, unique=True)
        uid_manufacturer = CharField(null=False, unique=True)
        uid_extension = CharField()
        enter_count = IntegerField(null=False)
        blacklisted = BooleanField(null=False, default=False)
        label = CharField()
        timestamp_created = CharField()
        timestamp_last_used = CharField()
        user_id = ForeignKeyField(User, null=False, backref='rfids', on_delete='CASCADE')


    class Delivery(BaseModel):
        id = AutoField()
        type = CharField(null=False)
        timestamp_delivery = CharField(null=False)
        timestamp_pickup = CharField()
        courier_firm = CharField()
        signature_delivery = CharField(null=False)
        signature_pickup = CharField()
        parcelbox_rebus_id = IntegerField(null=False)
        user_id_delivery = ForeignKeyField(User, backref='deliveries', on_delete='NO ACTION', null=False)
        user_id_pickup = ForeignKeyField(User, backref='pickups', on_delete='NO ACTION')

    migrator.create_model(Apartment)
    migrator.create_model(RFID)
    migrator.create_model(Delivery)

    # Since there is a bug in peewee_migrate, just run the raw sql form of the table rename.
    # Updating to a newer version of peewee_migrate is not applicable since the current version
    # is the latest one supported by Python 2.7
    migrator.sql('ALTER TABLE user RENAME TO _user_old')
    migrator.create_model(User)

def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
