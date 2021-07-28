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
            USER = 'USER'
            ADMIN = 'ADMIN'
            TECHNICIAN = 'TECHNICIAN'
            COURIER = 'COURIER'

        class UserLanguages(object):
            EN = 'English'
            DE = 'Deutsch'
            NL = 'Nederlands'
            FR = 'Francais'

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


    class RFID(BaseModel):
        id = AutoField(constraints=[SQL('AUTOINCREMENT')], unique=True)
        tag_string = CharField(null=False, unique=True)
        uid_manufacturer = CharField(null=False, unique=True)
        uid_extension = CharField(null=True)
        enter_count = IntegerField(null=False)
        blacklisted = BooleanField(null=False, default=False)
        label = CharField()
        timestamp_created = CharField(null=False)
        timestamp_last_used = CharField(null=True)
        user_id = ForeignKeyField(User, null=False, backref='rfids', on_delete='CASCADE')


    class Delivery(BaseModel):
        class DeliveryType(object):
            DELIVERY = 'DELIVERY'
            RETURN = 'RETURN'

        id = AutoField(constraints=[SQL('AUTOINCREMENT')], unique=True)
        type = CharField(null=False)  # options: DeliveryType
        timestamp_delivery = CharField(null=False)
        timestamp_pickup = CharField(null=True)
        courier_firm = CharField(null=True)
        signature_delivery = CharField(null=True)
        signature_pickup = CharField(null=True)
        parcelbox_rebus_id = IntegerField(null=False)
        user_delivery = ForeignKeyField(User, backref='deliveries', on_delete='NO ACTION', null=True)
        user_pickup = ForeignKeyField(User, backref='pickups', on_delete='NO ACTION', null=False)

    migrator.drop_table(Delivery)
    migrator.drop_table(RFID)

    migrator.create_table(Delivery)
    migrator.create_table(RFID)


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
