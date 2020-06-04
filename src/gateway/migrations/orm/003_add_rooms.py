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
    PrimaryKeyField, CharField, BooleanField, IntegerField, ForeignKeyField
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

    class Floor(BaseModel):
        id = PrimaryKeyField()
        number = IntegerField(unique=True)
        name = CharField(null=True)

    class Room(BaseModel):
        id = PrimaryKeyField()
        number = IntegerField(unique=True)
        name = CharField(null=True)
        floor = ForeignKeyField(Floor, null=True, on_delete='SET NULL', backref='rooms')

    class Input(BaseModel):
        id = PrimaryKeyField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='inputs')

    class Shutter(BaseModel):
        id = PrimaryKeyField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='shutters')

    class ShutterGroup(BaseModel):
        id = PrimaryKeyField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='shutter_groups')

    class Sensor(BaseModel):
        id = PrimaryKeyField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='sensors')

    class PulseCounter(BaseModel):
        id = PrimaryKeyField()
        number = IntegerField(unique=True)
        name = CharField()
        source = CharField()  # Options: 'master' or 'gateway'
        persistent = BooleanField()
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='pulse_counters')

    migrator.create_model(Floor)
    migrator.create_model(Room)
    migrator.create_model(Input)
    migrator.create_model(Shutter)
    migrator.create_model(ShutterGroup)
    migrator.create_model(Sensor)
    migrator.create_model(PulseCounter)

    class Output(BaseModel):
        id = PrimaryKeyField()
        number = IntegerField(unique=True)

    migrator.add_columns(Output,
                         room=ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='outputs'))


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
