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

    class Sensor(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='sensors')

    class ThermostatGroup(BaseModel):
        class Modes(object):
            HEATING = 'heating'
            COOLING = 'cooling'

        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField()
        on = BooleanField(default=True)
        threshold_temperature = FloatField(null=True, default=None)
        sensor = ForeignKeyField(Sensor, null=True, backref='thermostat_groups', on_delete='SET NULL')
        mode = CharField(default=Modes.HEATING)

    class OutputToThermostatGroup(BaseModel):
        id = AutoField()
        output = ForeignKeyField(Output, on_delete='CASCADE')
        thermostat_group = ForeignKeyField(ThermostatGroup, on_delete='CASCADE')
        index = IntegerField()
        mode = CharField()
        value = IntegerField()

        class Meta:
            indexes = (
                (('output_id', 'thermostat_group_id', 'mode'), True),
            )

    class Pump(BaseModel):
        id = AutoField()
        name = CharField()
        output = ForeignKeyField(Output, null=True, backref='pumps', on_delete='SET NULL', unique=True)

    class Valve(BaseModel):
        id = AutoField()
        name = CharField()
        delay = IntegerField(default=60)
        output = ForeignKeyField(Output, backref='valves', on_delete='CASCADE', unique=True)

    class PumpToValve(BaseModel):
        id = AutoField()
        pump = ForeignKeyField(Pump, on_delete='CASCADE')
        valve = ForeignKeyField(Valve, on_delete='CASCADE')

        class Meta:
            indexes = (
                (('pump_id', 'valve_id'), True),
            )

    class Thermostat(BaseModel):
        class ValveConfigs(object):
            CASCADE = 'cascade'
            EQUAL = 'equal'

        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField(default='Thermostat')
        sensor = ForeignKeyField(Sensor, null=True, backref='thermostats', on_delete='SET NULL')
        pid_heating_p = FloatField(default=120)
        pid_heating_i = FloatField(default=0)
        pid_heating_d = FloatField(default=0)
        pid_cooling_p = FloatField(default=120)
        pid_cooling_i = FloatField(default=0)
        pid_cooling_d = FloatField(default=0)
        automatic = BooleanField(default=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='thermostats')
        start = IntegerField()
        valve_config = CharField(default=ValveConfigs.CASCADE)
        thermostat_group = ForeignKeyField(ThermostatGroup, backref='thermostats', on_delete='CASCADE')

    class ValveToThermostat(BaseModel):
        valve = ForeignKeyField(Valve, on_delete='CASCADE')
        thermostat = ForeignKeyField(Thermostat, on_delete='CASCADE')
        mode = CharField(default=ThermostatGroup.Modes.HEATING)
        priority = IntegerField(default=0)

        class Meta:
            indexes = (
                (('valve_id', 'thermostat_id', 'mode'), True),
            )

    class Preset(BaseModel):
        class Types(object):
            MANUAL = 'manual'
            SCHEDULE = 'schedule'
            AWAY = 'away'
            VACATION = 'vacation'
            PARTY = 'party'

        TYPE_TO_SETPOINT = {Types.AWAY: 3,
                            Types.VACATION: 4,
                            Types.PARTY: 5}
        SETPOINT_TO_TYPE = {setpoint: preset_type
                            for preset_type, setpoint in TYPE_TO_SETPOINT.items()}

        id = AutoField()
        type = CharField()
        heating_setpoint = FloatField(default=14.0)
        cooling_setpoint = FloatField(default=30.0)
        active = BooleanField(default=False)
        thermostat = ForeignKeyField(Thermostat, backref='presets', on_delete='CASCADE')

    class DaySchedule(BaseModel):
        id = AutoField()
        index = IntegerField()
        content = TextField()
        mode = CharField(default=ThermostatGroup.Modes.HEATING)
        thermostat = ForeignKeyField(Thermostat, backref='day_schedules', on_delete='CASCADE')

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
