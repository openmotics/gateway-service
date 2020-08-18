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
from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import Feature, DataMigration

logger = logging.getLogger('openmotics')


class FeatureMigrator(BaseMigrator):

    MIGRATION_KEY = 'features'

    @classmethod
    def _migrate(cls):
        feature = Feature.get_or_none(name='orm_rooms')
        if feature is not None:
            orm_rooms_migration = DataMigration(name='rooms',
                                                migrated=feature.enabled)
            orm_rooms_migration.save()
            feature.delete_instance()
