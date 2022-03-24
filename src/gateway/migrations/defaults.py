# Copyright (C) 2022 OpenMotics BV
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
from gateway.models import Config, Database, DataMigration, Feature, \
    ThermostatGroup

if False:  # MYPY
    from typing import Any

logger = logging.getLogger(__name__)


class DefaultsMigrator(BaseMigrator):
    MIGRATION_KEY = 'defaults'

    @classmethod
    def migrate(cls):  # type: () -> None
        try:
            logger.info('Migrating ({0})...'.format(cls.__name__))
            with Database.get_session() as db:
                cls._seed_defaults(db)
                db.commit()
            logger.info('Migrating ({0})... Done'.format(cls.__name__))
        except Exception:
            logger.exception('Unexpected error in {0}'.format(cls.__name__))

    @classmethod
    def _seed_defaults(cls, db):  # type: (Any) -> None
        logger.debug('Configuring default settings')
        for key, default_value in {'cloud_enabled': True,
                                   'cloud_endpoint': 'cloud.openmotics.com',
                                   'cloud_endpoint_metrics': 'portal/metrics/',
                                   'cloud_metrics_types': [],
                                   'cloud_metrics_sources': [],
                                   'cloud_metrics_enabled|energy': True,
                                   'cloud_metrics_enabled|counter': True,
                                   'cloud_metrics_batch_size': 50,
                                   'cloud_metrics_min_interval': 300,
                                   'cloud_support': False,
                                   'cors_enabled': False}.items():
            if Config.get_entry(key, None) is None:
                Config.set_entry(key, default_value)

        logger.debug('Configuring default features')
        for name, default_value in {Feature.THERMOSTATS_GATEWAY: False}.items():
            feature = db.query(Feature).filter_by(name=name).one_or_none()
            if feature is None:
                db.add(Feature(name=name, enabled=default_value))

        logger.debug('Configuring thermostats')
        thermostat_group = db.query(ThermostatGroup).first()
        if thermostat_group is None:
            db.add(ThermostatGroup(number=0, name='default'))
