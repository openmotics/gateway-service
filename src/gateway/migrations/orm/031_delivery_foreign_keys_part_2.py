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
import peewee
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
        user_delivery = ForeignKeyField(User, backref='deliveries_old', on_delete='NO ACTION', null=True)
        user_pickup = ForeignKeyField(User, backref='pickups_old', on_delete='NO ACTION', null=False)
        user_delivery_tmp = ForeignKeyField(User, backref='deliveries', on_delete='SET NULL', null=True)
        user_pickup_tmp = ForeignKeyField(User, backref='pickups', on_delete='SET NULL', null=True)

    # Get the admin user to temporarily link an unlinked delivery to
    admin_user = User.select().where(User.role == User.UserRoles.ADMIN).first()

    # Go over all the deliveries and unlink them if necessary
    for d in Delivery.select():
        if User.select().where(User.id == d.user_delivery_id).exists():
            d.user_delivery_tmp = d.user_delivery
        else:
            # set them to None to unlink them if they do not exists
            d.user_delivery = None

        if User.select().where(User.id == d.user_pickup_id).exists():
            d.user_pickup_tmp = d.user_pickup
        else:
            # Temporary link them to the admin user to have some user to save the delivery to. (user_pickup is not nullable)
            # the Admin user will be unlinked in the next step when the user_pickup_tmp will be renamed to user_pickup.
            d.user_pickup = admin_user

        try:
            d.save()
        except peewee.IntegrityError:
            pass

    migrator.drop_columns(Delivery, 'user_delivery')
    migrator.drop_columns(Delivery, 'user_pickup')

    migrator.rename_column(Delivery, 'user_delivery_tmp', 'user_delivery')
    migrator.rename_column(Delivery, 'user_pickup_tmp', 'user_pickup')

def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass

