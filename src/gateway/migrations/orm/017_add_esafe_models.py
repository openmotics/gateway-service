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


    class EsafeUser(BaseModel):
        class EsafeUserRoles(object):
            USER = 'USER'
            ADMIN = 'ADMIN'
            TECHNICIAN = 'TECHNICIAN'
            COURIER = 'COURIER'

        id = AutoField()
        first_name = CharField()
        last_name = CharField()
        role = CharField(default=EsafeUserRoles.USER, null=False, )  # options USER, ADMIN, TECHNICAN, COURIER
        code = CharField(null=False, unique=True)
        apartment_id = ForeignKeyField(Apartment, backref='users', on_delete='SET NULL')
        is_active = BooleanField(default=True)


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
        user_id = ForeignKeyField(EsafeUser, null=False, backref='rfids', on_delete='CASCADE')


    class Delivery(BaseModel):
        id = AutoField()
        type = CharField(null=False)
        timestamp_delivery = CharField(null=False)
        timestamp_pickup = CharField()
        courier_firm = CharField()
        signature_delivery = CharField(null=False)
        signature_pickup = CharField()
        parcelbox_rebus_id = IntegerField(null=False)
        user_id_delivery = ForeignKeyField(EsafeUser, backref='deliveries', on_delete='NO ACTION', null=False)
        user_id_pickup = ForeignKeyField(EsafeUser, backref='pickups', on_delete='NO ACTION')

    migrator.create_model(Apartment)
    migrator.create_model(RFID)
    migrator.create_model(Delivery)
    migrator.create_model(EsafeUser)


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
