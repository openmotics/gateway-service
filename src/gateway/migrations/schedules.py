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
from gateway.models import Schedule

logger = logging.getLogger('openmotics')


class ScheduleMigrator(BaseMigrator):

    MIGRATION_KEY = 'schedules'

    @classmethod
    def _migrate(cls):
        old_sqlite_db = constants.get_scheduling_database_file()
        if os.path.exists(old_sqlite_db):
            import sqlite3
            connection = sqlite3.connect(old_sqlite_db,
                                         detect_types=sqlite3.PARSE_DECLTYPES,
                                         check_same_thread=False,
                                         isolation_level=None)
            cursor = connection.cursor()
            for row in cursor.execute('SELECT id, name, start, repeat, duration, end, type, arguments, status FROM schedules;'):
                schedule_id = row[0]
                schedule = Schedule.get_or_none(id=schedule_id)
                if schedule is None:
                    schedule = Schedule(name=row[1],
                                        start=row[2],
                                        repeat=row[3],
                                        duration=row[4],
                                        end=row[5],
                                        action=row[6],
                                        arguments=row[7],
                                        status=row[6])
                    schedule.save()
            os.rename(old_sqlite_db, '{0}.bak'.format(old_sqlite_db))
