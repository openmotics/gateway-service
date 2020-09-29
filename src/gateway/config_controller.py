# Copyright (C) 2017 OpenMotics BV
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
Configuration controller
"""

from __future__ import absolute_import
import logging
import ujson as json
from ioc import Injectable, Inject, Singleton, INJECTED
from gateway.models import Config

if False:  # MYPY
    from typing import Optional, Any

logger = logging.getLogger("openmotics")


@Injectable.named('configuration_controller')
@Singleton
class ConfigurationController(object):

    @Inject
    def __init__(self):
        # type: () -> None
        """ Constructs a new ConfigController. """
        self.__check_tables()

    def __check_tables(self):
        # type: () -> None
        """ Creates tables and execute migrations """

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
            if self.get(key) is None:
                self.set(key, default_value)

    def get(self, key, fallback=None):
        # type: (str, Optional[Any]) -> Optional[Any]
        """ Retrieves a setting from the DB, returns the argument 'fallback' when non existing """
        _ = self
        config_orm = Config.select().where(
            Config.setting == key.lower()
        ).first()
        if config_orm is not None:
            return json.loads(config_orm.data)
        return fallback

    def set(self, key, value):
        # type: (str, Any) -> None
        """ Sets a setting in the DB, does overwrite if already existing """
        _ = self
        config_orm = Config.select().where(
            Config.setting == key.lower()
        ).first()
        if config_orm is not None:
            # if the key already exists, update the value
            config_orm.data = json.dumps(value)
            config_orm.save()
            return config_orm.data
        else:
            # create a new setting if it was non existing
            config_orm = Config(
                setting=key,
                data=json.dumps(value)
            )
            config_orm.save()

    def remove(self, key):
        # type: (str) -> None
        """ Removes a setting from the DB """
        _ = self
        Config.delete().where(
            Config.setting == key.lower()
        ).execute()


