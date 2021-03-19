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
    class User(BaseModel):
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
    # class User(BaseModel):
    #     class EsafeUserRoles(object):
    #         USER = 'USER'
    #         ADMIN = 'ADMIN'
    #         TECHNICIAN = 'TECHNICIAN'
    #         COURIER = 'COURIER'
    #
    #     id = AutoField()
    #     first_name = CharField()
    #     last_name = CharField()
    #     username_old = CharField()
    #     role = CharField(default=EsafeUserRoles.USER, null=False, )  # options USER, ADMIN, TECHNICAN, COURIER
    #     pin_code = CharField(null=False, unique=True)
    #     password = CharField()
    #     apartment_id = ForeignKeyField(Apartment, backref='users', on_delete='SET NULL')
    #     is_active = BooleanField(default=True)
    #     accepted_terms = IntegerField(default=0)


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


    print('current user table:')
    for user in User.select():
        print(user)
        print('---')
    migrator.add_columns(User,
                         first_name=CharField(null=False, default=User.username),
                         last_name=CharField(null=True),
                         role=CharField(default=User.UserRoles.USER, null=False),
                         pin_code=CharField(null=False, default=User.username),
                         apartment_id=ForeignKeyField(Apartment, backref='users', on_delete='SET NULL', null=True, default=None),
                         is_active=BooleanField(default=True),
                         )
    migrator.rename_column(User,
                           old_name='username',
                           new_name='username_old')

    # Change the pin code field after the fact since it will not allow to be set unique when adding the column
    # The pin_code is by definition unique since it is a copy of username for the existing users,
    # (making the pin code unusable for the most part) which is also unique.
    migrator.change_columns(User,
                            pin_code=CharField(null=False, unique=True))


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
