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
from gateway.enums import ModuleType, EnergyEnums
import constants

if False:  # MYPY
    from typing import Dict, Any, List


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

    energy_modules = EnergyModule.select(EnergyModule, Module) \
                                 .join_from(EnergyModule, Module)  # type: List[EnergyModule]
    for energy_module in energy_modules:
        module = energy_module.module
        module.module_type = {EnergyEnums.Version.ENERGY_MODULE: ModuleType.ENERGY,
                              EnergyEnums.Version.P1_CONCENTRATOR: ModuleType.P1_CONCENTRATOR,
                              EnergyEnums.Version.POWER_MODULE: ModuleType.POWER}.get(energy_module.version, ModuleType.ENERGY)
        module.save()

    migrator.add_columns(Module,
                         update_success=BooleanField(null=True))


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass

