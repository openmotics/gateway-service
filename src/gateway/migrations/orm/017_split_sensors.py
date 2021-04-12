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
    TextField
)
from peewee_migrate import Migrator
import constants

if False:  # MYPY
    from typing import Dict, Any


def migrate(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    """
    Write your migrations here.

    > migrator.sql(sql)
    > migrator.python(func, *args, **kwargs)
    > migrator.create_model(Model)
    > migrator.store_model(Model)
    > migrator.remove_model(Model, cascade=True)
    > migrator.add_fields(Model, **fields)
    > migrator.change_fields(Model, **fields)
    > migrator.remove_fields(Model, *field_names, cascade=True)
    > migrator.rename_field(Model, old_field_name, new_field_name)
    > migrator.rename_table(Model, new_table_name)
    > migrator.add_index(Model, *col_names, unique=False)
    > migrator.drop_index(Model, index_name)
    > migrator.add_not_null(Model, field_name)
    > migrator.drop_not_null(Model, field_name)
    > migrator.add_default(Model, field_name, default)
    """

    class BaseModel(Model):
        class Meta:
            database = SqliteDatabase(constants.get_gateway_database_file(),
                                      pragmas={'foreign_keys': 1})

    class Floor(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField(null=True)

    class Room(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField(null=True)
        floor = ForeignKeyField(Floor, null=True, on_delete='SET NULL', backref='rooms')

    class Plugin(BaseModel):
        id = AutoField()
        name = CharField(unique=True)
        version = CharField()

    class Sensor(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='sensors')

    migrator.drop_index(Sensor, 'number')
    migrator.rename_field(Sensor, 'number', 'external_id')
    migrator.change_fields(Sensor, external_id=CharField())
    migrator.add_fields(Sensor,
                        source=CharField(default='master'),
                        plugin=ForeignKeyField(Plugin, null=True, on_delete='CASCADE'),
                        physical_quantity=CharField(null=True),
                        unit=CharField(null=True),
                        name=CharField(default=''))
    migrator.add_index(Sensor, 'source', 'plugin_id', 'external_id', 'physical_quantity', unique=True)


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
