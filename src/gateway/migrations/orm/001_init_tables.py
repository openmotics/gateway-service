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
    AutoField, CharField, BooleanField, IntegerField, ForeignKeyField, FloatField, TextField,
    CompositeKey
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

    class Feature(BaseModel):
        id = AutoField()
        name = CharField(unique=True)
        enabled = BooleanField()

    class Output(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)

    class ThermostatGroup(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField()
        on = BooleanField(default=True)
        threshold_temp = IntegerField(null=True, default=None)
        sensor = IntegerField(null=True, default=None)
        mode = CharField(default='heating')

    class OutputToThermostatGroup(BaseModel):
        class Meta:
            primary_key = CompositeKey('output', 'thermostat_group')

        output = ForeignKeyField(Output, on_delete='CASCADE')
        thermostat_group = ForeignKeyField(ThermostatGroup, on_delete='CASCADE')
        index = IntegerField()
        mode = CharField()
        value = IntegerField()

    class Pump(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField()
        output = ForeignKeyField(Output, backref='valve', on_delete='SET NULL', unique=True)

    class Valve(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField()
        delay = IntegerField(default=60)
        output = ForeignKeyField(Output, backref='valve', on_delete='SET NULL', unique=True)

    class PumpToValve(BaseModel):
        class Meta:
            primary_key = CompositeKey('pump', 'valve')

        pump = ForeignKeyField(Pump, on_delete='CASCADE')
        valve = ForeignKeyField(Valve, on_delete='CASCADE')

    class Thermostat(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField(default='Thermostat')
        sensor = IntegerField()

        pid_heating_p = FloatField(default=120)
        pid_heating_i = FloatField(default=0)
        pid_heating_d = FloatField(default=0)
        pid_cooling_p = FloatField(default=120)
        pid_cooling_i = FloatField(default=0)
        pid_cooling_d = FloatField(default=0)

        automatic = BooleanField(default=True)
        room = IntegerField()
        start = IntegerField()

        valve_config = CharField(default='cascade')  # options: cascade, equal

        thermostat_group = ForeignKeyField(ThermostatGroup, backref='thermostats', on_delete='CASCADE', default=1)

    class ValveToThermostat(BaseModel):
        class Meta:
            table_name = 'valve_to_thermostat'

        valve = ForeignKeyField(Valve, on_delete='CASCADE')
        thermostat = ForeignKeyField(Thermostat, on_delete='CASCADE')
        mode = CharField(default='heating')
        priority = IntegerField(default=0)

    class Preset(BaseModel):
        id = AutoField()
        name = CharField()
        heating_setpoint = FloatField(default=14.0)
        cooling_setpoint = FloatField(default=30.0)
        active = BooleanField(default=False)
        thermostat = ForeignKeyField(Thermostat, on_delete='CASCADE')

    class DaySchedule(BaseModel):
        id = AutoField()
        index = IntegerField()
        content = TextField()
        mode = CharField(default='heating')
        thermostat = ForeignKeyField(Thermostat, backref='day_schedules', on_delete='CASCADE')

    migrator.create_model(Feature)
    migrator.create_model(Output)
    migrator.create_model(ThermostatGroup)
    migrator.create_model(OutputToThermostatGroup)
    migrator.create_model(Pump)
    migrator.create_model(Valve)
    migrator.create_model(PumpToValve)
    migrator.create_model(Thermostat)
    migrator.create_model(ValveToThermostat)
    migrator.create_model(Preset)
    migrator.create_model(DaySchedule)


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
