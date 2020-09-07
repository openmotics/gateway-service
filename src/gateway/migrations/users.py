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

import os
import json
import logging
import constants
from ioc import INJECTED, Inject
from gateway.migrations.base_migrator import BaseMigrator
from gateway.user_controller import UserController
from gateway.models import User

if False:  # MYPY
    from gateway.scheduling import SchedulingController

logger = logging.getLogger('openmotics')


class UserMigrator(BaseMigrator):

    MIGRATION_KEY = 'users'

    @classmethod
    @Inject
    def _migrate(cls, user_controller=INJECTED):
        # type: (UserController) -> None
        old_sqlite_db = constants.get_config_database_file()
        if os.path.exists(old_sqlite_db):
            import sqlite3
            connection = sqlite3.connect(old_sqlite_db,
                                         detect_types=sqlite3.PARSE_DECLTYPES,
                                         check_same_thread=False,
                                         isolation_level=None)
            cursor = connection.cursor()
            for row in cursor.execute('SELECT id, username, password, accepted_terms FROM users;'):
                user_id = row[0]
                user = User.get_or_none(id=user_id)
                if user is None:
                    user = User(
                        username=row[1],
                        password=row[2],
                        accepted_terms=row[3]
                    )
                    user.save()
            cursor.execute('DROP TABLE users;')
