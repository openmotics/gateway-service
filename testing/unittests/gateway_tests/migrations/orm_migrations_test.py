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
        constants.get_gateway_database_file = lambda: cls._test_db_filename
        cls._test_db_filename = tempfile.mktemp(suffix='.db')

    @classmethod
    def tearDownClass(cls):
        pass  # os.remove(cls._test_db_filename)

    def test_migrations(self):
        gateway_src = os.path.abspath(os.path.join(__file__, '..'))
        path = os.path.join(gateway_src, '../../../../src/gateway/migrations/orm')

        from peewee_migrate import Router
        test_db = SqliteDatabase(self._test_db_filename, pragmas={'foreign_keys': 1})
        router = Router(test_db, migrate_dir=path)

        for filename in sorted(os.listdir(path)):
            if not filename.endswith('.py') or filename in ['__init__.py']:
                continue
            base_name = filename.replace('.py', '')
            if hasattr(self, '_pre_{0}'.format(base_name)):
                getattr(self, '_pre_{0}'.format(base_name))()
            router.run_one(base_name, router.migrator, fake=False)
            if hasattr(self, '_post_{0}'.format(base_name)):
                getattr(self, '_post_{0}'.format(base_name))()

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

        floor = Floor.create(number=1, name='base floor')
        Room.create(number=1, name='living', floor=floor)

    def _post_032_fix_room(self):
        _ = self

        class BaseModel(Model):
            class Meta:
                database = SqliteDatabase(constants.get_gateway_database_file(),
                                          pragmas={'foreign_keys': 1})

        class Room(BaseModel):
            id = AutoField()
            number = IntegerField(unique=True)
            name = CharField(null=True)

        room = Room.select().where(Room.number == 1).first()
        room.name = 'living 2'
        room.save()

        Room.create(number=2, name='kitchen')  # This failed before `032_fix_room`
