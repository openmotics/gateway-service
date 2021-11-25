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
from __future__ import absolute_import

import unittest
import os
import tempfile
from peewee import (
    Model, SqliteDatabase,
    AutoField, CharField, IntegerField, ForeignKeyField
)
import constants


class ORMMigrationsTest(unittest.TestCase):
    """
    This test module contains a single test that will perform all individual peewee ORM migrations
    one after the other. Before and after every migration, there is the possibility to execute
    code by wrapping that code in respectively a _pre_<migration name> and _post_<migration name>
    function. Remember to use model definitions in these functions that reflect how the models were
    at that point in time.
    """

    @classmethod
    def setUpClass(cls):
        cls._test_db_filename = tempfile.mktemp(suffix='.db')
        constants.get_gateway_database_file = lambda: cls._test_db_filename

        gateway_src = os.path.abspath(os.path.join(__file__, '..'))
        cls._migrations_path = os.path.join(gateway_src, '../../../../src/gateway/migrations/orm')

        from peewee_migrate import Router
        test_db = SqliteDatabase(cls._test_db_filename, pragmas={'foreign_keys': 1})
        cls._router = Router(test_db, migrate_dir=cls._migrations_path)

    @classmethod
    def tearDownClass(cls):
        cls._router.database.close()
        os.remove(cls._test_db_filename)

    def test_migrations(self):
        for filename in sorted(os.listdir(self._migrations_path)):
            if not filename.endswith('.py') or filename in ['__init__.py']:
                continue
            base_name = filename.replace('.py', '')
            pre_name = '_pre_{0}'.format(base_name)
            if hasattr(self, pre_name):
                print('Executing {0}...'.format(pre_name))
                getattr(self, pre_name)()
                print('Executing {0}... Done'.format(pre_name))
            self._router.run_one(base_name, self._router.migrator, fake=False)
            post_name = '_post_{0}'.format(base_name)
            if hasattr(self, post_name):
                print('Executing {0}...'.format(post_name))
                getattr(self, post_name)()
                print('Executing {0}... Done'.format(post_name))

    # Below are all the pre- and post-migration test files

    def _pre_021_remove_floors(self):
        _ = self

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

        floor = Floor.create(number=1, name='base floor')
        room = Room.create(number=1, name='living', floor=floor)
        Sensor.create(source='plugin', external_id='foo', name='foo', room=room)
        Sensor.create(source='plugin', external_id='bar', name='bar')

    def _post_021_remove_floors(self):

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

        room = Room.select().where(Room.number == 1).first()
        sensor_foo = Sensor.select().where(Sensor.external_id == 'foo').first()
        sensor_bar = Sensor.select().where(Sensor.external_id == 'bar').first()

        self.assertEqual(room, sensor_foo.room)  # Sensors still have rooms
        self.assertIsNone(sensor_bar.room)

    def _post_034_restore_room_references(self):
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

        room = Room.select().where(Room.number == 1).first()
        room.name = 'living 2'
        room.save()

        Room.create(number=2, name='kitchen')  # This failed after `021_remove_floors`

        sensor_foo = Sensor.select().where(Sensor.external_id == 'foo').first()
        sensor_bar = Sensor.select().where(Sensor.external_id == 'bar').first()

        self.assertEqual(room, sensor_foo.room)  # Sensors still have rooms
        self.assertIsNone(sensor_bar.room)
