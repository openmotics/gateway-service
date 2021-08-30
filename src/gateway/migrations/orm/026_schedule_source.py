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

    class Schedule(BaseModel):
        id = AutoField()
        name = CharField()
        start = FloatField()
        repeat = CharField(null=True)
        duration = FloatField(null=True)
        end = FloatField(null=True)
        action = CharField()
        arguments = CharField(null=True)
        status = CharField()

    migrator.add_columns(Schedule,
                         source=CharField(default='gateway'),
                         external_id=CharField(null=True))
    migrator.add_index(Schedule, 'source', 'external_id', unique=True)


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
