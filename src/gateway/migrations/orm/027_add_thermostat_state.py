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
Moves state from thermostat to thermostat unit
"""

from peewee import (
    Model, Database, SqliteDatabase,
    AutoField, CharField, IntegerField,
    ForeignKeyField, BooleanField, FloatField
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

    class Room(BaseModel):
        id = AutoField()
        number = IntegerField(unique=True)
        name = CharField(null=True)

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
        on = BooleanField(default=True)
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
        valve_config = CharField(default=ValveConfigs.CASCADE)  # Options: 'cascade' or 'equal'
        thermostat_group = ForeignKeyField(ThermostatGroup, backref='thermostats', on_delete='CASCADE')

    migrator.add_columns(Thermostat,
                         state=CharField(default='on'))


def rollback(migrator, database, fake=False, **kwargs):
    # type: (Migrator, Database, bool, Dict[Any, Any]) -> None
    pass
