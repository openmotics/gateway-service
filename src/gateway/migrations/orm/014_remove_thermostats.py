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
    ForeignKeyField, BooleanField, CompositeKey,
    FloatField, TextField
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
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField(null=True)

    class Room(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField(null=True)
        floor = ForeignKeyField(Floor, null=True, on_delete='SET NULL', backref='rooms')

    class Output(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='outputs')

    class ThermostatGroup(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField()
        on = BooleanField(default=True)
        threshold_temp = IntegerField(null=True, default=None)
        sensor = IntegerField(null=True, default=None)
        mode = CharField(default='heating')

    class OutputToThermostatGroup(BaseModel):
        output = ForeignKeyField(Output, on_delete='CASCADE')
        thermostat_group = ForeignKeyField(ThermostatGroup, on_delete='CASCADE')
        index = IntegerField()
        mode = CharField()
        value = IntegerField()

        class Meta:
            primary_key = CompositeKey('output', 'thermostat_group')

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
        pump = ForeignKeyField(Pump, on_delete='CASCADE')
        valve = ForeignKeyField(Valve, on_delete='CASCADE')

        class Meta:
            primary_key = CompositeKey('pump', 'valve')

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
        valve_config = CharField(default='cascade')
        thermostat_group = ForeignKeyField(ThermostatGroup, backref='thermostats', on_delete='CASCADE', default=1)

    class ValveToThermostat(BaseModel):
        valve = ForeignKeyField(Valve, on_delete='CASCADE')
        thermostat = ForeignKeyField(Thermostat, on_delete='CASCADE')
        mode = CharField(default='heating')
        priority = IntegerField(default=0)

        class Meta:
            table_name = 'valve_to_thermostat'

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

    migrator.remove_model(DaySchedule)
    migrator.remove_model(Preset)
    migrator.remove_model(ValveToThermostat)
    migrator.remove_model(Thermostat)
    migrator.remove_model(PumpToValve)
    migrator.remove_model(Valve)
    migrator.remove_model(Pump)
    migrator.remove_model(OutputToThermostatGroup)
    migrator.remove_model(ThermostatGroup)


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
