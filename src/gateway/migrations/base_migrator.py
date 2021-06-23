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

import logging
from gateway.models import DataMigration

if False:  # MYPY
    from typing import Optional

logger = logging.getLogger(__name__)


class BaseMigrator(object):

    MIGRATION_KEY = None  # type: Optional[str]

    @classmethod
    def migrate(cls):  # type: () -> None
        try:
            if cls.MIGRATION_KEY is None:
                return

            # Check if migration already done
            migration = DataMigration.get_or_none(name=cls.MIGRATION_KEY)
            if migration is None:
                migration = DataMigration.create(name=cls.MIGRATION_KEY, migrated=False)
            if migration.migrated:
                return

            logger.info('Migrating ({0})...'.format(cls.__name__))
            cls._migrate()
            logger.info('Migrating ({0})... Done'.format(cls.__name__))

            # Migration complete
            migration.migrated = True
            migration.save()
        except Exception:
            logger.exception('Unexpected error in {0}'.format(cls.__name__))

    @classmethod
    def _migrate(cls):
        raise NotImplementedError()
