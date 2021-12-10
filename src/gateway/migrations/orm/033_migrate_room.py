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
    AutoField, CharField, BooleanField, IntegerField, ForeignKeyField,
    FloatField
)
from peewee_migrate import Migrator
import constants

if False:  # MYPY
    from typing import Dict, Any, Type, List


def migrate(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None

    class BaseModel(Model):
        class Meta:
            database = SqliteDatabase(constants.get_gateway_database_file(),
                                      pragmas={'foreign_keys': 1})

    class Room(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField(null=True)
        floor_id = IntegerField()  # This field is a leftover from an in correct migration

    class Output(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='outputs')
        room_number = IntegerField(null=True)

    class Input(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        event_enabled = BooleanField(default=False)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='inputs')
        room_number = IntegerField(null=True)

    class Shutter(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='shutters')
        room_number = IntegerField(null=True)

    class ShutterGroup(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='shutter_groups')
        room_number = IntegerField(null=True)

    class PulseCounter(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField()
        source = CharField()  # Options: 'master' or 'gateway'
        persistent = BooleanField()
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='pulse_counters')
        room_number = IntegerField(null=True)

    class Plugin(BaseModel):
        id = AutoField()
        name = CharField(unique=True)
        version = CharField()

    class Sensor(BaseModel):
        id = AutoField()
        source = CharField()  # Options: 'master' or 'plugin'
        plugin = ForeignKeyField(Plugin, null=True, on_delete='CASCADE')
        external_id = CharField()
        physical_quantity = CharField(null=True)
        unit = CharField(null=True)
        name = CharField()
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='sensors')
        room_number = IntegerField(null=True)

        class Meta:
            indexes = (
                (('source', 'plugin_id', 'external_id', 'physical_quantity'), True),
            )

    class ThermostatGroup(BaseModel):
        class Modes(object):
            HEATING = 'heating'
            COOLING = 'cooling'

        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField()
        threshold_temperature = FloatField(null=True, default=None)
        sensor = ForeignKeyField(Sensor, null=True, backref='thermostat_groups', on_delete='SET NULL')
        mode = CharField(default=Modes.HEATING)  # Options: 'heating' or 'cooling'

    class Thermostat(BaseModel):
        class ValveConfigs(object):
            CASCADE = 'cascade'
            EQUAL = 'equal'

        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField(default='Thermostat')
        state = CharField(default='on')
        sensor = ForeignKeyField(Sensor, null=True, backref='thermostats', on_delete='SET NULL')
        pid_heating_p = FloatField(default=120)
        pid_heating_i = FloatField(default=0)
        pid_heating_d = FloatField(default=0)
        pid_cooling_p = FloatField(default=120)
        pid_cooling_i = FloatField(default=0)
        pid_cooling_d = FloatField(default=0)
        automatic = BooleanField(default=True)
        room = ForeignKeyField(Room, null=True, on_delete='SET NULL', backref='thermostats')
        room_number = IntegerField(null=True)
        start = IntegerField()
        valve_config = CharField(default=ValveConfigs.CASCADE)  # Options: 'cascade' or 'equal'
        thermostat_group = ForeignKeyField(ThermostatGroup, backref='thermostats', on_delete='CASCADE')

    models = [Output, Input, Shutter, ShutterGroup, PulseCounter, Sensor, Thermostat]  # type: List[Type[BaseModel]]
    for model in models:
        for entry in model.select():
            if entry.room is None:
                continue
            entry.room_number = entry.room.number
            entry.save()

    has_floor_id = migrator.database \
                           .execute_sql('select count(*) from pragma_table_info(\'room\') where name = \'floor_id\';') \
                           .fetchone()[0] == 1
    if has_floor_id:
        migrator.remove_fields(Room, 'floor_id')


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass

