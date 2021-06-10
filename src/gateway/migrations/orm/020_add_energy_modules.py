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
    AutoField, CharField, BooleanField, IntegerField, ForeignKeyField
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

    class Module(BaseModel):
        id = AutoField()
        source = CharField()
        address = CharField()
        module_type = CharField(null=True)
        hardware_type = CharField()
        firmware_version = CharField(null=True)
        hardware_version = CharField(null=True)
        order = IntegerField(null=True)
        last_online_update = IntegerField(null=True)

    class EnergyModule(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        version = IntegerField()
        name = CharField(default='')
        module = ForeignKeyField(Module, on_delete='CASCADE', backref='energy_modules', unique=True)

    class EnergyCT(BaseModel):
        id = AutoField()
        number = IntegerField()
        name = CharField(default='')
        sensor_type = IntegerField()
        times = CharField()
        inverted = BooleanField(default=False)
        energy_module = ForeignKeyField(EnergyModule, on_delete='CASCADE', backref='cts')

        class Meta:
            indexes = (
                (('number', 'energy_module_id'), True),
            )

    migrator.create_model(EnergyModule)
    migrator.create_model(EnergyCT)
    migrator.add_index(EnergyCT, 'number', 'energy_module_id', unique=True)


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
