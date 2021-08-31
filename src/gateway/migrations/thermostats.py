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
from gateway.models import Feature, Thermostat
from ioc import INJECTED, Inject
from platform_utils import Platform

if False:  # MYPY
    from typing import Any
    from master.classic.master_communicator import MasterCommunicator
    from master.models import BaseModel

logger = logging.getLogger(__name__)


class ThermostatsMigrator(BaseMigrator):

    MIGRATION_KEY = 'thermostats'

    @classmethod
    @Inject
    def _migrate(cls, master_communicator=INJECTED):  # type: (MasterCommunicator) -> None
        # Core(+) platforms only support gateway thermostats
        if Platform.get_platform() in Platform.CoreTypes:
            return

        raise NotImplementedError()
