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
    AutoField, CharField, BooleanField, IntegerField, ForeignKeyField,
    SQL
)
from peewee_migrate import Migrator
import constants

if False:  # MYPY
    from typing import Dict, Any, List


def migrate(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None

    class BaseModel(Model):
        class Meta:
            database = SqliteDatabase(constants.get_gateway_database_file(),
                                      pragmas={'foreign_keys': 1})

    class Apartment(BaseModel):
        id = AutoField(constraints=[SQL('AUTOINCREMENT')], unique=True)
        name = CharField(null=False)
        mailbox_rebus_id = IntegerField(unique=True, null=True)
        doorbell_rebus_id = IntegerField(unique=True, null=True)

    class User(BaseModel):
        class UserRoles(object):
            SUPER = 'SUPER'
            USER = 'USER'
            ADMIN = 'ADMIN'
            TECHNICIAN = 'TECHNICIAN'
            COURIER = 'COURIER'

        id = AutoField(constraints=[SQL('AUTOINCREMENT')], unique=True)
        username = CharField(null=False, unique=True)
        first_name = CharField(null=True)
        last_name = CharField(null=True)
        role = CharField(default=UserRoles.USER, null=False, )  # options USER, ADMIN, TECHNICIAN, COURIER, SUPER
        pin_code = CharField(null=True, unique=True)
        language = CharField(null=False)  # options: See languages
        password = CharField()
        apartment = ForeignKeyField(Apartment, null=True, default=None, backref='users', on_delete='SET NULL')
        is_active = BooleanField(default=True)
        accepted_terms = IntegerField(default=0)
        email = CharField(null=True, unique=False)

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

    migrator.add_columns(Delivery, user_delivery_tmp=ForeignKeyField(User, backref='deliveries', on_delete='SET NULL', null=True))
    migrator.add_columns(Delivery, user_pickup_tmp=ForeignKeyField(User, backref='pickups', on_delete='SET NULL', null=True))

def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass

