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
import logging
import constants
from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import User

logger = logging.getLogger('openmotics')


class EsafeMigrator(BaseMigrator):

    MIGRATION_KEY = 'esafe'

    @classmethod
    def _migrate(cls):
        # type: () -> None

        # TODO: Migrate esafe data
        # find the eSafe database and migrate the users, settings, rfid, deliveries, and apartments
        # old_sqlite_db = 'database.db'  # TODO: Change this to esafe database
        # if os.path.exists(old_sqlite_db):
        #     import sqlite3
        #     connection = sqlite3.connect(old_sqlite_db,
        #                                  detect_types=sqlite3.PARSE_DECLTYPES,
        #                                  check_same_thread=False,
        #                                  isolation_level=None)
        #     cursor = connection.cursor()
        #     for row in cursor.execute('SELECT id, username, password, accepted_terms FROM users;'):
        #         username = row[1]
        #         user = User.get_or_none(username=username)
        #         if user is None:
        #             user = User(
        #                 username=username,
        #                 password=row[2],
        #                 accepted_terms=row[3]
        #             )
        #             user.save()
        #     cursor.execute('DROP TABLE users;')
        #

        # Change the username into first_name and last_name
        for user in User.select():
            # Read in the existing username, and copy that over to the new property in the user model
            current_username = User.username_old
            user.username = current_username
