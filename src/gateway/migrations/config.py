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
from gateway.models import Config

logger = logging.getLogger('openmotics')


class ConfigMigrator(BaseMigrator):

    MIGRATION_KEY = 'config'

    @classmethod
    def _migrate(cls):
        # type: () -> None
        old_sqlite_db = constants.get_config_database_file()
        if os.path.exists(old_sqlite_db):
            import sqlite3
            connection = sqlite3.connect(old_sqlite_db,
                                         detect_types=sqlite3.PARSE_DECLTYPES,
                                         check_same_thread=False,
                                         isolation_level=None)
            cursor = connection.cursor()
            for row in cursor.execute('SELECT FROM config;'):
                setting = row[1]
                config = Config.get_or_none(setting=setting)
                if config is None:
                    config = Config(
                        setting=setting,
                        data=row[2]
                    )
                    config.save()
            os.rename(old_sqlite_db, '{0}.bak'.format(old_sqlite_db))
